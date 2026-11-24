# AI-assisted (Claude)
"""점주 화면 개선: 상단 메뉴, 대시보드 오늘 예약·확정 대기, 예약 탭, 문의함 탭, 최근 고객."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import database
from app.db.database import Base, get_session
from app.db.seed import load_all
from app.main import app
from app.models.models import Customer, Inquiry, Reservation
from app.presentation.routers.reservation import get_service
from app.services.reservation.service import ReservationService

NOW = datetime(2026, 11, 20, 9, 0)  # 가상 데이터: 11/10~11/22 예약, 12/25~12/31 예약


@pytest.fixture
def factory(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    f = sessionmaker(bind=engine)
    with f() as s:
        load_all(s)
        s.commit()
    monkeypatch.setattr(database, "SessionLocal", f)
    return f


@pytest.fixture
def client(factory):
    def _session():
        with factory() as s:
            yield s

    def _service():
        with factory() as s:
            yield ReservationService(s, now=lambda: NOW)

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_service] = _service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_owner_nav_collapses_and_highlights(client):
    page = client.get("/owner/reservations").text
    nav = page.split("</nav>")[0]
    assert "navbar-toggler" in nav and 'id="ownerNav"' in nav
    assert 'class="nav-link active" href="/owner/reservations"' in nav
    assert "<title>예약 관리 — 브루밍 카페 관리</title>" in page


def test_dashboard_today_and_pending(client, factory):
    today = datetime.now().replace(hour=23, minute=0, second=0, microsecond=0)
    with factory() as s:
        s.add(
            Reservation(
                store_id=1,
                customer=Customer(name="오늘손님", phone="010-3333-0000"),
                reserved_at=today,
                party_size=2,
                status="요청",
            )
        )
        s.commit()
    page = client.get("/owner").text
    assert 'data-card="today"' in page and 'data-card="pending"' in page
    today_list = page.split("data-today-list")[1].split("</section>")[0]
    assert "오늘손님" in today_list and "23:00" in today_list
    assert 'href="/owner/reservations?status=요청"' in page


def test_reservation_tabs(client):
    upcoming = client.get("/owner/reservations").text
    assert "서지우" in upcoming and "김하늘" not in upcoming  # 12/25는 보이고 11월 중순은 안 보임
    assert "<th>번호</th>" not in upcoming and '<select name="store_id"' not in upcoming
    past = client.get("/owner/reservations?view=past").text
    assert "김하늘" in past and "12/25" not in past
    assert past.index("11/19") < past.index("11/10")  # 지난 예약은 최근 순
    pending = client.get("/owner/reservations?status=요청").text
    assert "방문완료</span>" not in pending


def test_inquiry_tabs(client, factory):
    with factory() as s:
        q = s.get(Inquiry, 1)
        q.status, q.final_answer = "답변완료", "4,500원입니다."
        s.commit()
        total = s.query(Inquiry).count()
    unanswered = client.get("/owner/inquiries").text
    assert unanswered.count("data-inquiry-row") == total - 1
    answered = client.get("/owner/inquiries?tab=answered").text
    assert answered.count("data-inquiry-row") == 1


def test_recent_customers_and_digit_search(client):
    page = client.get("/owner/customers").text
    assert "data-recent-customers" in page
    # 예약 많은 순: 단골 김서연(예약 7건·방문 5회)이 예약 1건 손님보다 위
    assert page.index("김서연") < page.index("하시우")
    first = page.split("data-customer-row")[1].split("</tr>")[0]
    assert "김서연" in first and 'data-badge="regular"' in first
    no_show = page.split("윤성민")[1].split("</tr>")[0]
    assert 'data-badge="no-show"' in no_show  # 노쇼 3회 → 노쇼 주의
    found = client.get("/owner/customers?phone=01000000101").text
    assert "김하늘" in found and "data-customer-summary" in found


def test_customer_search_by_name_or_last_digits(client):
    """점주 고객 찾기: 이름 일부, 번호 뒤 4자리, 전체 번호 (11/24)."""
    for q in ("김하늘", "김 하늘", "0101", "010-0000-0101", "01000000101"):
        res = client.get(f"/owner/customers?q={q}", follow_redirects=False)
        assert res.status_code == 303, q  # 한 명이면 바로 그 손님 이력으로
        assert "phone=010-0000-0101" in res.headers["location"], q
    many = client.get("/owner/customers?q=김").text  # 김서연·김하늘…
    assert "data-search-result" in many and many.count("data-customer-row") >= 2
    assert "김서연" in many and "윤성민" not in many
    none = client.get("/owner/customers?q=없는사람").text
    assert "없는사람" in none and "에 맞는 고객이 없습니다." in none


def test_sidebar_counts_and_dashboard_charts(client):
    page = client.get("/owner").text
    nav = page.split('id="ownerNav"')[1].split("</nav>")[0]
    assert "data-count" in nav  # 확정 대기·미응답 문의 숫자 배지
    assert "data-timeline" in page and "data-week" in page
    assert page.count('class="week-col') == 7  # 오늘부터 7일


def test_inquiries_newest_first(client, factory):
    with factory() as s:
        s.add(
            Inquiry(
                store_id=1,
                customer=Customer(name="최신손님", phone="010-4444-0000"),
                content="가장 최근 문의예요",
                received_at=datetime(2026, 11, 24, 15, 0),
            )
        )
        s.commit()
    page = client.get("/owner/inquiries").text
    assert page.index("가장 최근 문의예요") < page.index("아메리카노 한 잔 얼마예요?")


def test_timeline_groups_same_time_reservations(client, factory):
    """오늘 같은 시각 예약 2건은 점 하나에 '2'로 보인다 (점이 겹쳐 1건처럼 보이던 문제)."""
    from datetime import datetime as dt

    from app.models.models import Customer, Reservation, Store

    at = dt.now().replace(hour=20, minute=30, second=0, microsecond=0)
    with factory() as s:
        store = s.get(Store, 1)
        for name in ("같은시각1", "같은시각2"):
            s.add(Reservation(store=store, customer=Customer(name=name, phone="010-9999-0000"),
                              reserved_at=at, party_size=2, status="확정"))
        s.commit()
    page = client.get("/owner").text
    dots = [d for d in page.split("data-timeline-dot")[1:] if "같은시각1" in d]
    assert len(dots) == 1 and "같은시각2" in dots[0]
    assert ">2</span>" in dots[0]


def test_week_bar_links_to_that_day(client, factory):
    """대시보드 7일 그래프 막대를 누르면 그날 예약만 보인다 (11/24)."""
    from datetime import date as d
    from datetime import datetime as dt
    from datetime import timedelta as td

    from app.models.models import Customer, Reservation, Store

    day = d.today() + td(days=3)
    with factory() as s:
        store = s.get(Store, 1)
        for name, offset in (("그날손님", 0), ("다음날손님", 1)):
            at = dt.combine(day + td(days=offset), dt.min.time()).replace(hour=15)
            s.add(Reservation(store=store, customer=Customer(name=name, phone="010-9999-1111"),
                              reserved_at=at, party_size=2, status="요청"))
        s.commit()
    assert f'href="/owner/reservations?day={day.isoformat()}"' in client.get("/owner").text
    page = client.get(f"/owner/reservations?day={day.isoformat()}").text
    assert "data-day-filter" in page and "그날손님" in page and "다음날손님" not in page
    assert "data-day-filter" not in client.get("/owner/reservations?day=잘못된값").text


def test_reservation_list_has_date_picker_and_day_arrows(client):
    page = client.get("/owner/reservations").text
    assert 'type="date" name="day"' in page and "data-day-filter" not in page
    page = client.get("/owner/reservations?day=2026-12-12&status=요청").text
    assert 'value="2026-12-12"' in page  # 고른 날짜가 입력칸에 남는다
    assert "day=2026-12-11&status=요청" in page and "day=2026-12-13&status=요청" in page  # ‹ ›


def test_customer_filters_regular_and_no_show(client):
    """고객 이력: 단골·노쇼 손님만 골라 보기 (11/24)."""
    page = client.get("/owner/customers").text
    assert "data-customer-filters" in page and "?only=no_show" in page
    regular = client.get("/owner/customers?only=regular").text
    rows = regular.split("data-customer-row")[1:]
    assert rows and all('data-badge="regular"' in r.split("</tr>")[0] for r in rows)
    no_show = client.get("/owner/customers?only=no_show").text
    rows = no_show.split("data-customer-row")[1:]
    assert all('data-badge="no-show"' in r.split("</tr>")[0] for r in rows)
    assert "윤성민" in rows[0] and "김서연" not in no_show.split("data-recent-customers")[1]
    assert "한재형" in no_show  # 11/11·11/13 노쇼 2회 (가상 데이터)


def test_unknown_customer_filter_shows_all(client):
    page = client.get("/owner/customers?only=이상한값").text
    assert page.count("data-customer-row") == client.get("/owner/customers").text.count(
        "data-customer-row"
    )


def test_owner_sidebar_has_no_customer_link(client):
    """점주 메뉴에서 '고객 화면 보기' 링크는 뺐다 (11/24)."""
    nav = client.get("/owner").text.split('id="ownerNav"')[1].split("</nav>")[0]
    assert "고객 화면 보기" not in nav
