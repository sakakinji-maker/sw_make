# AI-assisted (Claude) — 정회성 검토 완료
"""문의 화면 라우터 (F-03). 고객: 문의 등록 / 점주: 문의함, AI 초안 생성, 답변 확정.

라우터는 입력을 받아 서비스에 넘기고 화면만 고른다. 로직과 SQL은 쓰지 않는다. (CLAUDE.md 3절)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.adapters.ai import AIClient, AIClientError, get_ai_client
from app.adapters.ai.mock_adapter import MockAIClient
from app.db.database import get_session
from app.models.models import Inquiry
from app.presentation.templating import templates
from app.repositories.inquiry_repository import InquiryRepository
from app.services.inquiry.schemas import (
    MAX_ANSWER_LENGTH,
    MAX_CONTENT_LENGTH,
    AnswerSubmit,
    InquiryCreate,
    InquiryLookup,
    korean_errors,
)
from app.services.inquiry.service import (
    InquiryNotFoundError,
    InquiryService,
    StoreNotFoundError,
)
from app.services.notification import Notifier, get_notifier

router = APIRouter(tags=["inquiry"])


class _MisconfiguredAI(MockAIClient):
    """설정 오류(.env)를 F-03-5의 'AI 실패' 흐름으로 보여주기 위한 대체 클라이언트."""

    def __init__(self, reason: str) -> None:
        super().__init__(fail=True)
        self.reason = reason

    def generate(self, prompt: str, system: str | None = None) -> str:
        raise AIClientError(self.reason)


def get_ai() -> AIClient:
    try:
        return get_ai_client()
    except AIClientError as e:
        return _MisconfiguredAI(str(e))


def get_service(
    session: Annotated[Session, Depends(get_session)],
    ai: Annotated[AIClient, Depends(get_ai)],
    notifier: Annotated[Notifier, Depends(get_notifier)],
) -> InquiryService:
    return InquiryService(ai, InquiryRepository(session), notifier=notifier)


ServiceDep = Annotated[InquiryService, Depends(get_service)]


# ---------- 고객 화면 (F-03-1) ----------


@router.get("/inquiries/new", response_class=HTMLResponse)
def inquiry_form(request: Request, service: ServiceDep) -> HTMLResponse:
    return _render_form(request, service, form={}, errors=[])


@router.post("/inquiries", response_class=HTMLResponse)
def submit_inquiry(
    request: Request,
    store_id: Annotated[int, Form()],
    service: ServiceDep,
    name: Annotated[str, Form()] = "",
    phone: Annotated[str, Form()] = "",
    content: Annotated[str, Form()] = "",
) -> HTMLResponse:
    form = {"store_id": store_id, "name": name, "phone": phone, "content": content}
    try:
        inquiry = service.register(InquiryCreate(**form))
    except ValidationError as e:
        return _render_form(request, service, form, korean_errors(e), status_code=400)
    except StoreNotFoundError:
        return _render_form(request, service, form, ["매장을 다시 선택해 주세요."], 400)
    return templates.TemplateResponse(request, "customer/inquiry_done.html", {"inquiry": inquiry})


def _render_form(
    request: Request,
    service: InquiryService,
    form: dict,
    errors: list[str],
    status_code: int = 200,
) -> HTMLResponse:
    context = {
        "stores": service.repo.list_stores(),
        "form": form,
        "errors": errors,
        "max_length": MAX_CONTENT_LENGTH,
    }
    return templates.TemplateResponse(
        request, "customer/inquiry_form.html", context, status_code=status_code
    )


# ---------- 고객 화면: 내 문의·답변 확인 (F-03-6) ----------
# AI-assisted (Claude) — 정회성 검토 완료


@router.get("/inquiries/lookup", response_class=HTMLResponse)
def inquiry_lookup_form(request: Request) -> HTMLResponse:
    return _render_lookup(request, phone=None, inquiries=[])


@router.post("/inquiries/lookup", response_class=HTMLResponse)
def inquiry_lookup(
    request: Request, service: ServiceDep, phone: Annotated[str, Form()] = ""
) -> HTMLResponse:
    try:
        lookup = InquiryLookup(phone=phone)
    except ValidationError as e:
        return _render_lookup(request, phone, [], errors=korean_errors(e), status_code=400)
    return _render_lookup(request, lookup.phone, service.find_for_customer(lookup))


def _render_lookup(
    request: Request,
    phone: str | None,
    inquiries: list,
    errors: list[str] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    context = {"phone": phone, "inquiries": inquiries, "errors": errors or []}
    return templates.TemplateResponse(
        request, "customer/inquiry_lookup.html", context, status_code=status_code
    )


# ---------- 점주 화면 (F-03-2 ~ F-03-5) ----------


@router.get("/owner/inquiries", response_class=HTMLResponse)
def inquiry_list(
    request: Request,
    service: ServiceDep,
    store_id: int | None = None,
) -> HTMLResponse:
    stores = service.repo.list_stores()
    selected = next((s for s in stores if s.id == store_id), stores[0] if stores else None)
    inquiries = service.repo.list_by_store(selected.id) if selected else []
    context = {"stores": stores, "selected": selected, "inquiries": inquiries}
    return templates.TemplateResponse(request, "owner/inquiry_list.html", context)


@router.get("/owner/inquiries/{inquiry_id}", response_class=HTMLResponse)
def inquiry_detail(
    request: Request,
    inquiry_id: int,
    service: ServiceDep,
    ai_error: str | None = None,
    sent: str | None = None,
) -> HTMLResponse:
    inquiry = _get_or_404(service, inquiry_id)
    return _render_detail(request, service, inquiry, ai_error=bool(ai_error), sent=bool(sent))


@router.post("/owner/inquiries/{inquiry_id}/answer", response_class=HTMLResponse)
def submit_answer(
    request: Request,
    inquiry_id: int,
    service: ServiceDep,
    answer: Annotated[str, Form()] = "",
) -> Response:
    """점주가 수정·작성한 답변을 '발송 완료'로 확정한다. (F-03-4, F-03-5)"""
    inquiry = _get_or_404(service, inquiry_id)
    try:
        service.finalize(inquiry_id, AnswerSubmit(answer=answer))
    except ValidationError as e:
        return _render_detail(
            request, service, inquiry, errors=korean_errors(e), answer=answer, status_code=400
        )
    return RedirectResponse(f"/owner/inquiries/{inquiry_id}?sent=1", status_code=303)


def _get_or_404(service: InquiryService, inquiry_id: int) -> Inquiry:
    try:
        return service.get(inquiry_id)
    except InquiryNotFoundError as e:
        raise HTTPException(status_code=404, detail="문의를 찾을 수 없습니다") from e


def _render_detail(
    request: Request,
    service: InquiryService,
    inquiry: Inquiry,
    *,
    ai_error: bool = False,
    sent: bool = False,
    errors: list[str] | None = None,
    answer: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """입력칸에는 '방금 입력한 값 → 확정된 답변 → AI 초안 → 빈칸' 순으로 채운다."""
    final = inquiry.final_answer
    context = {
        "inquiry": inquiry,
        "mismatches": service.mismatches_of(inquiry),
        "final_mismatches": service.check_answer(inquiry, final) if final else [],
        "ai_error": ai_error,
        "sent": sent,
        "errors": errors or [],
        "answer": answer if answer is not None else (final or inquiry.ai_draft or ""),
        "max_answer_length": MAX_ANSWER_LENGTH,
    }
    return templates.TemplateResponse(
        request, "owner/inquiry_detail.html", context, status_code=status_code
    )


@router.post("/owner/inquiries/{inquiry_id}/draft")
def create_draft(inquiry_id: int, service: ServiceDep) -> RedirectResponse:
    """초안 생성 후 상세 화면으로 돌아간다. 새로고침해도 다시 생성되지 않게 리다이렉트한다."""
    _get_or_404(service, inquiry_id)
    result = service.generate_draft(inquiry_id)
    url = f"/owner/inquiries/{inquiry_id}"
    if result.error:
        url += "?ai_error=1"
    return RedirectResponse(url, status_code=303)
