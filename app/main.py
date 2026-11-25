"""앱 진입점. 실행: uvicorn app.main:app --reload"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.db.database import init_db
from app.db.seed import seed
from app.presentation.routers import customer, inquiry, marketing, owner, reservation
from app.presentation.templating import templates
from app.services.store.menu_photo import STATIC_DIR


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    seed()  # 데이터 없을 때만 자동 적재 (중복 삽입 없음)
    yield


app = FastAPI(title="소상공인 AI 마케팅·고객응대 시스템", lifespan=lifespan)

app.include_router(customer.router)
app.include_router(owner.router)
app.include_router(inquiry.router)
app.include_router(marketing.router)
app.include_router(reservation.router)
# 메뉴 사진 등 정적 파일 (app/presentation/static)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 브라우저 탭 아이콘 (☕). 없으면 브라우저가 매번 /favicon.ico를 찾다가 404가 난다.
FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    '<text y=".9em" font-size="90">☕</text></svg>'
)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(FAVICON_SVG, media_type="image/svg+xml")


@app.exception_handler(StarletteHTTPException)
async def friendly_not_found(request: Request, exc: StarletteHTTPException):
    """브라우저로 없는 화면에 들어오면 안내 화면을 보여 준다. API 호출은 원래대로 JSON."""
    if exc.status_code == 404 and "text/html" in request.headers.get("accept", ""):
        owner_page = request.url.path.startswith("/owner")
        return templates.TemplateResponse(
            request, "not_found.html", {"home": "/owner" if owner_page else "/"}, status_code=404
        )
    return await http_exception_handler(request, exc)
