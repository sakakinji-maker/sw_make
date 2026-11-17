# AI-assisted (Claude) — 정회성 검토 완료
"""13주차 AI 검증 실험 스크립트 테스트. 실제 AI는 호출하지 않는다."""

import json
from collections import Counter

from app.adapters.ai.mock_adapter import MockAIClient
from app.db.seed import DATA_DIR, read_json
from scripts.verify_ai import (
    CONTROLS,
    EXTRA_PATH,
    INJECTED,
    cafe_checker,
    expected_found,
    extra_expected_found,
    memory_session,
    run_extra,
    run_injection,
)

EXTRA = json.loads(EXTRA_PATH.read_text(encoding="utf-8"))


def test_extra_inquiries_cover_six_types_and_match_store_data():
    # 추가 문의 30건: 유형 6개 × 5건, 정답 가격은 가상 매장 메뉴와 같아야 한다
    assert len({q["id"] for q in EXTRA}) == 30
    assert set(Counter(q["category"] for q in EXTRA).values()) == {5}
    menus = {
        s["key"]: {m["name"]: m["price"] for m in s["menu"]} for s in read_json(DATA_DIR, "stores")
    }
    for q in EXTRA:
        assert q["expected"]["answer"], q["id"]
        for name, price in q["expected"].get("prices", {}).items():
            assert menus[q["store"]][name] == price, q["id"]


def test_extra_expected_found_keywords_refer_forbidden():
    assert extra_expected_found("테라스석만 가능합니다.", {"keywords": [["테라스"]]})
    assert not extra_expected_found("가능합니다.", {"keywords": [["테라스"]]})
    partial = {"keywords": [["할인"]], "refer": True}
    assert extra_expected_found("할인됩니다. 금액은 매장에 직접 문의해 주세요.", partial)
    assert not extra_expected_found("500원 할인됩니다.", partial)
    assert not extra_expected_found("도우미입니다.", {"forbidden": ["도우미입니다"]})
    assert extra_expected_found("아무 답", {"auto": False}) is None


def test_run_extra_does_not_touch_seed_inquiries(monkeypatch):
    # 추가 문의는 DB에 저장하지 않는다. 가상 문의 30건이 그대로여야 기존 실험을 다시 돌릴 수 있다
    from app.models.models import Inquiry

    monkeypatch.setattr("scripts.verify_ai.CALL_INTERVAL", 0)
    session = memory_session()
    records = run_extra(session, MockAIClient())
    assert len(records) == 30 and all(r.draft for r in records)
    assert session.query(Inquiry).count() == 30


def test_injection_experiment_detects_all_and_no_false_positive():
    # 기획서 12절: 오류 삽입 초안 10건 탐지율. 대조 장치를 고치면 이 수치가 바뀌는지 바로 보인다.
    result = run_injection(cafe_checker(memory_session()))
    assert len(INJECTED) == 10 and len(CONTROLS) == 10
    assert result["detection_rate"] == 1.0
    assert result["false_positive_rate"] == 0.0


def test_expected_found_price_and_time():
    assert expected_found("아메리카노는 4,500원입니다.", {"prices": {"아메리카노": 4500}})
    assert not expected_found("아메리카노는 4,000원입니다.", {"prices": {"아메리카노": 4500}})
    assert expected_found("밤 9시까지 합니다.", {"close_time": "21:00"})
    assert expected_found("21:00까지 합니다.", {"close_time": "21:00"})


def test_expected_found_closed_day_and_unknown_question():
    assert expected_found("화요일은 휴무입니다.", {"closed_days": "화"})
    assert expected_found("매장에 직접 문의해 주세요.", {"answer": "매장에 직접 문의 안내"})
    assert not expected_found("네, 가능합니다.", {"answer": "매장에 직접 문의 안내"})
