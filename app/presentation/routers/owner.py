"""점주 화면 라우터."""

from datetime import time
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.adapters.ai import get_ai_client
from app.db.database import get_session
from app.models.models import MenuItem, Store
from app.presentation.templating import templates
from app.services.dashboard.service import DashboardService
from app.services.marketing.service import ContentResult, MarketingService
from app.services.marketing.strategies import available_channels
from app.services.store.menu_photo import MenuPhotoError, delete_menu_photo, save_menu_photo
from app.services.store.service import StoreService

CHANNEL_LABELS = {
    "instagram": "인스타그램",
    "blog": "블로그",
    "sms": "문자(SMS)",
}

router = APIRouter(prefix="/owner", tags=["owner"])

# ── 의존성 헬퍼 ───────────────────────────────────────────

SessionDep = Annotated[Session, Depends(get_session)]


def get_store_service(session: SessionDep) -> StoreService:
    return StoreService(session)


StoreSvcDep = Annotated[StoreService, Depends(get_store_service)]


# ── 대시보드 ──────────────────────────────────────────────

STORE_ID = 1  # 단일 매장 시스템 (추후 인증 연동 시 세션에서 추출)


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request, session: SessionDep) -> HTMLResponse:
    """점주 대시보드에 예약·문의·홍보 콘텐츠 현황을 전달한다 (F-05)."""
    data = DashboardService(session).get_dashboard(STORE_ID)
    context = {
        "today": data.today,
        "reservations": data.reservations,
        "status_counts": data.status_counts,
        "unanswered": data.unanswered,
        "contents": data.contents,
        "contents_count": data.contents_count,
        "today_reservations": data.today_reservations,
        "today_counts": data.today_counts,
        "pending": data.pending,
        "week": data.week,
        "open_time": data.open_time,
        "close_time": data.close_time,
        "channel_labels": CHANNEL_LABELS,
    }
    return templates.TemplateResponse(request, "owner/dashboard.html", context)


# ── HTML 화면 라우터 (F-01) ───────────────────────────────


@router.get("/store", response_class=HTMLResponse)
def store_page(request: Request, svc: StoreSvcDep, photo_error: str = "") -> HTMLResponse:
    """매장·메뉴·FAQ 관리 화면. photo_error: 메뉴 사진을 못 올렸을 때 안내."""
    try:
        store = svc.get_store(STORE_ID)
        menus = svc.list_menus(STORE_ID)
        faqs = svc.list_faqs(STORE_ID)
    except ValueError:
        store, menus, faqs = None, [], []
    return templates.TemplateResponse(
        request,
        "owner/store.html",
        {"store": store, "menus": menus, "faqs": faqs, "photo_error": photo_error[:100]},
    )


@router.post("/store")
def update_store_form(
    svc: StoreSvcDep,
    name: str = Form(""),
    category: str = Form(""),
    address: str = Form(""),
    open_time: str = Form(""),
    close_time: str = Form(""),
    closed_days: str = Form(""),
    phone: str = Form(""),
    capacity_per_hour: int = Form(0),
):
    """매장 정보 수정 (HTML 폼)."""
    kwargs = {}
    if name:
        kwargs["name"] = name
    if category:
        kwargs["category"] = category
    if address:
        kwargs["address"] = address
    if open_time:
        kwargs["open_time"] = time.fromisoformat(open_time)
    if close_time:
        kwargs["close_time"] = time.fromisoformat(close_time)
    kwargs["closed_days"] = closed_days or None
    if phone:
        kwargs["phone"] = phone
    if capacity_per_hour:
        kwargs["capacity_per_hour"] = capacity_per_hour
    try:
        svc.update_store(STORE_ID, **kwargs)
    except ValueError:
        pass
    return RedirectResponse(url="/owner/store", status_code=status.HTTP_303_SEE_OTHER)


MENU_TAB = "/owner/store#tab-menu"
PhotoFile = Annotated[UploadFile | None, File()]  # 메뉴 사진 (선택)


def _menu_tab(photo_error: str = "") -> RedirectResponse:
    url = f"/owner/store?photo_error={quote(photo_error)}#tab-menu" if photo_error else MENU_TAB
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


async def _save_photo(name: str, photo: UploadFile | None) -> str:
    """사진이 있으면 저장한다. 실패하면 안내 문구를, 성공하거나 사진이 없으면 ''를 돌려준다."""
    if photo is None or not photo.filename:
        return ""
    try:
        save_menu_photo(name, photo.filename, await photo.read())
    except MenuPhotoError as e:
        return str(e)
    return ""


@router.post("/menus")
async def add_menu_form(
    svc: StoreSvcDep,
    name: str = Form(...),
    price: int = Form(...),
    description: str = Form(""),
    photo: PhotoFile = None,
):
    """메뉴 추가 (HTML 폼). 사진은 선택."""
    try:
        menu = svc.add_menu(STORE_ID, name, price, description, on_sale=True)
    except ValueError:
        return _menu_tab()
    return _menu_tab(await _save_photo(menu.name, photo))


@router.post("/menus/{menu_id}/photo")
async def upload_menu_photo(menu_id: int, svc: StoreSvcDep, photo: PhotoFile = None):
    """메뉴 사진 올리기·바꾸기."""
    menu = _owned_menu(svc, menu_id)
    if photo is None or not photo.filename:
        return _menu_tab("사진을 골라 주세요.")
    return _menu_tab(await _save_photo(menu.name, photo))


@router.post("/menus/{menu_id}/photo/delete")
def remove_menu_photo(menu_id: int, svc: StoreSvcDep):
    """메뉴 사진 지우기 (손님 화면은 이모지로 돌아간다)."""
    delete_menu_photo(_owned_menu(svc, menu_id).name)
    return _menu_tab()


@router.post("/menus/{menu_id}/delete")
def delete_menu_form(menu_id: int, svc: StoreSvcDep):
    """메뉴 삭제 (HTML 폼). 사진도 같이 지운다."""
    try:
        menu = _owned_menu(svc, menu_id)
        svc.delete_menu(STORE_ID, menu_id)
        delete_menu_photo(menu.name)
    except (ValueError, HTTPException):
        pass
    return _menu_tab()


def _owned_menu(svc: StoreService, menu_id: int) -> MenuItem:
    menu = next((m for m in svc.list_menus(STORE_ID) if m.id == menu_id), None)
    if menu is None:
        raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다")
    return menu


@router.post("/faqs")
def add_faq_form(
    svc: StoreSvcDep,
    question: str = Form(...),
    answer: str = Form(...),
):
    """FAQ 추가 (HTML 폼)."""
    try:
        svc.add_faq(STORE_ID, question, answer)
    except ValueError:
        pass
    return RedirectResponse(url="/owner/store#tab-faq", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/faqs/{faq_id}/delete")
def delete_faq_form(faq_id: int, svc: StoreSvcDep):
    """FAQ 삭제 (HTML 폼)."""
    try:
        svc.delete_faq(STORE_ID, faq_id)
    except ValueError:
        pass
    return RedirectResponse(url="/owner/store#tab-faq", status_code=status.HTTP_303_SEE_OTHER)


# ── 홍보 문구 화면 (F-04) ────────────────────────────────


MAX_TARGET_LENGTH = 30  # 홍보 대상 직접 입력 길이
MAX_KEYWORD_LENGTH = 20  # 직접 입력 키워드 한 개 길이


@router.get("/marketing", response_class=HTMLResponse)
def marketing_page(request: Request, session: SessionDep) -> HTMLResponse:
    """홍보 문구 생성 화면."""
    service = MarketingService(get_ai_client())
    contents = service.list_saved(session=session, store_id=STORE_ID)
    return templates.TemplateResponse(
        request,
        "owner/marketing.html",
        {
            "channels": available_channels(),
            "channel_labels": CHANNEL_LABELS,
            "contents": contents,
            "result": None,
            "form": {},
        },
    )


@router.post("/marketing/generate", response_class=HTMLResponse)
def generate_marketing(
    request: Request,
    session: SessionDep,
    channel: str = Form(...),
    target: str = Form(""),
    target_custom: str = Form(""),
    keywords_raw: str = Form(""),
    keywords_custom: str = Form(""),
    extra_note: str = Form(""),
) -> HTMLResponse:
    """홍보 문구 생성 처리. 고른 키워드 + 직접 입력한 키워드(쉼표로 구분)를 함께 쓴다."""
    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
    for k in keywords_custom.replace("，", ",").split(","):
        if k.strip() and k.strip() not in keywords:
            keywords.append(k.strip()[:MAX_KEYWORD_LENGTH])
    store = session.get(Store, STORE_ID)
    menus = session.query(MenuItem).filter(MenuItem.store_id == STORE_ID).all()
    picked = target
    target = target_custom.strip()[:MAX_TARGET_LENGTH] or target  # 직접 입력이 있으면 그걸 쓴다

    service = MarketingService(get_ai_client())
    if not target.strip():
        result = ContentResult(text=None, violations=[], error="홍보 대상을 골라 주세요.")
    else:
        result = service.generate(
            channel=channel,
            target=target,
            keywords=keywords,
            store=store,
            menus=menus,
            extra_note=extra_note.strip(),
        )

    if not result.error:
        try:
            service.save(
                session=session,
                store_id=STORE_ID,
                channel=channel,
                target=target,
                keywords=keywords,
                result=result,
            )
        except ValueError:
            pass

    contents = service.list_saved(session=session, store_id=STORE_ID)
    return templates.TemplateResponse(
        request,
        "owner/marketing.html",
        {
            "channels": available_channels(),
            "channel_labels": CHANNEL_LABELS,
            "contents": contents,
            "result": result,
            "form": {
                "channel": channel,
                "target": picked,
                "target_custom": target_custom,
                "keywords_raw": keywords_raw,
                "keywords_custom": keywords_custom,
                "extra_note": extra_note,
            },
        },
    )


@router.post("/marketing/{content_id}/delete")
def delete_marketing(content_id: int, session: SessionDep):
    """홍보 문구 삭제."""
    service = MarketingService(get_ai_client())
    service.delete(session=session, content_id=content_id, store_id=STORE_ID)
    return RedirectResponse(url="/owner/marketing", status_code=status.HTTP_303_SEE_OTHER)


# ── Pydantic 스키마 (F-01) ────────────────────────────────


class StoreUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    address: str | None = None
    open_time: time | None = None
    close_time: time | None = None
    closed_days: str | None = None
    phone: str | None = None
    capacity_per_hour: int | None = None


class MenuCreate(BaseModel):
    name: str
    price: int
    description: str = ""
    on_sale: bool = True


class MenuUpdate(BaseModel):
    name: str | None = None
    price: int | None = None
    description: str | None = None
    on_sale: bool | None = None


class FAQCreate(BaseModel):
    question: str
    answer: str


class FAQUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None


# ── 매장 정보 엔드포인트 (F-01-1) ─────────────────────────


@router.get("/stores/{store_id}")
def get_store(store_id: int, svc: StoreSvcDep):
    """매장 정보 조회."""
    try:
        store = svc.get_store(store_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return {
        "id": store.id,
        "name": store.name,
        "category": store.category,
        "address": store.address,
        "open_time": str(store.open_time),
        "close_time": str(store.close_time),
        "closed_days": store.closed_days,
        "phone": store.phone,
        "capacity_per_hour": store.capacity_per_hour,
    }


@router.patch("/stores/{store_id}")
def update_store(store_id: int, body: StoreUpdate, svc: StoreSvcDep):
    """매장 정보 수정."""
    try:
        store = svc.update_store(store_id, **body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return {"id": store.id, "name": store.name}


# ── 메뉴 엔드포인트 (F-01-2) ──────────────────────────────


@router.get("/stores/{store_id}/menus")
def list_menus(store_id: int, svc: StoreSvcDep):
    """메뉴 목록 조회."""
    try:
        items = svc.list_menus(store_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return [
        {
            "id": m.id,
            "name": m.name,
            "price": m.price,
            "description": m.description,
            "on_sale": m.on_sale,
        }
        for m in items
    ]


@router.post("/stores/{store_id}/menus", status_code=status.HTTP_201_CREATED)
def add_menu(store_id: int, body: MenuCreate, svc: StoreSvcDep):
    """메뉴 추가."""
    try:
        item = svc.add_menu(store_id, body.name, body.price, body.description, body.on_sale)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)) from e
    return {"id": item.id, "name": item.name, "price": item.price}


@router.patch("/stores/{store_id}/menus/{menu_id}")
def update_menu(store_id: int, menu_id: int, body: MenuUpdate, svc: StoreSvcDep):
    """메뉴 수정."""
    try:
        item = svc.update_menu(store_id, menu_id, **body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return {"id": item.id, "name": item.name, "price": item.price, "on_sale": item.on_sale}


@router.delete("/stores/{store_id}/menus/{menu_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu(store_id: int, menu_id: int, svc: StoreSvcDep):
    """메뉴 삭제."""
    try:
        svc.delete_menu(store_id, menu_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


# ── FAQ 엔드포인트 (F-01-3) ───────────────────────────────


@router.get("/stores/{store_id}/faqs")
def list_faqs(store_id: int, svc: StoreSvcDep):
    """FAQ 목록 조회."""
    try:
        faqs = svc.list_faqs(store_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return [{"id": f.id, "question": f.question, "answer": f.answer} for f in faqs]


@router.post("/stores/{store_id}/faqs", status_code=status.HTTP_201_CREATED)
def add_faq(store_id: int, body: FAQCreate, svc: StoreSvcDep):
    """FAQ 추가."""
    try:
        faq = svc.add_faq(store_id, body.question, body.answer)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)) from e
    return {"id": faq.id, "question": faq.question}


@router.patch("/stores/{store_id}/faqs/{faq_id}")
def update_faq(store_id: int, faq_id: int, body: FAQUpdate, svc: StoreSvcDep):
    """FAQ 수정."""
    try:
        faq = svc.update_faq(store_id, faq_id, **body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return {"id": faq.id, "question": faq.question, "answer": faq.answer}


@router.delete("/stores/{store_id}/faqs/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_faq(store_id: int, faq_id: int, svc: StoreSvcDep):
    """FAQ 삭제."""
    try:
        svc.delete_faq(store_id, faq_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
