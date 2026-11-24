# AI-assisted (Claude)
"""점주 취소 사유·노쇼 메모: 이력 저장, 손님 문자, 단문 길이, 예전 DB 자동 칸 추가."""

from datetime import date, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters.sms import MockSmsSender, digits
from app.db import database
from app.db.database import Base, get_session
from app.db.seed import load_all
from app.main import app
from app.presentation.routers.reservation import get_service
from app.services.notification import Notifier
from app.services.reservation.schemas import ReservationCreate
from app.services.reservation.service import (
    CANCEL_REASONS,
    MAX_NOTE_LENGTH,
    MAX_REASON_LENGTH,
    ReservationService,
)

NOW = datetime(2026, 11, 10, 9, 0)
PHONE = "010-9999-0000"


@pytest.fixture
def factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    f = sessionmaker(bind=engine)
    with f() as s:
        load_all(s)
        s.commit()
    return f


@pytest.fixture
def sms():
    return MockSmsSender()


def service_for(session, sms) -> ReservationService:
    return ReservationService(session, now=lambda: NOW, notifier=Notifier(sms, "010-1111-2222"))


def book(service: ReservationService):
    data = ReservationCreate(
        store_id=1,
        name="홍길동",
        phone=PHONE,
        visit_date=date(2026, 11, 11),
        visit_time=time(12, 0),
        party_size=2,
    )
    return service.create(data)


def customer_texts(sms):
    return [t for n, t in sms.sent if n == digits(PHONE)]


@pytest.mark.parametrize("reason", [*CANCEL_REASONS, "가" * MAX_REASON_LENGTH])
def test_cancel_with_reason_saved_and_texted_as_short_sms(factory, sms, reason):
    with factory() as s:
        service = service_for(s, sms)
        r = book(service)
        sms.sent.clear()
        service.process(r.id, "cancel", reason)
        assert r.histories[-1].memo == reason
        [text_] = customer_texts(sms)
        assert f"사유: {reason}" in text_ and len(text_.encode("cp949")) <= 90


def test_cancel_without_reason_keeps_old_message(factory, sms):
    with factory() as s:
        service = service_for(s, sms)
        r = book(service)
        sms.sent.clear()
        service.process(r.id, "cancel")
        assert "매장 사정으로 취소" in customer_texts(sms)[0] and r.histories[-1].memo is None


def test_reason_is_cut_and_only_kept_for_cancel_or_no_show(factory, sms):
    with factory() as s:
        service = service_for(s, sms)
        r = book(service)
        sms.sent.clear()
        service.process(r.id, "confirm")  # 한마디 없이 확정하면 메모·안내 없음
        assert r.histories[-1].memo is None
        assert "메모" not in customer_texts(sms)[-1]
        sms.sent.clear()
        service.process(r.id, "no_show", "  연락 없이 미방문이었고 전화도 받지 않음  ")
        assert r.histories[-1].memo == "연락 없이 미방문이었고 전화도 받지 않음"[:MAX_REASON_LENGTH]
        assert sms.sent == []  # 노쇼는 손님에게 문자를 보내지 않는다


def test_owner_cancel_form_and_customer_sees_reason(factory, monkeypatch):
    monkeypatch.setattr(database, "SessionLocal", factory)

    def _session():
        with factory() as s:
            yield s

    def _service():
        with factory() as s:
            yield ReservationService(s, now=lambda: NOW)

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_service] = _service
    try:
        with TestClient(app) as c:
            with factory() as s:
                rid = book(ReservationService(s, now=lambda: NOW)).id
            detail = c.get(f"/owner/reservations/{rid}").text
            assert 'data-reason-form="cancel"' in detail and "재료 소진" in detail
            data = {"reason": "직접 입력", "reason_custom": "원두 입고 지연"}
            page = c.post(f"/owner/reservations/{rid}/cancel", data=data).text
            assert "원두 입고 지연" in page.split("data-history")[1]
            mine = c.post("/reservations/lookup", data={"phone": PHONE, "name": "홍길동"}).text
            assert "취소 사유: 원두 입고 지연" in mine
    finally:
        app.dependency_overrides.clear()


def test_old_database_gets_memo_column(tmp_path, monkeypatch):
    """예전 app.db(이력 표에 memo 칸 없음)도 서버를 켜면 칸이 추가된다. 두 번 켜도 문제없다."""
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE reservation_histories (id INTEGER PRIMARY KEY, "
                "reservation_id INTEGER, from_status VARCHAR(10), to_status VARCHAR(10), "
                "changed_at DATETIME)"
            )
        )
    monkeypatch.setattr(database, "engine", engine)
    database.add_missing_columns()
    database.add_missing_columns()
    assert "memo" in {c["name"] for c in inspect(engine).get_columns("reservation_histories")}


# ---------- 확정할 때 손님에게 한마디 (11/24) ----------


def test_confirm_note_saved_and_sms_points_to_lookup(factory, sms):
    with factory() as s:
        service = service_for(s, sms)
        r = book(service)
        sms.sent.clear()
        note = "커플석 창가 쪽으로 준비해 둘게요. 조심히 오세요!"
        service.process(r.id, "confirm", note)
        assert r.histories[-1].memo == note  # 50자까지 그대로
        [text_] = customer_texts(sms)
        assert "사장님 메모는 내 예약에서 확인" in text_ and note not in text_
        assert len(text_.encode("cp949")) <= 90  # 단문 유지
        service.process(book(service).id, "confirm", "가" * 80)
        assert len(service.get(r.id + 1).histories[-1].memo) == MAX_NOTE_LENGTH


def test_owner_confirm_note_and_no_show_warning_on_screens(factory, monkeypatch):
    monkeypatch.setattr(database, "SessionLocal", factory)

    def _session():
        with factory() as s:
            yield s

    def _service():
        with factory() as s:
            yield ReservationService(s, now=lambda: NOW)

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_service] = _service
    try:
        with TestClient(app) as c:
            with factory() as s:
                service = ReservationService(s, now=lambda: NOW)
                old = book(service)
                service.process(old.id, "confirm")
                service.process(old.id, "no_show")  # 예전에 노쇼 1번
                rid = book(service).id
            detail = c.get(f"/owner/reservations/{rid}").text
            assert "data-confirm-form" in detail and "손님에게 한마디 남기기" in detail
            assert "노쇼 1회 손님이에요." in detail and "data-no-show-count" in detail
            page = c.post(f"/owner/reservations/{rid}/confirm", data={"reason": "케이크 OK예요"})
            assert "케이크 OK예요" in page.text.split("data-history")[1]
            assert "data-no-show-warning" not in page.text  # 확정 뒤에는 경고를 내린다
            mine = c.post("/reservations/lookup", data={"phone": PHONE, "name": "홍길동"}).text
            assert "💬 사장님: 케이크 OK예요" in mine
    finally:
        app.dependency_overrides.clear()
