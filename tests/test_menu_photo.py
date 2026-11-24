# AI-assisted (Claude)
"""점주 메뉴 사진 올리기·바꾸기·지우기 (F-01 메뉴 관리, 11/24)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_session
from app.db.seed import load_all
from app.main import app
from app.models.models import MenuItem
from app.services.store import menu_photo as photos
from app.services.store.menu_photo import MenuPhotoError, menu_photo, save_menu_photo

JPG = b"\xff\xd8\xff\xe0" + b"0" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


@pytest.fixture(autouse=True)
def photo_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(photos, "MENU_PHOTO_DIR", tmp_path)
    return tmp_path


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
def client(factory):
    def _session():
        with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_save_replaces_old_photo_and_blocks_bad_files(photo_dir):
    save_menu_photo("홍시에이드", "a.jpg", JPG)
    save_menu_photo("홍시에이드", "b.PNG", PNG)  # 바꾸면 예전 jpg는 지운다
    assert sorted(p.name for p in photo_dir.iterdir()) == ["홍시에이드.png"]
    for filename, data in (("x.gif", JPG), ("x.jpg", b"not image"), ("x.jpg", b"")):
        with pytest.raises(MenuPhotoError):
            save_menu_photo("홍시에이드", filename, data)
    with pytest.raises(MenuPhotoError):
        save_menu_photo("홍시에이드", "big.jpg", JPG + b"0" * photos.MAX_PHOTO_BYTES)


def test_menu_name_cannot_escape_photo_folder(photo_dir):
    save_menu_photo("../../evil", "a.jpg", JPG)
    assert [p.parent for p in photo_dir.iterdir()] == [photo_dir]


def test_uploaded_photo_wins_over_sample_photo(photo_dir):
    (photo_dir / "americano.jpg").write_bytes(JPG)  # 가상 데이터 사진
    assert menu_photo("아메리카노") == "/static/menu/americano.jpg"
    save_menu_photo("아메리카노", "mine.png", PNG)  # 점주가 새로 올린 사진
    assert menu_photo("아메리카노").endswith(".png")


def test_owner_adds_menu_with_photo_and_customer_sees_it(client, photo_dir):
    res = client.post(
        "/owner/menus",
        data={"name": "홍시에이드", "price": "6500", "description": "겨울 한정"},
        files={"photo": ("hongsi.jpg", JPG, "image/jpeg")},
    )
    assert res.status_code == 200 and "data-photo-error" not in res.text
    assert (photo_dir / "홍시에이드.jpg").is_file()
    assert 'alt="홍시에이드"' in res.text  # 메뉴 목록 썸네일
    assert 'alt="홍시에이드"' in client.get("/").text  # 손님 화면 카드


def test_owner_menu_without_photo_still_added(client, factory):
    client.post("/owner/menus", data={"name": "아이스티", "price": "4000"})
    with factory() as s:
        assert s.query(MenuItem).filter_by(name="아이스티").count() == 1


def test_owner_bad_photo_shows_error(client, factory):
    res = client.post(
        "/owner/menus",
        data={"name": "홍시에이드", "price": "6500"},
        files={"photo": ("doc.pdf", b"%PDF", "application/pdf")},
    )
    assert "jpg, png, webp 파일만" in res.text  # 메뉴는 추가되고 사진만 안내
    with factory() as s:
        assert s.query(MenuItem).filter_by(name="홍시에이드").count() == 1


def test_owner_change_and_delete_photo(client, factory, photo_dir):
    with factory() as s:
        mid = s.query(MenuItem).filter_by(name="브라우니").one().id
    client.post(f"/owner/menus/{mid}/photo", files={"photo": ("b.png", PNG, "image/png")})
    assert menu_photo("브라우니").endswith(".png")
    client.post(f"/owner/menus/{mid}/photo/delete")
    assert menu_photo("브라우니") is None
    assert client.post("/owner/menus/99999/photo/delete").status_code == 404


def test_deleting_menu_removes_photo(client, factory, photo_dir):
    with factory() as s:
        mid = s.query(MenuItem).filter_by(name="브라우니").one().id
    client.post(f"/owner/menus/{mid}/photo", files={"photo": ("b.jpg", JPG, "image/jpeg")})
    client.post(f"/owner/menus/{mid}/delete")
    assert list(photo_dir.iterdir()) == []
