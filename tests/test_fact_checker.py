"""AI 초안 DB 대조 테스트 (F-03-3)."""

from datetime import time

from app.services.inquiry.fact_checker import FactChecker

checker = FactChecker(
    menu_prices={"아메리카노": 4500, "카페라떼": 5000},
    open_time=time(9, 0),
    close_time=time(21, 0),
)


def test_correct_draft_passes():
    text = "아메리카노는 4,500원이고 영업시간은 09:00~21:00입니다."
    assert checker.check(text) == []


def test_wrong_price_detected():
    result = checker.check("아메리카노는 4,000원입니다.")
    assert len(result) == 1
    assert result[0].kind == "가격"


def test_wrong_time_detected():
    result = checker.check("저녁 22:00까지 영업합니다.")
    assert [m.kind for m in result] == ["시각"]


def test_single_digit_hour_normalized():
    assert checker.check("9:00에 문을 엽니다.") == []


# ---------- 휴무일 대조 (13주차 F-03-3 보강) ----------
# AI-assisted (Claude) — 정회성 검토 완료

closed_mon = FactChecker(
    menu_prices={"아메리카노": 4500},
    open_time=time(9, 0),
    close_time=time(21, 0),
    closed_days="월",
)


def test_correct_closed_day_passes():
    assert closed_mon.check("매주 월요일은 휴무입니다. 화요일에는 정상 영업합니다.") == []


def test_wrong_closed_day_detected():
    result = closed_mon.check("저희는 화요일에 쉽니다.")
    assert [(m.kind, m.found) for m in result] == [("휴무일", "화요일")]


def test_open_on_closed_day_detected():
    result = closed_mon.check("월요일에도 09:00부터 영업합니다.")
    assert [(m.kind, m.found) for m in result] == [("휴무일", "월요일")]


def test_no_holiday_claim_detected():
    result = closed_mon.check("저희 매장은 연중무휴입니다.")
    assert [m.kind for m in result] == ["휴무일"]


def test_weekday_without_context_is_ignored():
    # 휴무·영업 단서가 없는 문장은 판단하지 않는다 (오탐 방지)
    assert closed_mon.check("월요일 오전에 예약하신 분께 연락드렸습니다.") == []


def test_store_without_holiday_flags_off_claims():
    # 휴무일이 없는 매장("")에서 "화요일 휴무"라고 하면 틀린 정보다
    no_holiday = FactChecker({}, time(9, 0), time(21, 0), closed_days="")
    assert [m.found for m in no_holiday.check("화요일은 휴무입니다.")] == ["화요일"]


def test_closed_days_not_given_skips_day_check():
    # 휴무일을 넘기지 않는 호출부(마케팅)는 기존처럼 가격·시각만 본다
    assert checker.check("화요일은 휴무입니다.") == []
