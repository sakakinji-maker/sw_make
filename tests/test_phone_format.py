# AI-assisted (Claude)
"""연락처 형식 통일: 하이픈 유무와 상관없이 같은 손님으로 보고, 저장은 010-1234-5678 모양으로."""

from datetime import date, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters.ai.mock_adapter import MockAIClient
from app.db.database import Base, get_session
from app.db.seed import load_all
from app.main import app
from app.models.models import Customer, Reservation
from app.presentation.routers.reservation import get_service
from app.repositories.inquiry_repository import InquiryRepository
from app.services.inquiry.schemas import InquiryCreate, InquiryLookup
from app.services.inquiry.service import InquiryService
from app.services.phone import normalize_phone, phone_digits
from app.services.reservation.schemas import ReservationCreate
from app.services.reservation.service import ReservationService

NOW = datetime(2026, 11, 10, 9, 0)


@pytest.mark.parametrize(
    ("raw", "saved"),
    [
        ("01012345678", "010-1234-5678"),
        ("010-1234-5678", "010-1234-5678"),
        (" 010 1234 5678 ", "010-1234-5678"),
        ("0111234567", "011-123-4567"),  # 10자리 옛 번호
    ],
)
def test_normalize_phone(raw, saved):
    assert normalize_phone(raw) == saved
    assert phone_digits(saved) == phone_digits(raw)


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


def booking(phone: str) -> ReservationCreate:
    return ReservationCreate(
        store_id=1,
        name="홍길동",
        phone=phone,
        visit_date=date(2026, 11, 11),
        visit_time=time(12, 0),
        party_size=2,
    )


def test_reservation_saved_with_hyphens_and_found_either_way(factory):
    with factory() as s:
        service = ReservationService(s, now=lambda: NOW)
        r = service.create(booking("01099990000"))
        assert r.customer.phone == "010-9999-0000"
        assert service.find_by_phone("010-9999-0000") == service.find_by_phone("01099990000") == [r]
        assert service.get_owned(r.id, "01099990000") is r  # 변경·취소 본인 확인도 통과
        # 같은 번호를 다른 모양으로 써도 같은 손님으로 본다
        r2 = service.create(booking("010-9999-0000"))
        assert r2.customer is r.customer


def test_legacy_phone_without_hyphen_is_still_found(factory):
    with factory() as s:
        store_id = 1
        customer = Customer(name="옛손님", phone="01088887777")  # 예전에 하이픈 없이 저장된 데이터
        s.add(
            Reservation(
                store_id=store_id,
                customer=customer,
                reserved_at=datetime(2026, 11, 12, 12),
                party_size=2,
                status="요청",
            )
        )
        s.commit()
        service = ReservationService(s, now=lambda: NOW)
        assert len(service.find_by_phone("010-8888-7777")) == 1


def test_inquiry_phone_normalized(factory):
    with factory() as s:
        service = InquiryService(MockAIClient(), InquiryRepository(s))
        i = service.register(
            InquiryCreate(store_id=1, name="홍길동", phone="01077776666", content="주차?")
        )
        assert i.customer.phone == "010-7777-6666"
        assert service.find_for_customer(InquiryLookup(phone="010-7777-6666"))


def test_lookup_page_cards_and_sections(factory):
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
            c.post(
                "/reservations",
                data={
                    "store_id": "1",
                    "name": "홍길동",
                    "phone": "01099990000",
                    "visit_date": "2026-11-11",
                    "visit_time": "12:00",
                    "party_size": "2",
                },
            )
            page = c.post(
                "/reservations/lookup", data={"phone": "01099990000", "name": "홍길동"}
            ).text
            empty = c.post(
                "/reservations/lookup", data={"phone": "010-5555-4444", "name": "홍길동"}
            ).text
    finally:
        app.dependency_overrides.clear()
    assert 'value="010-9999-0000"' in page  # 조회칸도 표준 모양으로 다시 보여 준다
    assert "data-upcoming" in page and "11/11(수)" in page
    assert "<th>번호</th>" not in page  # 표 대신 카드
    assert "data-empty" in empty and 'href="/reservations/new"' in empty
