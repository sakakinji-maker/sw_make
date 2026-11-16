# AI-assisted (Claude) — 정회성 검토 완료
"""13주차 AI 검증 실험 스크립트 테스트. 실제 AI는 호출하지 않는다."""

from scripts.verify_ai import (
    CONTROLS,
    INJECTED,
    cafe_checker,
    expected_found,
    memory_session,
    run_injection,
)


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
