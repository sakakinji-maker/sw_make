# AI-assisted (Claude)
"""고객 첫 화면 UI 개선 테스트: 예약·문의 버튼 위치, 영업 상태, 메뉴 분류, FAQ 더보기, 매장 이름."""

from datetime import datetime, time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import database
from app.db.database import Base, get_session
from app.db.seed import load_all
from app.main import app
from app.presentation.routers.customer import menu_icon, open_status, split_menus

CAFE = SimpleNamespace(open_time=time(9), close_time=time(21), closed_days="월")


@pytest.mark.parametrize(
    ("now", "label"),
    [
        (datetime(2026, 11, 23, 12, 0), "오늘 휴무 (월)"),  # 월요일
        (datetime(2026, 11, 24, 8, 59), "영업 전 · 09:00 오픈"),
        (datetime(2026, 11, 24, 9, 0), "영업 중 · 21:00까지"),  # 경계: 오픈 시각
        (datetime(2026, 11, 24, 20, 59), "영업 중 · 21:00까지"),
        (datetime(2026, 11, 24, 21, 0), "오늘 영업 종료"),  # 경계: 마감 시각
    ],
)
def test_open_status(now, label):
    assert open_status(CAFE, now).label == label


def test_split_menus_into_drinks_and_desserts():
    names = ["아메리카노", "치즈케이크", "크루아상", "자몽에이드", "브라우니"]
    drinks, desserts = split_menus([SimpleNamespace(name=n) for n in names])
    assert [m.name for m in drinks] == ["아메리카노", "자몽에이드"]
    assert [m.name for m in desserts] == ["치즈케이크", "크루아상", "브라우니"]


@pytest.fixture
def page(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as s:
        load_all(s)
        s.commit()
    monkeypatch.setattr(database, "SessionLocal", factory)  # 상단 매장 이름도 같은 DB에서 읽게

    def _session():
        with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    try:
        yield TestClient(app).get("/").text
    finally:
        app.dependency_overrides.clear()


def test_actions_come_before_menu_and_faq(page):
    assert page.index("data-actions") < page.index("data-menu-group") < page.index("자주 묻는 질문")
    for link in (
        "/reservations/new",
        "/inquiries/new",
        "/reservations/lookup",
        "/inquiries/lookup",
    ):
        assert f'href="{link}"' in page


def test_brand_is_store_name_not_system_name(page):
    assert "☕ 브루밍 카페" in page
    assert "AI 마케팅·고객응대" not in page


def test_menu_groups_and_status_badge(page):
    assert ">음료<" in page and ">디저트<" in page
    assert "data-open-status" in page


def test_faq_shows_five_then_more_button(page):
    faq = page.split('id="faqAccordion"')[1].split("faqMoreBtn")[0]
    assert faq.count('class="accordion-item"') == 5  # 처음엔 5개만 보이고
    assert faq.count("data-faq-extra") == 15  # 나머지 15개는 숨김
    assert "질문 15개 더보기" in page  # 가상 데이터 FAQ 20개
    # 더보기를 접히는 칸(collapse)으로 감싸지 않는다: 질문을 펼 때 더보기가 같이 닫히던 문제
    assert 'id="faqMore"' not in page


def test_mobile_nav_collapses(page):
    assert "navbar-toggler" in page and 'id="customerNav"' in page


def test_nav_highlights_current_page():
    with TestClient(app) as client:
        nav = client.get("/reservations/lookup").text.split("</nav>")[0]
    assert 'customer-nav-link active" href="/reservations/lookup"' in nav
    assert 'customer-nav-link active" href="/inquiries/new"' not in nav


@pytest.mark.parametrize(
    ("name", "icon"),
    [
        ("아메리카노", "☕"),
        ("카페라떼", "☕"),
        ("밤라떼", "🌰"),
        ("말차라떼", "🍵"),
        ("딸기스무디", "🍓"),
        ("자몽에이드", "🍊"),
        ("핫초코", "🍫"),
        ("크루아상", "🥐"),
        ("치즈케이크", "🍰"),
        ("브라우니", "🍫"),
        ("새로운 메뉴", "☕"),  # 모르는 이름은 기본 아이콘
    ],
)
def test_menu_icon(name, icon):
    assert menu_icon(name) == icon


def test_menu_cards_show_photos(page):
    """메뉴 12개 모두 사진이 있다 (Gemini 생성 이미지, 11/24). 없으면 이모지로 대신한다."""
    assert page.count("data-menu-photo") == 12 and 'class="menu-icon' not in page
    assert 'src="/static/menu/americano.jpg"' in page and "data-store-hero" in page


def test_menu_photo_replaces_icon_when_file_exists(tmp_path, monkeypatch):
    """메뉴 이름과 같은 사진 파일이 있으면 이모지 대신 사진을 보여 준다 (11/24)."""
    from urllib.parse import quote

    from app.presentation.routers import customer
    from app.services.store import menu_photo as photos

    monkeypatch.setattr(photos, "MENU_PHOTO_DIR", tmp_path)
    assert customer.menu_photo("아메리카노") is None and customer.menu_icon("유자차") == "🍋"
    (tmp_path / "얼그레이 케이크.jpg").write_bytes(b"jpg")
    assert customer.menu_photo("얼그레이 케이크") == "/static/menu/" + quote("얼그레이 케이크.jpg")
    (tmp_path / "americano.png").write_bytes(b"png")  # 영문 파일명도 찾는다
    assert customer.menu_photo("아메리카노") == "/static/menu/americano.png"
    with TestClient(app) as client:
        page = client.get("/").text
    assert 'alt="아메리카노"' in page and 'alt="카페라떼"' not in page


def test_menu_card_comes_from_db_and_shows_sold_out():
    """메뉴 카드의 이름·가격은 DB 값이고, 판매 중지 메뉴는 '품절'로 흐리게 보인다 (11/24)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db.database import Base, get_session
    from app.db.seed import load_all
    from app.models.models import MenuItem

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as s:
        load_all(s)
        menu = s.query(MenuItem).filter_by(name="브라우니").one()
        menu.price, menu.on_sale = 5300, False
        s.commit()

    def _session():
        with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    try:
        page = TestClient(app).get("/").text
    finally:
        app.dependency_overrides.clear()
    card = page.split('alt="브라우니"')[1].split("</div>\n  </div>")[0]
    assert "5,300원" in card and "품절" in card
    assert page.count("data-soldout") == 1
