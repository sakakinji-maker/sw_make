# AI-assisted (Claude) — 정회성 검토 완료
"""예약 화면 라우터 (F-02). 고객: 신청·조회·변경·취소 / 점주: 예약 처리, 고객 이력.

라우터는 입력을 받아 서비스에 넘기고 화면만 고른다. 로직과 SQL은 쓰지 않는다. (CLAUDE.md 3절)
연락처는 개인정보라 URL에 남지 않도록 조회·변경·취소는 POST로 받는다.
"""

from datetime import date, datetime, timedelta
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.models.models import Reservation, Store
from app.presentation.templating import templates
from app.services.notification import Notifier, get_notifier
from app.services.phone import normalize_phone
from app.services.reservation.schemas import (
    MAX_PARTY_SIZE,
    ReservationCreate,
    ReservationSlot,
    korean_errors,
)
from app.services.reservation.service import (
    CANCEL_REASONS,
    MAX_NOTE_LENGTH,
    MAX_REASON_LENGTH,
    OWNER_ACTIONS,
    ReservationNotFoundError,
    ReservationRejectedError,
    ReservationService,
    StoreNotFoundError,
)
from app.services.reservation.states import InvalidTransitionError, ReservationStatus, state_of

router = APIRouter(tags=["reservation"])

ACTION_LABELS = {
    "confirm": "확정",
    "visit": "방문완료",
    "no_show": "노쇼",
    "cancel": "취소",
    "change": "변경",
}
STATUS_BADGES = {
    "요청": "text-bg-warning",
    "확정": "text-bg-primary",
    "방문완료": "text-bg-success",
    "취소": "text-bg-secondary",
    "노쇼": "text-bg-danger",
}


def get_service(
    session: Annotated[Session, Depends(get_session)],
    notifier: Annotated[Notifier, Depends(get_notifier)],
) -> ReservationService:
    return ReservationService(session, notifier=notifier)


ServiceDep = Annotated[ReservationService, Depends(get_service)]
FormStr = Annotated[str, Form()]


def _render(request: Request, name: str, context: dict, status_code: int = 200) -> HTMLResponse:
    base = {"badges": STATUS_BADGES, "labels": ACTION_LABELS, "max_party": MAX_PARTY_SIZE}
    return templates.TemplateResponse(request, name, base | context, status_code=status_code)


JS_WEEKDAYS = "일월화수목금토"  # 자바스크립트 Date.getDay() 순서
SLOT_MINUTES = 30


def time_slots(store: Store) -> list[str]:
    """영업시간 안에서 30분 간격으로 고를 수 있는 시각. 마감 시각 정각은 뺀다."""
    t = datetime.combine(date.min, store.open_time)
    end = datetime.combine(date.min, store.close_time)
    slots = []
    while t < end:
        slots.append(f"{t:%H:%M}")
        t += timedelta(minutes=SLOT_MINUTES)
    return slots


def _slot_context(service: ReservationService, store: Store) -> dict:
    """예약 신청·변경 화면의 날짜·시간 칸에 필요한 값."""
    closed = [d.strip() for d in (store.closed_days or "").split(",") if d.strip()]
    return {
        "store": store,
        "today": f"{service.now():%Y-%m-%d}",
        "slots": time_slots(store),
        "closed_js": [JS_WEEKDAYS.index(d) for d in closed if d in JS_WEEKDAYS],
    }


def _customer_actions(status: str) -> list[str]:
    """고객 화면에는 변경·취소 버튼만 보여준다. (F-02-3)"""
    return [a for a in state_of(status).allowed_actions() if a in ("change", "cancel")]


# ---------- 고객: 예약 신청 (F-02-1, F-02-2) ----------


@router.get("/reservations/new", response_class=HTMLResponse)
def reservation_form(request: Request, service: ServiceDep) -> HTMLResponse:
    return _render_form(request, service, form={}, errors=[])


@router.post("/reservations", response_class=HTMLResponse)
def submit_reservation(
    request: Request,
    service: ServiceDep,
    store_id: Annotated[int, Form()],
    name: FormStr = "",
    phone: FormStr = "",
    visit_date: FormStr = "",
    visit_time: FormStr = "",
    party_size: FormStr = "",
    request_text: Annotated[str, Form(alias="request")] = "",
) -> HTMLResponse:
    form = {
        "store_id": store_id,
        "name": name,
        "phone": phone,
        "visit_date": visit_date,
        "visit_time": visit_time,
        "party_size": party_size,
        "request": request_text,
    }
    try:
        reservation = service.create(ReservationCreate(**form))
    except ValidationError as e:
        return _render_form(request, service, form, korean_errors(e), 400)
    except StoreNotFoundError:
        return _render_form(request, service, form, ["매장을 다시 선택해 주세요."], 400)
    except ReservationRejectedError as e:
        return _render_form(request, service, form, [str(e)], 400)
    return _render(request, "customer/reservation_done.html", {"reservation": reservation})


def _render_form(
    request: Request,
    service: ReservationService,
    form: dict,
    errors: list[str],
    status_code: int = 200,
) -> HTMLResponse:
    stores = service.repo.list_stores()
    context = {"store": None, "form": form, "errors": errors}
    if stores:  # 단일 매장 시스템: 첫 매장으로 받는다
        context |= _slot_context(service, stores[0])
    return _render(request, "customer/reservation_form.html", context, status_code)


# ---------- 고객: 조회·변경·취소 (F-02-3) ----------


@router.get("/reservations/lookup", response_class=HTMLResponse)
def lookup_form(request: Request) -> HTMLResponse:
    return _render(request, "customer/reservation_lookup.html", {"phone": None, "name": ""})


@router.post("/reservations/lookup", response_class=HTMLResponse)
def lookup(
    request: Request, service: ServiceDep, phone: FormStr = "", name: FormStr = ""
) -> HTMLResponse:
    if not phone.strip() or not name.strip():
        error = "이름과 연락처를 모두 입력해 주세요."
        return _render_lookup(request, service, phone, name, error=error, status_code=400)
    return _render_lookup(request, service, phone, name)


def _render_lookup(
    request: Request,
    service: ReservationService,
    phone: str,
    name: str,
    message: str | None = None,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """번호와 이름이 모두 맞는 예약만 보여 준다. (번호만으로는 남의 예약이 보이지 않게)"""
    phone, name = normalize_phone(phone), name.strip()
    reservations = service.find_owned(phone, name) if phone and name else []
    now = service.now()
    active = (ReservationStatus.REQUESTED.value, ReservationStatus.CONFIRMED.value)
    # 다가오는 '요청'·'확정' 예약은 가까운 날짜부터, 나머지(지난·취소 등)는 최근 것부터
    upcoming = sorted(
        (r for r in reservations if r.reserved_at >= now and r.status in active),
        key=lambda r: r.reserved_at,
    )
    others = [r for r in reservations if r not in upcoming]
    context = {
        "phone": phone,
        "name": name,
        "searched": bool(phone and name and not error),
        "reservations": reservations,
        "upcoming": upcoming,
        "others": others,
        "actions": {r.id: _customer_actions(r.status) for r in reservations},
        "message": message,
        "error": error,
    }
    return _render(request, "customer/reservation_lookup.html", context, status_code)


@router.post("/reservations/{reservation_id}/edit", response_class=HTMLResponse)
def edit_form(
    request: Request,
    reservation_id: int,
    service: ServiceDep,
    phone: FormStr = "",
    name: FormStr = "",
) -> HTMLResponse:
    try:
        reservation = service.get_owned(reservation_id, phone, name)
    except ReservationNotFoundError as e:
        return _render_lookup(request, service, phone, name, error=str(e), status_code=404)
    form = {
        "visit_date": f"{reservation.reserved_at:%Y-%m-%d}",
        "visit_time": f"{reservation.reserved_at:%H:%M}",
        "party_size": reservation.party_size,
    }
    return _render_edit(request, service, reservation, phone, name, form, [])


@router.post("/reservations/{reservation_id}/change", response_class=HTMLResponse)
def change_reservation(
    request: Request,
    reservation_id: int,
    service: ServiceDep,
    phone: FormStr = "",
    name: FormStr = "",
    visit_date: FormStr = "",
    visit_time: FormStr = "",
    party_size: FormStr = "",
) -> HTMLResponse:
    form = {"visit_date": visit_date, "visit_time": visit_time, "party_size": party_size}
    try:
        reservation = service.get_owned(reservation_id, phone, name)
        service.change(reservation_id, phone, ReservationSlot(**form), name)
    except ReservationNotFoundError as e:
        return _render_lookup(request, service, phone, name, error=str(e), status_code=404)
    except ValidationError as e:
        return _render_edit(request, service, reservation, phone, name, form, korean_errors(e))
    except (ReservationRejectedError, InvalidTransitionError) as e:
        return _render_edit(request, service, reservation, phone, name, form, [str(e)])
    message = "예약을 변경했습니다. 매장에서 다시 확정하면 '확정'으로 바뀝니다."
    return _render_lookup(request, service, phone, name, message=message)


def _render_edit(
    request: Request,
    service: ReservationService,
    reservation: Reservation,
    phone: str,
    name: str,
    form: dict,
    errors: list[str],
) -> HTMLResponse:
    context = {
        "reservation": reservation,
        "phone": phone,
        "name": name,
        "form": form,
        "errors": errors,
    }
    context |= _slot_context(service, reservation.store)
    status_code = 400 if errors else 200
    return _render(request, "customer/reservation_edit.html", context, status_code)


@router.post("/reservations/{reservation_id}/cancel", response_class=HTMLResponse)
def cancel_reservation(
    request: Request,
    reservation_id: int,
    service: ServiceDep,
    phone: FormStr = "",
    name: FormStr = "",
) -> HTMLResponse:
    try:
        service.cancel_by_customer(reservation_id, phone, name)
    except ReservationNotFoundError as e:
        return _render_lookup(request, service, phone, name, error=str(e), status_code=404)
    except InvalidTransitionError as e:
        return _render_lookup(request, service, phone, name, error=str(e), status_code=400)
    return _render_lookup(request, service, phone, name, message="예약을 취소했습니다.")


# ---------- 점주: 예약 처리 (F-02-4, F-02-5) ----------


OWNER_VIEWS = {"today": "오늘", "upcoming": "다가오는 예약", "past": "지난 예약", "all": "전체"}


@router.get("/owner/reservations", response_class=HTMLResponse)
def owner_reservation_list(
    request: Request,
    service: ServiceDep,
    view: str = "upcoming",
    status: str | None = None,
    day: str = "",
) -> HTMLResponse:
    """기본은 오늘 이후 예약을 가까운 순으로. 지난 예약은 '지난 예약' 탭에서 최근 순으로 본다.

    day=YYYY-MM-DD 를 주면 그날 예약만 본다 (대시보드 7일 그래프의 막대를 누를 때).
    """
    stores = service.repo.list_stores()
    store = stores[0] if stores else None  # 단일 매장 시스템
    view = view if view in OWNER_VIEWS else "upcoming"
    status = status if status in STATUS_BADGES else None
    rows = service.list_for_store(store.id, status) if store else []
    today = service.now().date()
    try:
        picked = date.fromisoformat(day) if day else None
    except ValueError:
        picked = None
    if picked is not None:
        view = "day"
        rows = [r for r in rows if r.reserved_at.date() == picked]
    elif view == "today":
        rows = [r for r in rows if r.reserved_at.date() == today]
    elif view == "upcoming":
        rows = [r for r in rows if r.reserved_at.date() >= today]
    elif view == "past":
        rows = sorted(
            (r for r in rows if r.reserved_at.date() < today),
            key=lambda r: r.reserved_at,
            reverse=True,
        )
    context = {
        "store": store,
        "view": view,
        "views": OWNER_VIEWS,
        "status": status,
        "statuses": [s.value for s in ReservationStatus],
        "reservations": rows,
        "day": picked,
        "prev_day": picked - timedelta(days=1) if picked else None,
        "next_day": picked + timedelta(days=1) if picked else None,
    }
    return _render(request, "owner/reservation_list.html", context)


@router.get("/owner/reservations/{reservation_id}", response_class=HTMLResponse)
def owner_reservation_detail(
    request: Request, reservation_id: int, service: ServiceDep, error: str | None = None
) -> HTMLResponse:
    try:
        reservation = service.get(reservation_id)
    except ReservationNotFoundError as e:
        raise HTTPException(status_code=404, detail="예약을 찾을 수 없습니다") from e
    owner_actions = [
        a for a in state_of(reservation.status).allowed_actions() if a in OWNER_ACTIONS
    ]
    context = {
        "reservation": reservation,
        "owner_actions": owner_actions,
        "error": error,
        "cancel_reasons": CANCEL_REASONS,
        "max_reason": MAX_REASON_LENGTH,
        "max_note": MAX_NOTE_LENGTH,
        # 이 손님의 방문·노쇼 횟수 (확정 전에 노쇼 손님인지 바로 보이게)
        "customer_history": service.customer_history(reservation.customer.phone),
    }
    return _render(request, "owner/reservation_detail.html", context)


@router.post("/owner/reservations/{reservation_id}/{action}")
def owner_process(
    reservation_id: int,
    action: str,
    service: ServiceDep,
    reason: FormStr = "",
    reason_custom: FormStr = "",
) -> RedirectResponse:
    """처리 후 상세 화면으로 돌아간다. 새로고침해도 다시 처리되지 않게 리다이렉트한다.

    확정은 손님에게 남길 한마디, 취소·노쇼는 사유를 받을 수 있다.
    '직접 입력'을 고르면 reason_custom을 쓴다.
    """
    url = f"/owner/reservations/{reservation_id}"
    memo = reason_custom if reason == "직접 입력" else reason
    try:
        service.process(reservation_id, action, memo)
    except ReservationNotFoundError as e:
        raise HTTPException(status_code=404, detail="예약을 찾을 수 없습니다") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail="알 수 없는 처리입니다") from e
    except InvalidTransitionError as e:
        url += f"?error={quote(str(e))}"
    return RedirectResponse(url, status_code=303)


# ---------- 점주: 고객 이력 (UC-10) ----------


CUSTOMER_FILTERS = {"all": "전체", "regular": "단골", "no_show": "노쇼 주의"}
REGULAR_VISITS = 3  # 방문 3회 이상이면 단골 (화면 배지와 같은 기준)


@router.get("/owner/customers", response_class=HTMLResponse)
def customer_history(
    request: Request, service: ServiceDep, phone: str = "", q: str = "", only: str = "all"
) -> HTMLResponse:
    """phone: 고객 한 명의 이력 (다른 화면의 링크). q: 이름 또는 번호(뒤 4자리도 가능)로 검색."""
    phone = normalize_phone(phone.strip())
    q = q.strip()
    history = service.customer_history(phone) if phone else None
    recent = []
    if not phone:  # 검색 전에는 전체 고객, 검색하면 맞는 고객만
        stores = service.repo.list_stores()
        recent = service.repo.recent_customers(stores[0].id, query=q) if stores else []
        if q and len(recent) == 1:  # 한 명이면 바로 그 손님 이력으로
            return RedirectResponse(f"/owner/customers?phone={quote(recent[0][0].phone)}", 303)
        if q and not recent and service.repo.find_customer(q):  # 예약 없이 문의만 한 손님
            return RedirectResponse(f"/owner/customers?phone={quote(normalize_phone(q))}", 303)
    only = only if only in CUSTOMER_FILTERS else "all"
    counts = {
        "all": len(recent),
        "regular": sum((v or 0) >= REGULAR_VISITS for _, _, _, v, _ in recent),
        "no_show": sum(bool(n) for *_, n in recent),
    }
    if only == "regular":
        recent = [row for row in recent if (row[3] or 0) >= REGULAR_VISITS]
    elif only == "no_show":  # 노쇼 많은 손님부터
        recent = sorted((row for row in recent if row[4]), key=lambda row: -row[4])
    context = {
        "phone": phone,
        "q": q,
        "history": history,
        "recent": recent,
        "only": only,
        "filters": CUSTOMER_FILTERS,
        "filter_counts": counts,
    }
    return _render(request, "owner/customer_history.html", context)
