# AI-assisted (Claude)
"""F-05 대시보드 화면과 F-04 홍보 문구 화면 테스트 (13주차 피드백 반영).

- F-05-1: 다가오는 예약(요청·확정만), 미응답 문의 수, 최근 생성 콘텐츠를 보여준다.
- F-05-2: 각 항목을 누르면 처리 화면으로 이동한다.
- 운영계획서: 생성형 AI 결과는 사용자에게 AI 생성 결과임을 표시한다.
- NF-04: AI 호출이 실패해도 화면은 오류 안내를 보여주고 멈추지 않는다.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters.ai.mock_adapter import MockAIClient
from app.db.database import Base, get_session
from app.db.seed import load_all
from app.main import app
from app.models.models import Customer, Inquiry, MarketingContent, Reservation, Store
from app.presentation.routers import owner


def make_factory(seeded: bool) -> sessionmaker:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    if seeded:
        with factory() as s:
            load_all(s)
            s.commit()
    return factory


def client_for(factory: sessionmaker) -> TestClient:
    def _session():
        with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    return TestClient(app)


@pytest.fixture
def factory():
    f = make_factory(seeded=True)
    yield f
    app.dependency_overrides.clear()


@pytest.fixture
def client(factory):
    return client_for(factory)


# ---------- F-05 대시보드 ----------


def test_dashboard_shows_counts_and_links(client, factory):
    with factory() as s:
        unanswered = s.query(Inquiry).filter_by(store_id=1, status="미응답").count()
    res = client.get("/owner")
    assert res.status_code == 200
    card = res.text.split('data-card="unanswered"')[1].split("</a>")[0]
    assert f'kpi-value">{unanswered}<' in card  # F-05-1 미응답 문의 수
    for link in ("/owner/reservations", "/owner/inquiries", "/owner/marketing"):  # F-05-2
        assert f'href="{link}"' in res.text


def test_dashboard_lists_only_upcoming_requested_or_confirmed(client, factory):
    tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=12, minute=0, second=0)
    yesterday = tomorrow - timedelta(days=2)
    with factory() as s:
        store = s.get(Store, 1)
        for name, at, status in (
            ("미래요청손님", tomorrow, "요청"),
            ("미래취소손님", tomorrow, "취소"),
            ("지난요청손님", yesterday, "요청"),
        ):
            customer = Customer(name=name, phone="010-5555-0000")
            s.add(
                Reservation(
                    store=store, customer=customer, reserved_at=at, party_size=2, status=status
                )
            )
        s.commit()
    text = client.get("/owner").text
    assert "미래요청손님" in text
    assert "미래취소손님" not in text and "지난요청손님" not in text
    assert "/owner/reservations/" in text  # 예약 행을 누르면 상세 화면으로 이동 (F-05-2)


def test_dashboard_empty_state():
    client = client_for(make_factory(seeded=False))
    try:
        res = client.get("/owner")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    assert "오늘 이후 요청 또는 확정된 예약이 없습니다." in res.text
    assert "아직 생성된 홍보 콘텐츠가 없습니다." in res.text


def test_dashboard_marks_recent_contents_as_ai_generated(client, factory):
    with factory() as s:
        s.add(MarketingContent(store_id=1, channel="sms", target="아메리카노", text="테스트 문구"))
        s.commit()
    text = client.get("/owner").text
    assert "테스트 문구" in text and "AI 생성" in text


# ---------- F-04 홍보 문구: AI 생성 표시, AI 실패 처리 ----------


def generate(client, channel: str = "instagram"):
    return client.post(
        "/owner/marketing/generate",
        data={"channel": channel, "target": "아메리카노", "keywords_raw": "따뜻한"},
    )


def test_marketing_result_is_marked_ai_generated(client, monkeypatch):
    monkeypatch.setattr(owner, "get_ai_client", MockAIClient)
    res = generate(client)
    assert res.status_code == 200
    assert "data-ai-label" in res.text and "AI가 만든 문구입니다" in res.text
    # 저장된 이력과 상세 모달에도 AI 생성 표시가 붙는다
    assert res.text.count("AI 생성") >= 3


def test_marketing_ai_failure_shows_error_and_saves_nothing(client, factory, monkeypatch):
    monkeypatch.setattr(owner, "get_ai_client", lambda: MockAIClient(fail=True))
    res = generate(client)
    assert res.status_code == 200
    assert "문구 생성 실패" in res.text
    assert "data-ai-label" not in res.text  # 실패했으니 AI 결과 표시도 없다
    with factory() as s:
        assert s.query(MarketingContent).count() == 0


# ---------- F-03 문의 답변: AI 생성 표시 ----------


def test_inquiry_draft_is_marked_ai_generated(client):
    from app.presentation.routers.inquiry import get_ai

    app.dependency_overrides[get_ai] = MockAIClient
    client.post("/owner/inquiries/1/draft")
    page = client.get("/owner/inquiries/1").text
    assert "AI가 만든 초안입니다" in page


def test_markdown_removed_from_prefill_and_final_answer(client, factory):
    with factory() as s:
        q = s.get(Inquiry, 2)
        q.ai_draft = "**카페라떼**는 5,500원입니다."
        s.commit()
    page = client.get("/owner/inquiries/2").text
    assert ">카페라떼는 5,500원입니다.</textarea>" in page  # 답변 칸에는 기호 없이
    client.post("/owner/inquiries/2/answer", data={"answer": "**카페라떼**는 5,500원이에요."})
    with factory() as s:
        q = s.get(Inquiry, 2)
        assert q.final_answer == "카페라떼는 5,500원이에요."  # 손님이 보는 답변
        assert q.ai_draft == "**카페라떼**는 5,500원입니다."  # AI 원본은 검증용으로 그대로


def test_marketing_custom_target(client, factory, monkeypatch):
    """홍보 대상 직접 입력칸: 적으면 고른 대상 대신 쓴다 (11/24)."""
    monkeypatch.setattr(owner, "get_ai_client", MockAIClient)
    res = client.post(
        "/owner/marketing/generate",
        data={"channel": "sms", "target": "대학생", "target_custom": "근처 헬스장 회원"},
    )
    assert res.status_code == 200 and "data-ai-label" in res.text
    assert 'value="근처 헬스장 회원"' in res.text  # 입력한 대상이 칸에 남는다
    assert 'value="직접 입력"' not in res.text  # '직접 입력' 라디오는 없앴다
    with factory() as s:
        assert s.query(MarketingContent).one().target == "근처 헬스장 회원"
    empty = client.post("/owner/marketing/generate", data={"channel": "sms", "target": ""})
    assert "홍보 대상을 골라 주세요." in empty.text


def test_marketing_custom_keywords_join_checked_ones(client, factory, monkeypatch):
    """키워드 직접 입력칸 (11/24): 고른 키워드와 합쳐서 AI에 넘기고 이력에도 남긴다."""
    monkeypatch.setattr(owner, "get_ai_client", MockAIClient)
    res = client.post(
        "/owner/marketing/generate",
        data={
            "channel": "sms",
            "target": "대학생",
            "keywords_raw": "신메뉴 출시",
            "keywords_custom": "홍시에이드, 신메뉴 출시 ,오픈 1주년",
        },
    )
    assert 'value="홍시에이드, 신메뉴 출시 ,오픈 1주년"' in res.text  # 입력값이 칸에 남는다
    with factory() as s:
        saved = s.query(MarketingContent).one()
    assert saved.keywords == "신메뉴 출시, 홍시에이드, 오픈 1주년"  # 중복 없이 합쳐짐
