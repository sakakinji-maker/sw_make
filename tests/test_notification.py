# AI-assisted (Claude)
"""예약·문의 문자 알림 테스트. 실제 문자는 보내지 않고 MockSmsSender에 쌓인 내용을 확인한다.

'지금'은 2026-11-10(화) 09:00, 예약은 11/11(수) 12:00 2명.
"""

from datetime import date, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters.ai.mock_adapter import MockAIClient
from app.adapters.sms import MockSmsSender, SmsError, digits, get_sms_sender
from app.adapters.sms.solapi_adapter import SolapiSmsSender
from app.db.database import Base, get_session
from app.db.seed import load_all
from app.main import app
from app.models.models import Store
from app.repositories.inquiry_repository import InquiryRepository
from app.services.inquiry.schemas import AnswerSubmit, InquiryCreate
from app.services.inquiry.service import InquiryService
from app.services.notification import Notifier, get_notifier
from app.services.reservation.schemas import ReservationCreate, ReservationSlot
from app.services.reservation.service import ReservationRejectedError, ReservationService

NOW = datetime(2026, 11, 10, 9, 0)
CUSTOMER = "010-9999-0000"
OWNER = "010-1111-2222"


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as s:
        load_all(s)
        s.commit()
    return factory


@pytest.fixture
def session(session_factory):
    with session_factory() as s:
        yield s


@pytest.fixture
def sms() -> MockSmsSender:
    return MockSmsSender()


@pytest.fixture
def notifier(sms) -> Notifier:
    return Notifier(sms, owner_phone=OWNER)


@pytest.fixture
def reservations(session, notifier) -> ReservationService:
    return ReservationService(session, now=lambda: NOW, notifier=notifier)


@pytest.fixture
def inquiries(session, notifier) -> InquiryService:
    return InquiryService(MockAIClient(), InquiryRepository(session), notifier=notifier)


def cafe_id(session) -> int:
    return session.query(Store).filter_by(name="브루밍 카페").one().id


def book(service: ReservationService, session):
    return service.create(
        ReservationCreate(
            store_id=cafe_id(session),
            name="홍길동",
            phone=CUSTOMER,
            visit_date=date(2026, 11, 11),
            visit_time=time(12, 0),
            party_size=2,
        )
    )


def to(sms: MockSmsSender, phone: str) -> list[str]:
    return [text for number, text in sms.sent if number == digits(phone)]


# ---------- 예약 ----------


def test_reservation_request_notifies_owner_and_customer(reservations, session, sms):
    book(reservations, session)
    assert to(sms, OWNER) == ["[브루밍 카페] 새 예약 요청: 홍길동 11/11(수) 12:00 2명"]
    assert to(sms, CUSTOMER) == [
        "[브루밍 카페] 11/11(수) 12:00 2명 예약 신청 접수. 확정되면 다시 알려 드립니다."
    ]


def test_change_notifies_owner_and_customer(reservations, session, sms):
    r = book(reservations, session)
    sms.sent.clear()
    new = ReservationSlot(visit_date=date(2026, 11, 12), visit_time=time(18, 0), party_size=3)
    reservations.change(r.id, CUSTOMER, new)
    assert to(sms, OWNER) == [
        "[브루밍 카페] 예약 변경 요청: 홍길동 11/11(수) 12:00 2명 → 11/12(목) 18:00 3명"
    ]
    assert "11/12(목) 18:00 3명으로 변경 접수" in to(sms, CUSTOMER)[0]


def test_rejected_change_sends_nothing(reservations, session, sms):
    r = book(reservations, session)
    sms.sent.clear()
    monday = ReservationSlot(visit_date=date(2026, 11, 16), visit_time=time(12, 0), party_size=2)
    with pytest.raises(ReservationRejectedError):
        reservations.change(r.id, CUSTOMER, monday)
    assert sms.sent == []


def test_confirm_notifies_customer(reservations, session, sms):
    r = book(reservations, session)
    sms.sent.clear()
    reservations.process(r.id, "confirm")
    assert to(sms, CUSTOMER) == ["[브루밍 카페] 11/11(수) 12:00 2명 예약이 확정되었습니다."]


def test_owner_cancel_notifies_customer_only(reservations, session, sms):
    r = book(reservations, session)
    sms.sent.clear()
    reservations.process(r.id, "cancel")
    assert len(sms.sent) == 1
    assert "매장 사정으로 취소" in to(sms, CUSTOMER)[0]


def test_customer_cancel_notifies_customer_and_owner(reservations, session, sms):
    r = book(reservations, session)
    sms.sent.clear()
    reservations.cancel_by_customer(r.id, CUSTOMER)
    assert to(sms, CUSTOMER) == ["[브루밍 카페] 11/11(수) 12:00 예약 취소가 완료되었습니다."]
    assert to(sms, OWNER) == ["[브루밍 카페] 예약 취소: 홍길동 11/11(수) 12:00 2명"]


def test_visit_and_no_show_send_nothing(reservations, session, sms):
    r = book(reservations, session)
    reservations.process(r.id, "confirm")
    sms.sent.clear()
    reservations.process(r.id, "visit")
    assert sms.sent == []


# ---------- 문의 ----------


def register(service: InquiryService, session, content: str = "아메리카노 얼마예요?"):
    data = InquiryCreate(store_id=cafe_id(session), name="홍길동", phone=CUSTOMER, content=content)
    return service.register(data)


def test_inquiry_notifies_owner_with_preview(inquiries, session, sms):
    register(inquiries, session, content="가" * 50)
    [text] = to(sms, OWNER)
    assert text == f"[브루밍 카페] 새 문의(홍길동): {'가' * 20}…"


def test_answer_notifies_customer_once(inquiries, session, sms):
    i = register(inquiries, session)
    inquiries.finalize(i.id, AnswerSubmit(answer="4,500원입니다."))
    inquiries.finalize(i.id, AnswerSubmit(answer="아메리카노는 4,500원입니다."))  # 오타 수정
    assert len(to(sms, CUSTOMER)) == 1
    assert "답변이 등록되었습니다" in to(sms, CUSTOMER)[0]


# ---------- 실패해도 업무는 계속 ----------


def test_sms_failure_does_not_break_reservation(session):
    service = ReservationService(
        session, now=lambda: NOW, notifier=Notifier(MockSmsSender(fail=True), OWNER)
    )
    assert book(service, session).id is not None


def test_missing_owner_phone_skips_owner_message(session, sms):
    service = ReservationService(session, now=lambda: NOW, notifier=Notifier(sms, owner_phone=""))
    book(service, session)
    assert to(sms, OWNER) == [] and len(to(sms, CUSTOMER)) == 1


def test_services_without_notifier_send_nothing(session):
    # 기존 테스트·스크립트처럼 알림기를 넘기지 않으면 아무것도 보내지 않는다.
    assert book(ReservationService(session, now=lambda: NOW), session).id is not None


# ---------- 어댑터 ----------


def test_digits_and_factory():
    assert digits("010-1234-5678") == "01012345678"
    assert isinstance(get_sms_sender("mock"), MockSmsSender)
    with pytest.raises(SmsError):
        get_sms_sender("kakao")


def test_solapi_requires_settings_and_hides_secret():
    with pytest.raises(SmsError):
        SolapiSmsSender(api_key="", api_secret="", sender="")
    sender = SolapiSmsSender(api_key="k", api_secret="secret-value", sender="010-1111-2222")
    header = sender._auth_header()
    assert header.startswith("HMAC-SHA256 apiKey=k, date=")
    assert "secret-value" not in header and sender.sender == "01011112222"


# ---------- 화면 → 알림 연결 ----------


def test_routes_use_notifier(session_factory, session, sms, notifier):
    def _session():
        with session_factory() as s:
            yield s

    def _reservations():
        with session_factory() as s:
            yield ReservationService(s, now=lambda: NOW, notifier=notifier)

    from app.presentation.routers.inquiry import get_ai
    from app.presentation.routers.reservation import get_service

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_service] = _reservations
    app.dependency_overrides[get_ai] = MockAIClient
    app.dependency_overrides[get_notifier] = lambda: notifier
    try:
        with TestClient(app) as c:
            form = {"store_id": cafe_id(session), "name": "홍길동", "phone": CUSTOMER}
            c.post(
                "/reservations",
                data=form | {"visit_date": "2026-11-11", "visit_time": "12:00", "party_size": "2"},
            )
            c.post("/inquiries", data=form | {"content": "주차 되나요?"})
    finally:
        app.dependency_overrides.clear()
    owner_texts = to(sms, OWNER)
    assert any("새 예약 요청" in t for t in owner_texts)
    assert any("새 문의" in t for t in owner_texts)


def test_every_message_fits_short_sms(reservations, inquiries, session, sms):
    # 단문은 90바이트(EUC-KR)까지. 넘으면 장문(LMS) 요금이 붙는다.
    r = book(reservations, session)
    new = ReservationSlot(visit_date=date(2026, 11, 12), visit_time=time(18, 0), party_size=10)
    reservations.change(r.id, CUSTOMER, new)
    reservations.process(r.id, "confirm")
    reservations.process(r.id, "cancel")
    r2 = book(reservations, session)
    reservations.cancel_by_customer(r2.id, CUSTOMER)
    i = register(inquiries, session, content="가" * 100)
    inquiries.finalize(i.id, AnswerSubmit(answer="답변"))
    assert len(sms.sent) == 12  # 신청2+변경2+확정1+취소1+신청2+고객취소2+문의1+답변1
    for _, text in sms.sent:
        assert len(text.encode("cp949")) <= 90, text
