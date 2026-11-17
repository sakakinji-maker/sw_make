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
