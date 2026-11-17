"""고객 화면 라우터."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.presentation.templating import templates
from app.services.store.service import StoreService

router = APIRouter(tags=["customer"])

SessionDep = Annotated[Session, Depends(get_session)]

STORE_ID = 1


@router.get("/", response_class=HTMLResponse)
def home(request: Request, session: SessionDep) -> HTMLResponse:
    """고객 첫 화면. 매장 정보·메뉴·FAQ와 예약(F-02)·문의(F-03) 화면으로 안내한다."""
    svc = StoreService(session)
    try:
        store = svc.get_store(STORE_ID)
        menus = svc.list_menus(STORE_ID)
        faqs = svc.list_faqs(STORE_ID)
    except ValueError:
        store, menus, faqs = None, [], []
    return templates.TemplateResponse(
        request, "customer/index.html",
        {"store": store, "menus": menus, "faqs": faqs},
    )
