# AI-assisted (Claude) — 정회성 검토 완료
"""F-03 문의 등록 → AI 초안 생성 → DB 대조 흐름 테스트 (12주차).

메모리 DB에 가상 데이터를 넣고, AI는 Mock으로 바꿔서 서비스와 화면을 모두 확인한다.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters.ai.mock_adapter import MockAIClient
from app.db.database import Base, get_session
from app.db.seed import load_all
from app.main import app
from app.models.models import Inquiry, Store
from app.presentation.routers.inquiry import get_ai
from app.repositories.inquiry_repository import InquiryRepository
from app.services.inquiry.schemas import AnswerSubmit, InquiryCreate, InquiryLookup, korean_errors
from app.services.inquiry.service import InquiryNotFoundError, InquiryService, StoreNotFoundError


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


def service_with(session, ai=None) -> InquiryService:
    return InquiryService(ai or MockAIClient(), InquiryRepository(session))


def cafe(session) -> Store:
    return session.query(Store).filter_by(name="온기 카페").one()


def valid_form(store_id: int, **overrides) -> dict:
    form = {
        "store_id": store_id,
        "name": "테스트",
        "phone": "010-9999-0000",
        "content": "주차 되나요?",
    }
    return form | overrides


# ---------- 서비스: F-03-1 문의 등록 ----------


def test_register_creates_unanswered_inquiry(session):
    inquiry = service_with(session).register(InquiryCreate(**valid_form(cafe(session).id)))
    assert inquiry.id and inquiry.status == "미응답"
    assert inquiry.customer.phone == "010-9999-0000"


def test_register_reuses_customer_by_phone(session):
    service = service_with(session)
    a = service.register(InquiryCreate(**valid_form(cafe(session).id)))
    b = service.register(InquiryCreate(**valid_form(cafe(session).id, content="와이파이?")))
    assert a.customer_id == b.customer_id


def test_register_unknown_store(session):
    with pytest.raises(StoreNotFoundError):
        service_with(session).register(InquiryCreate(**valid_form(9999)))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("content", "   ", "문의 내용을(를) 입력해 주세요."),
        ("content", "가" * 1001, "문의 내용은(는) 1,000자 이하로 입력해 주세요."),
        ("phone", "12345", "연락처 형식이 올바르지 않습니다. (예: 010-1234-5678)"),
        ("name", "", "이름을(를) 입력해 주세요."),
    ],
)
def test_invalid_input_has_korean_message(field, value, message):
    with pytest.raises(ValidationError) as info:
        InquiryCreate(**valid_form(1, **{field: value}))
    assert message in korean_errors(info.value)


# ---------- 서비스: F-03-2, F-03-3 초안 생성과 대조 결과 저장 ----------


def first_inquiry(session) -> Inquiry:
    return session.query(Inquiry).filter_by(store_id=cafe(session).id).first()


def test_generate_draft_saves_ai_draft_and_check(session):
    ai = MockAIClient(fixed_response="아메리카노는 4,500원, 09:00~21:00 영업합니다.")
    q = first_inquiry(session)
    result = service_with(session, ai).generate_draft(q.id)
    session.refresh(q)
    assert result.mismatches == [] and q.ai_draft.startswith("아메리카노")
    assert InquiryService.mismatches_of(q) == []
    assert q.status == "미응답"  # 발송 전까지는 미응답 유지 (F-03-4는 점주 확정 후)


def test_generate_draft_records_mismatch(session):
    ai = MockAIClient(fixed_response="아메리카노는 3,000원이고 22:00까지 합니다.")
    q = first_inquiry(session)
    service_with(session, ai).generate_draft(q.id)
    session.refresh(q)
    kinds = [m["kind"] for m in InquiryService.mismatches_of(q)]
    assert kinds == ["가격", "시각"]


def test_prompt_uses_seeded_store_data(session):
    ai = MockAIClient()
    service_with(session, ai).generate_draft(first_inquiry(session).id)
    assert "밤라떼: 6,000원" in ai.last_prompt and "휴무일 월" in ai.last_prompt


def test_generate_draft_ai_failure_keeps_inquiry(session):
    q = first_inquiry(session)
    result = service_with(session, MockAIClient(fail=True)).generate_draft(q.id)
    session.refresh(q)
    assert result.error and q.ai_draft is None


def test_generate_draft_unknown_inquiry(session):
    with pytest.raises(InquiryNotFoundError):
        service_with(session).generate_draft(9999)


# ---------- 화면 (라우터) ----------


@pytest.fixture
def client(session_factory):
    ai = MockAIClient(fixed_response="아메리카노는 4,000원입니다.")

    def override_session():
        with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_ai] = lambda: ai
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_customer_form_lists_stores(client):
    page = client.get("/inquiries/new")
    assert page.status_code == 200 and "온기 카페" in page.text and "결 헤어" in page.text


def test_customer_submit_success(client):
    page = client.post("/inquiries", data=valid_form(1))
    assert page.status_code == 200 and "문의가 접수되었습니다" in page.text


def test_customer_submit_invalid_shows_errors_and_keeps_input(client):
    page = client.post("/inquiries", data=valid_form(1, phone="abc", content="그대로 남아야 함"))
    assert page.status_code == 400
    assert "연락처 형식이 올바르지 않습니다" in page.text and "그대로 남아야 함" in page.text


def test_owner_list_shows_unanswered(client):
    page = client.get("/owner/inquiries?store_id=1")
    assert page.status_code == 200 and "미응답" in page.text and "아메리카노 한 잔" in page.text


def test_owner_generate_draft_shows_warning(client):
    redirect = client.post("/owner/inquiries/1/draft", follow_redirects=False)
    assert redirect.status_code == 303
    page = client.get(redirect.headers["location"])
    assert "4,000원" in page.text and "매장 정보와 다른 내용" in page.text


def test_owner_detail_404(client):
    assert client.get("/owner/inquiries/9999").status_code == 404


def test_owner_draft_ai_failure_message(client):
    app.dependency_overrides[get_ai] = lambda: MockAIClient(fail=True)
    redirect = client.post("/owner/inquiries/2/draft", follow_redirects=False)
    assert redirect.headers["location"].endswith("?ai_error=1")
    assert "직접 답변을 작성" in client.get(redirect.headers["location"]).text


# ---------- 13주차: F-03-3 휴무일, F-03-4 발송 완료, F-03-5 직접 작성 ----------
# AI-assisted (Claude) — 정회성 검토 완료


def test_generate_draft_detects_wrong_closed_day(session):
    ai = MockAIClient(fixed_response="온기 카페는 화요일에 쉽니다.")  # 실제 휴무는 월요일
    q = first_inquiry(session)
    result = service_with(session, ai).generate_draft(q.id)
    assert [(m.kind, m.found) for m in result.mismatches] == [("휴무일", "화요일")]


def test_finalize_saves_answer_and_keeps_ai_draft(session):
    ai = MockAIClient(fixed_response="아메리카노는 4,000원입니다.")
    q = first_inquiry(session)
    service = service_with(session, ai)
    service.generate_draft(q.id)
    service.finalize(q.id, AnswerSubmit(answer="아메리카노는 4,500원입니다."))
    session.refresh(q)
    assert q.status == "답변완료" and q.final_answer == "아메리카노는 4,500원입니다."
    assert q.ai_draft == "아메리카노는 4,000원입니다."  # 검증 보고서용 원본 보존


def test_finalize_without_ai_draft(session):
    # F-03-5: AI 실패로 초안이 없어도 점주가 직접 쓴 답변으로 확정할 수 있다
    q = first_inquiry(session)
    service = service_with(session, MockAIClient(fail=True))
    assert service.generate_draft(q.id).error
    service.finalize(q.id, AnswerSubmit(answer="직접 작성한 답변"))
    session.refresh(q)
    assert q.status == "답변완료" and q.ai_draft is None


def test_finalize_unknown_inquiry(session):
    with pytest.raises(InquiryNotFoundError):
        service_with(session).finalize(9999, AnswerSubmit(answer="답변"))


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("   ", "답변을(를) 입력해 주세요."),
        ("가" * 2001, "답변은(는) 2,000자 이하로 입력해 주세요."),
    ],
)
def test_invalid_answer_has_korean_message(value, message):
    with pytest.raises(ValidationError) as info:
        AnswerSubmit(answer=value)
    assert message in korean_errors(info.value)


def test_check_answer_flags_owner_mistake(session):
    q = first_inquiry(session)
    mismatches = service_with(session).check_answer(q, "22:00까지 영업합니다.")
    assert [m.kind for m in mismatches] == ["시각"]


def test_owner_submit_answer_marks_answered(client):
    redirect = client.post("/owner/inquiries/1/answer", data={"answer": "4,500원입니다."})
    assert redirect.status_code == 200  # TestClient가 303을 따라간다
    assert "발송 완료로 저장했습니다" in redirect.text and "답변완료" in redirect.text
    assert "답변 복사" in redirect.text


def test_owner_submit_empty_answer_rejected(client):
    page = client.post("/owner/inquiries/1/answer", data={"answer": "  "})
    assert page.status_code == 400 and "답변을(를) 입력해 주세요." in page.text
    assert "미응답" in page.text


def test_owner_submit_answer_404(client):
    assert client.post("/owner/inquiries/9999/answer", data={"answer": "x"}).status_code == 404


def test_owner_detail_prefills_ai_draft(client):
    client.post("/owner/inquiries/1/draft")
    page = client.get("/owner/inquiries/1")
    assert ">아메리카노는 4,000원입니다.</textarea>" in page.text


def test_owner_ai_failure_then_write_directly(client):
    app.dependency_overrides[get_ai] = lambda: MockAIClient(fail=True)
    client.post("/owner/inquiries/2/draft")
    page = client.post("/owner/inquiries/2/answer", data={"answer": "직접 쓴 답변입니다."})
    assert "발송 완료로 저장했습니다" in page.text and "직접 쓴 답변입니다." in page.text


def test_owner_answered_shows_warning_for_wrong_final(client):
    page = client.post("/owner/inquiries/1/answer", data={"answer": "3,000원입니다."})
    assert "저장된 답변에 매장 정보와 다른 내용" in page.text


# ---------- F-03-6 고객 답변 확인 ----------
# AI-assisted (Claude) — 정회성 검토 완료
# 가상 데이터 Q01(id=1): 온기 카페, 김하늘 010-0000-0101, "아메리카노 한 잔 얼마예요?"
Q01_PHONE = "010-0000-0101"


def lookup(client, phone: str):
    return client.post("/inquiries/lookup", data={"phone": phone})


def test_lookup_unanswered_shows_waiting(client):
    page = lookup(client, Q01_PHONE)
    assert page.status_code == 200
    assert "아메리카노 한 잔 얼마예요?" in page.text and "답변 대기" in page.text


def test_lookup_hides_unconfirmed_ai_draft(client):
    # 점주가 확정하기 전의 AI 초안(틀린 가격 4,000원)이 고객에게 보이면 안 된다
    client.post("/owner/inquiries/1/draft")
    page = lookup(client, Q01_PHONE)
    assert "4,000원" not in page.text and "답변 대기" in page.text


def test_lookup_shows_confirmed_answer(client):
    client.post("/owner/inquiries/1/draft")
    client.post("/owner/inquiries/1/answer", data={"answer": "아메리카노는 4,500원입니다."})
    page = lookup(client, Q01_PHONE)
    assert "답변 완료" in page.text and "아메리카노는 4,500원입니다." in page.text
    assert "4,000원" not in page.text


def test_lookup_accepts_phone_without_hyphen(client):
    assert "아메리카노 한 잔 얼마예요?" in lookup(client, "01000000101").text


def test_lookup_shows_only_own_inquiries(client):
    page = lookup(client, Q01_PHONE)
    assert "가을 시즌 밤라떼" not in page.text  # Q02는 다른 고객(010-0000-0102)


def test_lookup_new_inquiry_after_submit(client):
    client.post("/inquiries", data=valid_form(1, phone="010-5555-6666", content="단체석 있나요?"))
    page = lookup(client, "010-5555-6666")
    assert "단체석 있나요?" in page.text and "온기 카페" in page.text


def test_lookup_no_result_and_invalid_phone(client):
    assert "남긴 문의가 없습니다" in lookup(client, "010-1111-2222").text
    page = lookup(client, "abc")
    assert page.status_code == 400 and "연락처 형식이 올바르지 않습니다" in page.text


def test_lookup_page_and_links(client):
    assert client.get("/inquiries/lookup").status_code == 200
    assert "/inquiries/lookup" in client.get("/").text
    done = client.post("/inquiries", data=valid_form(1))
    assert "내 문의 확인" in done.text


def test_customer_view_has_no_ai_draft(session):
    # 화면이 실수로 초안을 쓰지 않도록 고객용 객체에는 초안 필드 자체가 없다
    service = service_with(session, MockAIClient(fixed_response="초안입니다."))
    service.generate_draft(1)
    (view,) = service.find_for_customer(InquiryLookup(phone=Q01_PHONE))
    assert view.answer is None and not hasattr(view, "ai_draft")
