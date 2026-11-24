# AI-assisted (Claude)
"""AI 초안의 마크다운 기호가 손님에게 보이지 않게 정리하는지."""

import pytest

from app.services.inquiry.service import SYSTEM_PROMPT
from app.services.inquiry.text import plain_text


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        (
            "**브루밍 치즈케이크** 및 **시즌 과일 타르트**는",
            "브루밍 치즈케이크 및 시즌 과일 타르트는",
        ),
        ("__굵게__ 쓴 글", "굵게 쓴 글"),
        ("## 안내\n영업시간은 09:00~21:00", "안내\n영업시간은 09:00~21:00"),
        ("* 아메리카노 4,500원\n* 카페라떼 5,500원", "- 아메리카노 4,500원\n- 카페라떼 5,500원"),
        ("짝이 안 맞는 **기호", "짝이 안 맞는 기호"),
        ("아메리카노는 4,500원입니다.", "아메리카노는 4,500원입니다."),  # 일반 글은 그대로
        ("2*3=6", "2*3=6"),  # 문장 속 별표 하나는 그대로
    ],
)
def test_plain_text(raw, clean):
    assert plain_text(raw) == clean


def test_prompt_asks_for_plain_sentences():
    assert "마크다운 기호 없이" in SYSTEM_PROMPT
    # 프롬프트 노출 검사(E30)에 쓰는 문구는 그대로 남아 있어야 한다
    assert "반드시 아래 매장 정보" in SYSTEM_PROMPT and "도우미입니다" in SYSTEM_PROMPT


def test_prompt_tells_ai_to_answer_only_the_question():
    """질문과 상관없는 '[영업시간] [휴무일]' 양식을 늘어놓던 문제 (11/24 시연 중 발견)."""
    from datetime import time

    from app.adapters.ai.mock_adapter import MockAIClient
    from app.models.models import Inquiry, MenuItem, Store
    from app.services.inquiry.service import InquiryService

    store = Store(name="브루밍 카페", open_time=time(9), close_time=time(21), phone="02-000-0000")
    menus = [MenuItem(name="허니브레드", price=6500, on_sale=True, description="꿀과 버터")]
    prompt = InquiryService(MockAIClient()).build_prompt(
        store, menus, [], Inquiry(content="떡볶이도 판매하나요?")
    )
    assert prompt.index("떡볶이도 판매하나요?") < prompt.index("[작성 방법]")
    assert "물어본 것에만 답하고" in prompt and "현재 판매하지 않는 메뉴" in prompt
    assert "허니브레드: 6,500원 (꿀과 버터)" in prompt
