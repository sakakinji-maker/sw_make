"""문의 답변 초안 서비스 테스트 (F-03-2, F-03-5). DB 없이 객체만으로 확인한다."""

from datetime import time

from app.adapters.ai.mock_adapter import MockAIClient
from app.models.models import FAQ, Inquiry, MenuItem, Store
from app.services.inquiry.service import InquiryService

store = Store(
    name="온기 카페",
    open_time=time(9, 0),
    close_time=time(21, 0),
    closed_days="월",
    phone="02-000-0000",
)
menus = [MenuItem(name="아메리카노", price=4500, on_sale=True)]
faqs = [FAQ(question="주차 되나요?", answer="2대 가능합니다.")]
inquiry = Inquiry(content="아메리카노 얼마예요?")


def test_draft_with_wrong_price_warns():
    ai = MockAIClient(fixed_response="아메리카노는 3,000원입니다.")
    result = InquiryService(ai).draft_answer(store, menus, faqs, inquiry)
    assert result.draft and len(result.mismatches) == 1


def test_prompt_contains_store_info():
    ai = MockAIClient()
    InquiryService(ai).draft_answer(store, menus, faqs, inquiry)
    assert "4,500원" in ai.last_prompt and "09:00" in ai.last_prompt


def test_ai_failure_returns_error():
    result = InquiryService(MockAIClient(fail=True)).draft_answer(store, menus, faqs, inquiry)
    assert result.draft is None and result.error
