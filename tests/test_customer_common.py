# AI-assisted (Claude)
"""고객 화면 공통: 하단 매장 정보, 탭 아이콘, 없는 페이지 안내, 예약 신청 완료 화면."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import database
from app.db.database import Base, get_session
from app.db.seed import load_all
from app.main import app

HTML = {"accept": "text/html,application/xhtml+xml"}


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as s:
        load_all(s)
        s.commit()
    monkeypatch.setattr(database, "SessionLocal", factory)

    def _session():
        with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.parametrize("url", ["/", "/reservations/new", "/inquiries/lookup"])
def test_footer_on_every_customer_page(client, url):
    page = client.get(url).text
    assert "data-footer" in page and "02-333-7742" in page and "월요일 휴무" in page


def test_favicon(client):
    res = client.get("/favicon.ico")
    assert res.status_code == 200 and res.headers["content-type"].startswith("image/svg+xml")


def test_not_found_page_for_browser_but_json_for_api(client):
    page = client.get("/no-such-page", headers=HTML)
    assert page.status_code == 404 and "페이지를 찾을 수 없어요" in page.text
    assert 'href="/"' in page.text
    owner = client.get("/owner/reservations/99999", headers=HTML)
    assert owner.status_code == 404 and 'href="/owner"' in owner.text
    api = client.get("/no-such-page")  # 브라우저가 아니면 JSON 그대로
    assert api.status_code == 404 and api.json() == {"detail": "Not Found"}


def test_reservation_done_page(client):
    data = {
        "store_id": "1",
        "name": "홍길동",
        "phone": "01099990000",
        "visit_date": "2099-12-01",
        "visit_time": "12:00",
        "party_size": "2",
        "request": "창가 자리",
    }
    page = client.post("/reservations", data=data).text
    assert "예약 신청이 접수되었어요" in page and "예약 번호" not in page
    assert "12/01(화)" in page and "12:00 · 2명" in page and "창가 자리" in page
    assert 'action="/reservations/lookup"' in page and 'value="010-9999-0000"' in page
    assert 'name="name" value="홍길동"' in page  # 이름도 같이 넘겨 바로 조회


def test_footer_sticks_to_bottom_on_short_pages():
    """짧은 페이지에서도 푸터가 화면 맨 아래에 붙는다 (11/24)."""
    with TestClient(app) as client:
        page = client.get("/reservations/lookup").text
    assert 'class="d-flex flex-column min-vh-100"' in page
    assert "flex-grow-1" in page.split("<main")[1].split(">")[0]
    assert 'class="border-top bg-white mt-auto" data-footer' in page
