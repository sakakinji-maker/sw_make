"""채널 Strategy 테스트 (F-04-2)."""

import pytest

from app.adapters.ai.mock_adapter import MockAIClient
from app.services.marketing.service import MarketingService
from app.services.marketing.strategies import available_channels, get_strategy


def test_channels_registered():
    assert set(available_channels()) >= {"instagram", "blog", "sms"}


def test_sms_rejects_hashtags():
    violations = get_strategy("sms").check("오늘만 라떼 1+1! #이벤트")
    assert any("해시태그" in v for v in violations)


def test_instagram_valid_text():
    text = "가을 신메뉴 출시! 따뜻한 밤라떼로 하루를 마무리하세요. " * 2 + "#카페 #신메뉴 #밤라떼"
    assert get_strategy("instagram").check(text) == []


def test_prompt_requires_korean_and_respectful_tone():
    prompt = get_strategy("sms").build_prompt("중장년층(50대 이상)", ["점심 특선"])

    assert "자연스러운 한국어" in prompt
    assert "친절하고 정중한 말투" in prompt
    assert "사실처럼 만들어내지 마세요" in prompt


def test_service_flags_foreign_cjk_characters():
    response = "이번 주말 단체 예약 시 特権 혜택을 누리세요."
    result = MarketingService(MockAIClient(fixed_response=response)).generate(
        "sms", "중장년층", ["단체 예약"]
    )

    assert result.text == response
    assert any("외국어 문자" in violation for violation in result.violations)


def test_unknown_channel():
    with pytest.raises(ValueError):
        get_strategy("tiktok")


def test_service_handles_ai_failure():
    result = MarketingService(MockAIClient(fail=True)).generate("sms", "라떼", [])
    assert result.text is None and result.error


# ---------- 13주차 이후: 매장 정보 전달, 길이 조정, 외국어 고치기 ----------


def test_prompt_includes_store_facts_when_given():
    prompt = get_strategy("blog").build_prompt(
        "대학생", [], "홍시에이드 출시", store_info="- 판매 메뉴: 아메리카노 4,500원"
    )
    assert "아메리카노 4,500원" in prompt and "홍시에이드 출시" in prompt
    assert "한자" in prompt


def test_sms_is_long_enough_for_a_real_message():
    sms = get_strategy("sms")
    assert sms.check("홍시에이드 신메뉴 나왔어요. 오늘 만나서 드셔보세요.")  # 너무 짧음
    assert sms.min_length >= 80


def test_store_info_lists_only_menus_on_sale():
    from datetime import time

    from app.models.models import MenuItem, Store
    from app.services.marketing.service import store_info

    store = Store(name="브루밍 카페", address="서울", open_time=time(9), close_time=time(21),
                  closed_days="월")
    menus = [MenuItem(name="라떼", price=5500, on_sale=True),
             MenuItem(name="단종메뉴", price=1000, on_sale=False)]
    info = store_info(store, menus)
    assert "브루밍 카페" in info and "09:00~21:00" in info and "월요일" in info
    assert "라떼 5,500원" in info and "단종메뉴" not in info


class _Seq(MockAIClient):
    """정해 둔 답을 차례로 돌려주는 가짜 AI."""

    def __init__(self, answers):
        super().__init__()
        self.answers = list(answers)
        self.prompts = []

    def generate(self, prompt, system=None):
        self.prompts.append(prompt)
        return self.answers.pop(0)


def test_service_asks_ai_to_fix_remaining_foreign_chars():
    bad = "주말에 特別한 라떼를 드셔 보세요. 따뜻한 한 잔이 기다려요."
    ai = _Seq([bad, bad, bad, "주말에 특별한 라떼를 드셔 보세요. 따뜻한 한 잔이 기다려요."])
    result = MarketingService(ai).generate("sms", "대학생", [])
    assert result.text.startswith("주말에 특별한")
    assert "特別" in ai.prompts[-1]  # 마지막 요청은 '이 글자만 고쳐 달라'
    assert not any("외국어" in v for v in result.violations)
