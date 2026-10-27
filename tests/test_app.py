"""앱이 뜨고 기본 화면이 열리는지 확인."""

from fastapi.testclient import TestClient

from app.main import app


def test_pages_open():
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/owner").status_code == 200
