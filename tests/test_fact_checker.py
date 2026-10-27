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
