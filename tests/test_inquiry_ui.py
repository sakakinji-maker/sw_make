# AI-assisted (Claude)
"""문의하기·내 문의 화면 UI: 매장 선택 제거, 예시·문자 안내, 글자 수, FAQ 안내, 카드 머리글."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters.ai.mock_adapter import MockAIClient
from app.db.database import Base, get_session
from app.db.seed import load_all
from app.main import app
from app.presentation.routers.inquiry import get_ai


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

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_ai] = MockAIClient
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_inquiry_form_layout(client):
    page = client.get("/inquiries/new").text
    assert '<select id="store_id"' not in page and 'type="hidden" name="store_id"' in page
    assert "답변이 등록되면 문자로 알려 드려요" in page
    assert 'href="/#faq"' in page and 'id="contentCount"' in page
    assert "예: 10명 단체 예약 가능한가요?" in page


def test_lookup_cards_and_empty_state(client):
    sent = {"store_id": "1", "name": "홍길동", "phone": "01099990000", "content": "주차 되나요?"}
    done = client.post("/inquiries", data=sent).text
    assert "문자로 알려 드려요" in done and "접수 번호" not in done
    assert 'name="name" value="홍길동"' in done  # 내 문의 확인 버튼이 이름도 넘긴다
    page = client.post("/inquiries/lookup", data={"phone": "01099990000", "name": "홍길동"}).text
    assert "data-inquiry" in page and "답변 대기" in page
    assert "접수 번호" not in page
    empty = client.post("/inquiries/lookup", data={"phone": "010-5555-4444", "name": "홍길동"}).text
    assert "data-empty" in empty and 'href="/inquiries/new"' in empty


def test_home_has_faq_anchor(client):
    assert 'id="faq"' in client.get("/").text


def test_lookup_requires_name(client):
    page = client.post("/inquiries/lookup", data={"phone": "010-0000-0101", "name": " "})
    assert page.status_code == 400 and "이름을(를) 입력해 주세요" in page.text
