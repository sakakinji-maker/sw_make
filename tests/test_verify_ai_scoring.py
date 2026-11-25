"""D-31: 검증 스크립트 자동 채점 기준."""

from scripts.verify_ai import expected_found, extra_expected_found


def test_not_sold_answer_counts_for_unknown_menu():
    draft = "안녕하세요, 브루밍 카페입니다. 현재 생맥주는 판매하지 않는 메뉴입니다."
    assert expected_found(draft, {})
    assert expected_found("현재 와인 판매를 하지 않습니다.", {})


def test_unknown_menu_without_guidance_fails():
    assert not expected_found("생맥주는 6,000원입니다.", {})


def test_refer_still_requires_referral():
    # 정책 문의(refer)는 '판매하지 않'만으로는 정답이 아니다
    assert not extra_expected_found("할인은 판매하지 않습니다.", {"refer": True})
    assert extra_expected_found("매장으로 직접 문의해 주세요.", {"refer": True})


def test_e21_keywords_accept_not_sold():
    expected = {"keywords": [["없", "판매하지 않", "직접 문의", "문의해 주"]]}
    assert extra_expected_found("딸기라떼는 현재 판매하지 않는 메뉴입니다.", expected)
