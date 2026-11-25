# AI-assisted (Claude) — 정회성 검토 완료
"""문의 접수와 AI 답변 초안 생성. (F-03) AI는 초안만 만들고 확정은 점주가 한다."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime

from app.adapters.ai import AIClient, AIClientError
from app.models.models import FAQ, Inquiry, MenuItem, Store
from app.repositories.inquiry_repository import InquiryRepository
from app.services.foreign_text import foreign_chars, generate_korean
from app.services.inquiry.fact_checker import FactChecker, Mismatch
from app.services.inquiry.schemas import AnswerSubmit, InquiryCreate, InquiryLookup
from app.services.inquiry.text import plain_text
from app.services.notification import Notifier, NullNotifier
from app.services.reservation.service import same_name

SYSTEM_PROMPT = (
    "당신은 소상공인 매장의 고객 문의 답변을 돕는 도우미입니다. "
    "반드시 아래 매장 정보·메뉴·FAQ만 근거로 답하세요. "
    "근거에 없는 내용은 '매장에 직접 문의해 주세요'라고 답하세요. "
    "답변은 손님에게 그대로 보이므로 **, # 같은 마크다운 기호 없이 평범한 문장으로 쓰세요."
)


# 지시 없이 정보만 주면 AI가 질문과 상관없이 '[영업시간] [휴무일]' 같은 안내문을 늘어놓는다.
# 그래서 무엇을 어떻게 답할지 마지막에 분명히 적는다.
ANSWER_RULES = (
    "[작성 방법]\n"
    "- 위 [고객 문의]에 대한 답변만 2~4문장으로 쓰세요.\n"
    "- 손님이 물어본 것에만 답하고, 묻지 않은 영업시간·휴무일 등을 나열하지 마세요.\n"
    "- 물어본 메뉴가 [메뉴]에 없으면 '현재 판매하지 않는 메뉴'라고 안내하고,\n"
    "  비슷한 메뉴가 있으면 하나만 추천하세요.\n"
    "- [영업시간] 같은 대괄호 제목이나 빈칸 양식을 쓰지 말고, '안녕하세요, (매장 이름)입니다.'로\n"
    "  시작하는 자연스러운 존댓말 문장으로 쓰세요.\n"
    "- 한국어로만 쓰세요."
)


class StoreNotFoundError(Exception):
    """존재하지 않는 매장에 문의하려 할 때."""


class InquiryNotFoundError(Exception):
    """존재하지 않는 문의를 찾을 때."""


ANSWERED = "답변완료"


@dataclass
class DraftResult:
    draft: str | None
    mismatches: list[Mismatch]
    error: str | None = None  # AI 실패 시 안내 문구 (F-03-5)


@dataclass(frozen=True)
class CustomerView:
    """고객 화면에 보여 줄 문의 한 건. 답변은 점주가 확정한 것만 담는다. (F-03-6)"""

    id: int
    store_name: str
    received_at: datetime
    content: str
    answer: str | None

    @classmethod
    def of(cls, inquiry: Inquiry) -> "CustomerView":
        answered = inquiry.status == ANSWERED and bool(inquiry.final_answer)
        return cls(
            id=inquiry.id,
            store_name=inquiry.store.name,
            received_at=inquiry.received_at,
            content=inquiry.content,
            answer=inquiry.final_answer if answered else None,
        )


class InquiryService:
    def __init__(
        self,
        ai_client: AIClient,
        repository: InquiryRepository | None = None,
        notifier: Notifier | None = None,
    ) -> None:
        self.ai = ai_client
        self.repo = repository
        self.notifier = notifier or NullNotifier()  # 문자 알림. 라우터가 실제 알림기를 넣는다.

    # ----- F-03-1 문의 등록 -----
    def register(self, data: InquiryCreate) -> Inquiry:
        if self.repo.get_store(data.store_id) is None:
            raise StoreNotFoundError(f"매장을 찾을 수 없습니다 (id={data.store_id})")
        customer = self.repo.find_or_create_customer(data.name, data.phone)
        inquiry = Inquiry(store_id=data.store_id, customer=customer, content=data.content)
        saved = self.repo.add(inquiry)
        self.notifier.inquiry_received(saved)
        return saved

    # ----- F-03-6 고객 답변 확인 -----
    # AI-assisted (Claude) — 정회성 검토 완료
    def find_for_customer(self, data: InquiryLookup) -> list[CustomerView]:
        """고객 본인의 문의와 '점주가 확정한' 답변만 돌려준다.

        AI 초안(ai_draft)은 점주 검토 전이라 사실 오류가 있을 수 있어 고객에게 보이지 않는다.
        화면이 실수로 초안을 꺼내 쓰지 않도록 Inquiry 대신 필요한 값만 담은 객체를 넘긴다.
        """
        found = self.repo.list_by_phone(data.digits)
        if data.name is not None:  # 이름도 맞는 문의만 (띄어쓰기 무시)
            found = [i for i in found if same_name(i.customer.name, data.name)]
        return [CustomerView.of(i) for i in found]

    # ----- F-03-2, F-03-3 AI 초안 생성과 DB 대조 -----
    def generate_draft(self, inquiry_id: int) -> DraftResult:
        """초안을 만들어 AI 원본(ai_draft)과 대조 결과(check_result)를 저장한다."""
        inquiry = self.get(inquiry_id)
        store = inquiry.store
        result = self.draft_answer(store, store.menu_items, store.faqs, inquiry)
        if result.draft is not None:
            inquiry.ai_draft = result.draft
            inquiry.check_result = json.dumps(
                [asdict(m) for m in result.mismatches], ensure_ascii=False
            )
            self.repo.save()
        return result

    def get(self, inquiry_id: int) -> Inquiry:
        inquiry = self.repo.get(inquiry_id)
        if inquiry is None:
            raise InquiryNotFoundError(f"문의를 찾을 수 없습니다 (id={inquiry_id})")
        return inquiry

    @staticmethod
    def mismatches_of(inquiry: Inquiry) -> list[dict[str, str]]:
        """저장된 대조 결과를 화면용으로 꺼낸다."""
        return json.loads(inquiry.check_result) if inquiry.check_result else []

    # ----- 프롬프트 구성과 초안 생성 (DB 없이도 동작) -----
    def build_prompt(
        self, store: Store, menus: list[MenuItem], faqs: list[FAQ], inquiry: Inquiry
    ) -> str:
        # 메뉴 설명도 넘긴다 (13주차 실험 E06: 설명에 있는 내용을 AI가 몰라서 못 답함)
        menu_lines = "\n".join(
            f"- {m.name}: {m.price:,}원" + (f" ({m.description})" if m.description else "")
            for m in menus
            if m.on_sale
        )
        faq_lines = "\n".join(f"- Q: {f.question} / A: {f.answer}" for f in faqs)
        return (
            f"[매장] {store.name}, 영업시간 {store.open_time:%H:%M}~{store.close_time:%H:%M}, "
            f"휴무일 {store.closed_days or '없음'}, 연락처 {store.phone}\n"
            f"[메뉴]\n{menu_lines}\n[FAQ]\n{faq_lines}\n"
            f"[고객 문의]\n{inquiry.content}\n\n"
            f"{ANSWER_RULES}"
        )

    def draft_answer(
        self, store: Store, menus: list[MenuItem], faqs: list[FAQ], inquiry: Inquiry
    ) -> DraftResult:
        prompt = self.build_prompt(store, menus, faqs, inquiry)
        try:
            # 중국어·일본어 문자가 섞이면 자동으로 다시 생성한다 (최대 2번 더)
            draft = generate_korean(lambda: self.ai.generate(prompt, system=SYSTEM_PROMPT))
        except AIClientError as e:
            return DraftResult(draft=None, mismatches=[], error=f"AI 초안 생성 실패: {e}")

        checker = self._checker(store, menus)
        mismatches = checker.check(draft, quoted=inquiry.content)
        if found := foreign_chars(draft):  # 다시 생성해도 섞여 있으면 점주에게 경고
            mismatches.append(
                Mismatch(kind="외국어", found=found, message="중국어·일본어 문자가 섞여 있습니다")
            )
        return DraftResult(draft=draft, mismatches=mismatches)

    # ----- F-03-4 점주 확정(발송 완료), F-03-5 직접 작성 -----
    # AI-assisted (Claude) — 정회성 검토 완료
    def finalize(self, inquiry_id: int, data: AnswerSubmit) -> Inquiry:
        """점주가 확정한 답변을 저장하고 '답변완료'로 바꾼다.

        AI 초안이 없어도(AI 실패, F-03-5) 점주가 직접 쓴 답변으로 확정할 수 있다.
        AI 원본(ai_draft)은 덮어쓰지 않는다. 검증 보고서에서 원본과 최종본을 비교하기 때문이다.
        이미 답변완료여도 고쳐서 다시 보낼 수 있다. 내용이 바뀌었으면 손님에게 '답변 수정' 문자를,
        그대로면 문자를 또 보내지 않는다(같은 문자 중복 방지).
        """
        inquiry = self.get(inquiry_id)
        first_answer = inquiry.status != ANSWERED
        new_answer = plain_text(data.answer)
        changed = new_answer != inquiry.final_answer
        inquiry.final_answer = new_answer
        inquiry.status = ANSWERED
        self.repo.save()
        if first_answer:
            self.notifier.inquiry_answered(inquiry)
        elif changed:
            self.notifier.inquiry_answer_updated(inquiry)
        return inquiry

    def check_answer(self, inquiry: Inquiry, text: str) -> list[Mismatch]:
        """점주가 고친 최종 답변도 같은 기준으로 DB와 대조한다. (발송 전 마지막 확인)"""
        store = inquiry.store
        return self._checker(store, store.menu_items).check(text, quoted=inquiry.content)

    @staticmethod
    def _checker(store: Store, menus: list[MenuItem]) -> FactChecker:
        return FactChecker(
            menu_prices={m.name: m.price for m in menus},
            open_time=store.open_time,
            close_time=store.close_time,
            closed_days=store.closed_days,
        )
