"""고객 화면 라우터."""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.models.models import MenuItem, Store
from app.presentation.templating import templates
from app.services.store.menu_photo import menu_photo
from app.services.store.service import StoreService

router = APIRouter(tags=["customer"])

SessionDep = Annotated[Session, Depends(get_session)]

STORE_ID = 1
WEEKDAYS = "월화수목금토일"
FAQ_PREVIEW = 5  # 첫 화면에 펼쳐 두는 FAQ 수. 나머지는 '더보기'로 연다.
# 메뉴 이름에 이 단어가 있으면 디저트로 나눈다. 메뉴에 분류 칸이 없어 이름으로 판단한다.
DESSERT_WORDS = (
    "케이크",
    "크루아상",
    "브라우니",
    "쿠키",
    "타르트",
    "마카롱",
    "스콘",
    "와플",
    "빵",
    "머핀",
)


# 메뉴 이름 → 아이콘. 사진 대신 이모지를 써서 저작권·업로드 걱정이 없다. 앞에 있는 단어가 우선이다.
MENU_ICONS = (
    ("딸기", "🍓"),
    ("자몽", "🍊"),
    ("레몬", "🍋"),
    ("유자", "🍋"),
    ("말차", "🍵"),
    ("녹차", "🍵"),
    ("밤", "🌰"),
    ("초코", "🍫"),
    ("브라우니", "🍫"),
    ("크루아상", "🥐"),
    ("케이크", "🍰"),
    ("쿠키", "🍪"),
    ("와플", "🧇"),
    ("머핀", "🧁"),
    ("타르트", "🥧"),
    ("마카롱", "🍬"),
    ("빵", "🍞"),
    ("에이드", "🥤"),
    ("스무디", "🥤"),
    ("티", "🍵"),
)


templates.env.globals["menu_photo"] = menu_photo


def menu_icon(name: str) -> str:
    """메뉴 이름에 맞는 이모지. 맞는 게 없으면 디저트는 🍰, 음료는 ☕."""
    for word, icon in MENU_ICONS:
        if word in name:
            return icon
    return "🍰" if any(w in name for w in DESSERT_WORDS) else "☕"


templates.env.globals["menu_icon"] = menu_icon


@dataclass(frozen=True)
class OpenStatus:
    label: str
    badge: str  # Bootstrap 배지 클래스


def open_status(store: Store, now: datetime) -> OpenStatus:
    """지금 영업 중인지 알려 준다. 휴무일 → 영업 전 → 영업 중 → 영업 종료 순으로 판단한다."""
    day = WEEKDAYS[now.weekday()]
    closed = {d.strip() for d in (store.closed_days or "").split(",") if d.strip()}
    if day in closed:
        return OpenStatus(f"오늘 휴무 ({day})", "text-bg-secondary")
    if now.time() < store.open_time:
        return OpenStatus(f"영업 전 · {store.open_time:%H:%M} 오픈", "text-bg-warning")
    if now.time() < store.close_time:
        return OpenStatus(f"영업 중 · {store.close_time:%H:%M}까지", "text-bg-success")
    return OpenStatus("오늘 영업 종료", "text-bg-secondary")


def split_menus(menus: list[MenuItem]) -> tuple[list[MenuItem], list[MenuItem]]:
    """(음료, 디저트)로 나눈다."""
    desserts = [m for m in menus if any(w in m.name for w in DESSERT_WORDS)]
    drinks = [m for m in menus if m not in desserts]
    return drinks, desserts


@router.get("/", response_class=HTMLResponse)
def home(request: Request, session: SessionDep) -> HTMLResponse:
    """고객 첫 화면. 매장 정보 바로 아래에 예약(F-02)·문의(F-03) 버튼을 둔다."""
    svc = StoreService(session)
    try:
        store = svc.get_store(STORE_ID)
        menus = svc.list_menus(STORE_ID)
        faqs = svc.list_faqs(STORE_ID)
    except ValueError:
        store, menus, faqs = None, [], []
    drinks, desserts = split_menus(menus)
    return templates.TemplateResponse(
        request,
        "customer/index.html",
        {
            "store": store,
            "status": open_status(store, datetime.now()) if store else None,
            "menu_groups": [("음료", drinks), ("디저트", desserts)],
            "faqs": faqs,
            "faq_preview": FAQ_PREVIEW,
        },
    )
