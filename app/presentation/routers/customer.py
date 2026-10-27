"""고객 화면 라우터."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.presentation.templating import templates

router = APIRouter(tags=["customer"])


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    """고객 첫 화면. TODO(한재형): 예약 신청(F-02), TODO(정회성): 문의 등록(F-03)."""
    return templates.TemplateResponse(request, "customer/index.html", {})
