"""문의 답변 초안 생성. (F-03) AI는 초안만 만들고 확정은 점주가 한다."""

from dataclasses import dataclass

from app.adapters.ai import AIClient, AIClientError
from app.models.models import FAQ, Inquiry, MenuItem, Store
from app.services.inquiry.fact_checker import FactChecker, Mismatch

SYSTEM_PROMPT = (
    "당신은 소상공인 매장의 고객 문의 답변을 돕는 도우미입니다. "
    "반드시 아래 매장 정보·메뉴·FAQ만 근거로 답하세요. "
    "근거에 없는 내용은 '매장에 직접 문의해 주세요'라고 답하세요."
)


@dataclass
class DraftResult:
    draft: str | None
    mismatches: list[Mismatch]
    error: str | None = None  # AI 실패 시 안내 문구 (F-03-5)


class InquiryService:
    def __init__(self, ai_client: AIClient) -> None:
        self.ai = ai_client

    def build_prompt(
        self, store: Store, menus: list[MenuItem], faqs: list[FAQ], inquiry: Inquiry
    ) -> str:
        menu_lines = "\n".join(f"- {m.name}: {m.price:,}원" for m in menus if m.on_sale)
        faq_lines = "\n".join(f"- Q: {f.question} / A: {f.answer}" for f in faqs)
        return (
            f"[매장] {store.name}, 영업시간 {store.open_time:%H:%M}~{store.close_time:%H:%M}, "
            f"휴무일 {store.closed_days or '없음'}, 연락처 {store.phone}\n"
            f"[메뉴]\n{menu_lines}\n[FAQ]\n{faq_lines}\n"
            f"[고객 문의]\n{inquiry.content}"
        )

    def draft_answer(
        self, store: Store, menus: list[MenuItem], faqs: list[FAQ], inquiry: Inquiry
    ) -> DraftResult:
        prompt = self.build_prompt(store, menus, faqs, inquiry)
        try:
            draft = self.ai.generate(prompt, system=SYSTEM_PROMPT)
        except AIClientError as e:
            return DraftResult(draft=None, mismatches=[], error=f"AI 초안 생성 실패: {e}")

        checker = FactChecker(
            menu_prices={m.name: m.price for m in menus},
            open_time=store.open_time,
            close_time=store.close_time,
        )
        return DraftResult(draft=draft, mismatches=checker.check(draft))

    # TODO(정회성): 초안·최종 답변 저장, 상태 '답변완료' 처리 (F-03-4)
