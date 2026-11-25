# AI-assisted (Claude) — 정회성 검토 완료
"""13주차 AI 검증 실험 (기획서 12절). 결과는 docs/verification/results/에 저장한다.

실행:
    python -m scripts.verify_ai                 # 오류 삽입 실험만 (AI 호출 없음)
    python -m scripts.verify_ai --ai            # + 실제 AI로 F-03 문의 30건, F-04 3채널×10건
    python -m scripts.verify_ai --ai --model gemini-3.5-flash-lite
    python -m scripts.verify_ai --recheck        # 저장된 초안을 지금의 대조 장치로 다시 검사
    python -m scripts.verify_ai --extra          # 추가 문의 30건(유형 6개)만 실제 AI로 실행

메모리 DB에 가상 데이터(seed_data)를 넣고 실행하므로 app.db 파일은 건드리지 않는다.
"""

import argparse
import csv
import json
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.ai import AIClient, get_ai_client
from app.config import AI_API_KEY, AI_MODEL, AI_PROVIDER
from app.db.database import Base
from app.db.seed import DATA_DIR, load_all
from app.models.models import Inquiry, Store
from app.services.inquiry.fact_checker import FactChecker
from app.services.inquiry.service import InquiryService
from app.services.marketing.service import MarketingService

RESULT_DIR = Path(__file__).resolve().parents[1] / "docs" / "verification" / "results"
EXTRA_PATH = RESULT_DIR.parent / "extra_inquiries.json"
CALL_INTERVAL = 4.5  # 무료 등급 분당 호출 제한(약 15회)을 넘지 않게 쉬는 시간(초)
FACT_KEYS = ("prices", "open_time", "close_time", "closed_days")
# 사람 평가 시트의 열. 기준은 docs/verification/eval_rubric.md
SHEET_HEADER = [
    "id",
    "유형",
    "문의",
    "기대 답변",
    "AI 초안",
    "자동 경고",
    "정확성(O/X)",
    "근거성(O/X)",
    "완전성(O/△/X)",
    "표현(O/△/X)",
    "판정(그대로/일부 수정/불가)",
    "사유",
    "메모",
]

# ---------- 오류 삽입 실험 (대조 장치 자체 검증, AI 호출 없음) ----------
# 브루밍 카페: 09:00~21:00, 월요일 휴무, 아메리카노 4,500 / 카페라떼 5,500 / 밤라떼 6,000 ...
INJECTED = [
    ("가격", "아메리카노는 4,000원입니다."),
    ("가격", "밤라떼는 6,500원이에요."),
    ("가격", "카페라떼는 5,000원입니다."),  # 5,000원 → 실제 가격은 5,500원
    ("가격", "크루아상은 3000원입니다."),
    ("시각", "영업시간은 10:00부터 21:00까지입니다."),
    ("시각", "평일에는 22:00까지 영업합니다."),
    ("시각", "저녁 10시까지 영업합니다."),  # HH:MM이 아닌 'N시' 표기
    ("휴무일", "매주 화요일은 휴무입니다."),
    ("휴무일", "월요일에도 정상 영업합니다."),
    ("휴무일", "연중무휴로 운영합니다."),
]
CONTROLS = [
    "아메리카노는 4,500원입니다.",
    "밤라떼는 6,000원입니다.",
    "영업시간은 09:00~21:00입니다.",
    "9:00에 문을 엽니다.",
    "매주 월요일은 휴무입니다.",
    "화요일부터 일요일까지 영업합니다.",
    "주차는 매장에 직접 문의해 주세요.",
    "카페라떼 5,500원, 카푸치노 5,500원입니다.",
    "치즈케이크는 7,000원입니다.",
    "월요일을 제외하고 매일 영업합니다.",
]


def cafe_checker(session: Session) -> FactChecker:
    store = session.query(Store).filter_by(name="브루밍 카페").one()
    return InquiryService._checker(store, store.menu_items)


def run_injection(checker: FactChecker) -> dict[str, Any]:
    """오류 삽입 초안의 탐지율과 정상 초안의 오탐률을 잰다."""
    injected = [
        {"kind": kind, "text": text, "detected": bool(checker.check(text))}
        for kind, text in INJECTED
    ]
    controls = [{"text": text, "flagged": bool(checker.check(text))} for text in CONTROLS]
    return {
        "injected": injected,
        "controls": controls,
        "detection_rate": sum(r["detected"] for r in injected) / len(injected),
        "false_positive_rate": sum(r["flagged"] for r in controls) / len(controls),
    }


# ---------- F-03 문의 30건 (실제 AI) ----------


@dataclass
class DraftRecord:
    id: str
    store: str
    category: str
    content: str
    draft: str | None
    error: str | None
    mismatches: list[dict[str, str]]
    expected_found: bool | None  # 정답 사실(가격·시각·휴무·직접 문의 안내)이 초안에 들어 있는지
    seconds: float


# 자동 채점 단서. 11/25 재실험부터 없는 메뉴는 "판매하지 않는 메뉴"로 안내한다. (D-31)
REFER_WORDS = ("직접 문의", "문의해 주")
NOT_SOLD_WORDS = ("판매하지 않", "판매를 하지 않")


def expected_found(draft: str, expected: dict[str, Any]) -> bool:
    """seed_data의 expected 값이 초안에 모두 나타나는지 본다. (자동 정답 확인)"""
    checks: list[bool] = []
    for price in expected.get("prices", {}).values():
        checks.append(f"{price:,}원" in draft or f"{price}원" in draft)
    for key in ("open_time", "close_time"):
        if key in expected:
            checks.append(_time_mentioned(draft, expected[key]))
    for day in expected.get("closed_days", ""):
        if day.strip(","):
            checks.append(f"{day}요일" in draft)
    if not checks:  # 매장 정보에 없는 질문 → 판매하지 않음 또는 직접 문의 안내가 정답 (D-31)
        checks.append(any(word in draft for word in NOT_SOLD_WORDS + REFER_WORDS))
    return all(checks)


def _time_mentioned(draft: str, hhmm: str) -> bool:
    hour, minute = (int(x) for x in hhmm.split(":"))
    variants = {f"{hour:02d}:{minute:02d}", f"{hour}:{minute:02d}"}
    if minute == 0:
        variants |= {f"{hour}시", f"{hour % 12 or 12}시"}
    return any(re.search(rf"(?<!\d){re.escape(v)}", draft) for v in variants)


def run_inquiries(session: Session, ai: AIClient) -> list[DraftRecord]:
    rows = json.loads((DATA_DIR / "inquiries.json").read_text(encoding="utf-8"))
    inquiries = session.query(Inquiry).order_by(Inquiry.id).all()
    service = InquiryService(ai)
    records = []
    for row, inquiry in zip(rows, inquiries, strict=True):
        records.append(_draft_one(service, row, inquiry))
        print(f"  F-03 {row['id']}: {'오류' if records[-1].error else 'OK'}", flush=True)
        time.sleep(CALL_INTERVAL)
    return records


def _draft_one(
    service: InquiryService,
    row: dict[str, Any],
    inquiry: Inquiry | SimpleNamespace,
    judge: Callable[[str, dict[str, Any]], bool | None] = expected_found,
) -> DraftRecord:
    store = inquiry.store
    started = time.time()
    result = service.draft_answer(store, store.menu_items, store.faqs, inquiry)
    return DraftRecord(
        id=row["id"],
        store=store.name,
        category=row["category"],
        content=row["content"],
        draft=result.draft,
        error=result.error,
        mismatches=[asdict(m) for m in result.mismatches],
        expected_found=judge(result.draft, row.get("expected", {})) if result.draft else None,
        seconds=round(time.time() - started, 1),
    )


# ---------- F-03 추가 문의 30건 (실제 AI, 유형 확대) ----------
# 기존 30건(가격·영업시간·근거없음)에 없던 유형: FAQ, 조건, 복합, 표현변형, 틀린전제, 정책·악의


def extra_expected_found(draft: str, expected: dict[str, Any]) -> bool | None:
    """추가 문의의 자동 정답 확인. 자동으로 판단할 수 없는 문의(auto=false)는 None."""
    if expected.get("auto") is False:
        return None
    facts = {k: v for k, v in expected.items() if k in FACT_KEYS}
    checks = [expected_found(draft, facts)] if facts else []
    checks += [any(word in draft for word in group) for group in expected.get("keywords", [])]
    checks += [word not in draft for word in expected.get("forbidden", [])]
    if expected.get("refer"):  # 근거 없는 부분은 직접 문의로 안내해야 한다
        checks.append(any(word in draft for word in REFER_WORDS))
    return all(checks)


def run_extra(session: Session, ai: AIClient) -> list[DraftRecord]:
    """DB에 넣지 않은 임시 문의로 초안을 만든다. (가상 데이터 30건은 그대로 둔다)"""
    rows = json.loads(EXTRA_PATH.read_text(encoding="utf-8"))
    stores = {"cafe": "브루밍 카페"}
    service = InquiryService(ai)
    records = []
    for row in rows:
        store = session.query(Store).filter_by(name=stores[row["store"]]).one()
        # Inquiry 모델을 만들면 세션에 붙어 저장되므로, 매장과 내용만 가진 임시 객체를 쓴다
        inquiry = SimpleNamespace(store=store, content=row["content"])
        records.append(_draft_one(service, row, inquiry, extra_expected_found))
        print(f"  F-03 {row['id']}: {'오류' if records[-1].error else 'OK'}", flush=True)
        time.sleep(CALL_INTERVAL)
    return records


# ---------- F-04 채널 3개 × 10건 (실제 AI, 전지호와 공동) ----------

TARGETS = [
    ("브루밍 카페", "아메리카노", ["아침", "테이크아웃"]),
    ("브루밍 카페", "카페라떼", ["부드러운", "오후"]),
    ("브루밍 카페", "딸기 스무디", ["달콤한", "시즌 한정"]),
    ("브루밍 카페", "아메리카노", ["디저트", "주말"]),
    ("브루밍 카페", "카페라떼", ["따뜻한", "신메뉴"]),
    ("브루밍 카페", "딸기 스무디", ["갓 만든", "브런치"]),
    ("브루밍 카페", "아메리카노", ["깔끔", "직장인"]),
    ("브루밍 카페", "카페라떼", ["부드러운", "환절기"]),
    ("브루밍 카페", "딸기 스무디", ["상큼", "가을"]),
    ("브루밍 카페", "아메리카노", ["진한", "연말"]),
]
CHANNELS = ["instagram", "blog", "sms"]


def run_marketing(session: Session, ai: AIClient) -> list[dict[str, Any]]:
    service = MarketingService(ai)
    records = []
    for channel in CHANNELS:
        for store_name, target, keywords in TARGETS:
            store = session.query(Store).filter_by(name=store_name).one()
            result = service.generate(channel, target, keywords, store, store.menu_items)
            records.append(_marketing_record(channel, store_name, target, result))
            print(f"  F-04 {channel} {target}: {'오류' if result.error else 'OK'}", flush=True)
            time.sleep(CALL_INTERVAL)
    return records


def _marketing_record(channel: str, store: str, target: str, result: Any) -> dict[str, Any]:
    rule = [v for v in result.violations if v.startswith(("글자 수", "해시태그"))]
    return {
        "channel": channel,
        "store": store,
        "target": target,
        "text": result.text,
        "error": result.error,
        "rule_violations": rule,
        "fact_violations": [v for v in result.violations if v not in rule],
    }


def recheck_saved(session: Session) -> list[dict[str, Any]]:
    """f03_drafts.json의 초안을 AI 호출 없이 지금의 FactChecker로 다시 대조한다."""
    saved = json.loads((RESULT_DIR / "f03_drafts.json").read_text(encoding="utf-8"))
    inquiries = session.query(Inquiry).order_by(Inquiry.id).all()
    rows = []
    for record, inquiry in zip(saved["records"], inquiries, strict=True):
        if record["draft"] is None:
            continue
        store = inquiry.store
        checker = InquiryService._checker(store, store.menu_items)
        now = checker.check(record["draft"], quoted=inquiry.content)
        rows.append(
            {"id": record["id"], "before": record["mismatches"], "after": [asdict(m) for m in now]}
        )
    return rows


# ---------- 집계·저장 ----------


def summarize_inquiries(records: list[DraftRecord]) -> dict[str, Any]:
    ok = [r for r in records if r.draft is not None]
    by_category: dict[str, dict[str, int]] = {}
    for r in ok:
        c = by_category.setdefault(r.category, {"n": 0, "mismatch": 0, "expected_found": 0})
        c["n"] += 1
        c["mismatch"] += bool(r.mismatches)
        c["expected_found"] += bool(r.expected_found)
    return {
        "total": len(records),
        "generated": len(ok),
        "ai_errors": len(records) - len(ok),
        "mismatch_drafts": sum(bool(r.mismatches) for r in ok),
        "expected_found": sum(bool(r.expected_found) for r in ok),
        "avg_seconds": round(sum(r.seconds for r in ok) / len(ok), 1) if ok else None,
        "by_category": by_category,
    }


def summarize_marketing(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for channel in CHANNELS:
        rows = [r for r in records if r["channel"] == channel and r["text"]]
        summary[channel] = {
            "generated": len(rows),
            "rule_pass": sum(not r["rule_violations"] for r in rows),
            "fact_pass": sum(not r["fact_violations"] for r in rows),
        }
    return summary


def write_json(name: str, data: Any) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2, default=asdict)
    (RESULT_DIR / name).write_text(text + "\n", encoding="utf-8")


def write_human_sheet(
    records: list[DraftRecord],
    name: str = "f03_human_eval.csv",
    answers: dict[str, str] | None = None,
) -> None:
    """팀원이 기준별 O/△/X와 '그대로 / 일부 수정 / 불가'를 채울 평가 시트. (기획서 12절)"""
    answers = answers or {}
    with (RESULT_DIR / name).open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:  # 엑셀 한글 깨짐 방지
        w = csv.writer(f)
        w.writerow(SHEET_HEADER)
        for r in records:
            warn = ", ".join(f"{m['kind']} {m['found']}" for m in r.mismatches)
            draft = r.draft or f"(실패) {r.error}"
            w.writerow([r.id, r.category, r.content, answers.get(r.id, ""), draft, warn] + [""] * 7)


def memory_session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    load_all(session)
    session.commit()
    return session


def timed(label: str, fn: Callable[[], Any]) -> Any:
    started = time.time()
    print(f"[{label}] 시작", flush=True)
    result = fn()
    print(f"[{label}] 끝 ({time.time() - started:.0f}초)", flush=True)
    return result


def run_extra_experiment(session: Session, ai: AIClient, meta: dict[str, str]) -> None:
    drafts = timed("F-03 추가 문의", lambda: run_extra(session, ai))
    summary = summarize_inquiries(drafts)
    write_json("f03_extra_drafts.json", {"meta": meta, "summary": summary, "records": drafts})
    rows = json.loads(EXTRA_PATH.read_text(encoding="utf-8"))
    answers = {row["id"]: row["expected"]["answer"] for row in rows}
    write_human_sheet(drafts, "f03_extra_human_eval.csv", answers)
    print(json.dumps(summary, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="13주차 AI 검증 실험")
    parser.add_argument("--ai", action="store_true", help="실제 AI 호출 실험까지 실행")
    parser.add_argument("--extra", action="store_true", help="추가 문의 30건(유형 확대)만 실행")
    parser.add_argument("--recheck", action="store_true", help="저장된 초안 재대조")
    parser.add_argument("--model", default=AI_MODEL, help="AI 모델 ID (기본: .env의 AI_MODEL)")
    args = parser.parse_args()

    session = memory_session()
    injection = run_injection(cafe_checker(session))
    write_json("injection.json", injection)
    print(f"오류 삽입: 탐지율 {injection['detection_rate']:.0%}, ", end="")
    print(f"정상 초안 오탐률 {injection['false_positive_rate']:.0%}")
    if args.recheck:
        rows = recheck_saved(session)
        write_json("f03_recheck.json", rows)
        before, after = (sum(bool(r[k]) for r in rows) for k in ("before", "after"))
        print(f"재대조: 경고 초안 {before}건 → {after}건 (전체 {len(rows)}건)")
    if not (args.ai or args.extra):
        return

    ai = get_ai_client(AI_PROVIDER, AI_API_KEY, args.model)
    meta = {"provider": AI_PROVIDER, "model": args.model, "run_at": time.strftime("%Y-%m-%d %H:%M")}
    if args.extra:
        run_extra_experiment(session, ai, meta)
    if not args.ai:
        return
    drafts = timed("F-03 문의 30건", lambda: run_inquiries(session, ai))
    write_json(
        "f03_drafts.json", {"meta": meta, "summary": summarize_inquiries(drafts), "records": drafts}
    )
    write_human_sheet(drafts)
    marketing = timed("F-04 3채널×10건", lambda: run_marketing(session, ai))
    write_json(
        "f04_marketing.json",
        {"meta": meta, "summary": summarize_marketing(marketing), "records": marketing},
    )
    print(json.dumps(summarize_inquiries(drafts), ensure_ascii=False))
    print(json.dumps(summarize_marketing(marketing), ensure_ascii=False))


if __name__ == "__main__":
    main()
