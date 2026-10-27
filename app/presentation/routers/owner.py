"""점주 화면 라우터."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.presentation.templating import templates

router = APIRouter(prefix="/owner", tags=["owner"])


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    """점주 대시보드 (F-05). TODO(전지호): 오늘 예약·미응답 문의·최근 콘텐츠 조회."""
    return templates.TemplateResponse(
        request, "owner/dashboard.html", {"reservations": [], "unanswered": 0, "contents": []}
    )
