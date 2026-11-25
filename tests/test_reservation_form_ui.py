# AI-assisted (Claude)
"""예약 신청·변경 화면 UI: 매장 선택 제거, 영업·문자 안내, 지난 날짜 막기, 30분 단위 시간."""

from datetime import datetime, time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_session
from app.db.seed import load_all
from app.main import app
from app.models.models import Reservation
from app.presentation.routers.reservation import get_service, time_slots
from app.services.reservation.service import ReservationService

NOW = datetime(2026, 11, 10, 9, 0)  # 화요일


def test_time_slots_every_30_minutes_within_hours():
    slots = time_slots(SimpleNamespace(open_time=time(9), close_time=time(21)))
    assert slots[0] == "09:00" and slots[1] == "09:30" and slots[-1] == "20:30"
    assert "21:00" not in slots and len(slots) == 24


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as s:
        load_all(s)
        s.commit()

    def _session():
        with factory() as s:
            yield s

    def _service():
        with factory() as s:
            yield ReservationService(s, now=lambda: NOW)

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_service] = _service
    with TestClient(app) as c:
        c.factory = factory
        yield c
    app.dependency_overrides.clear()


def test_new_form_layout(client):
    page = client.get("/reservations/new").text
    assert '<select id="store_id"' not in page  # 매장 선택칸 없음
    assert 'type="hidden" name="store_id"' in page
    assert "시간당" not in page  # 내부 정원은 손님에게 보이지 않음
    assert "영업 09:00–21:00" in page and "월요일 휴무" in page
    assert "예약 확인 문자를 보내 드려요" in page
    assert 'min="2026-11-10"' in page  # 오늘 이전 날짜는 고를 수 없음
    assert '<option value="09:00"' in page and '<option value="20:30"' in page
    assert '<option value="21:00"' not in page
    assert "const closed = [1]" in page  # 월요일(getDay=1) 휴무 안내


def test_rejected_submit_keeps_selected_time(client):
    data = {"store_id": "1", "name": "홍길동", "phone": "010-9999-0000"}
    data |= {"visit_date": "2026-11-16", "visit_time": "12:30", "party_size": "2"}  # 월요일
    page = client.post("/reservations", data=data).text
    assert "월요일은 휴무일입니다." in page
    assert '<option value="12:30" selected>' in page


def test_edit_form_keeps_off_grid_time(client):
    with client.factory() as s:
        r = s.query(Reservation).filter(Reservation.status == "요청").first()
        r.reserved_at = r.reserved_at.replace(minute=45)
        s.commit()
        rid, phone, name = r.id, r.customer.phone, r.customer.name
        current = f"{r.reserved_at:%H:%M}"
    page = client.post(f"/reservations/{rid}/edit", data={"phone": phone, "name": name}).text
    assert f'<option value="{current}" selected>{current} (현재 예약)</option>' in page
    assert "영업 09:00–21:00" in page
