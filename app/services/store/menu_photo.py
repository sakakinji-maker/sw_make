# AI-assisted (Claude)
"""메뉴 사진 파일 관리 (F-01 메뉴 관리, 11/24).

사진은 DB가 아니라 app/presentation/static/menu 폴더에 '메뉴 이름.확장자'로 둔다.
DB에는 사진 칸이 없어서, 메뉴 이름으로 파일을 찾는다. (DB 구조를 바꾸지 않으려는 선택)
"""

import re
from pathlib import Path
from urllib.parse import quote

STATIC_DIR = Path(__file__).resolve().parents[2] / "presentation" / "static"
MENU_PHOTO_DIR = STATIC_DIR / "menu"
PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5MB

# 가상 데이터 메뉴의 사진 파일명 (영문으로 두어 압축·윈도우에서 한글 파일명이 깨지지 않게)
MENU_PHOTO_FILES = {
    "아메리카노": "americano",
    "카페라떼": "cafe-latte",
    "밤라떼": "chestnut-latte",
    "말차라떼": "matcha-latte",
    "딸기스무디": "strawberry-smoothie",
    "자몽에이드": "grapefruit-ade",
    "핫초코": "hot-chocolate",
    "유자차": "yuja-tea",
    "크루아상": "croissant",
    "치즈케이크": "cheesecake",
    "브라우니": "brownie",
    "얼그레이 케이크": "earl-grey-cake",
}

# 파일 앞부분으로 진짜 이미지인지 확인한다 (확장자만 바꾼 다른 파일 차단)
_SIGNATURES = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".webp": (b"RIFF",),
}


class MenuPhotoError(ValueError):
    """올릴 수 없는 사진 (형식·크기)."""


def _stem(name: str) -> str:
    """메뉴 이름을 파일 이름으로. 경로를 바꿀 수 있는 글자(/ \\ .. 등)는 _로 바꾼다."""
    return re.sub(r'[\\/:*?"<>|.]', "_", name).strip() or "_"


def _files_for(name: str) -> list[Path]:
    stems = [_stem(name)]
    if name in MENU_PHOTO_FILES:
        stems.append(MENU_PHOTO_FILES[name])
    return [MENU_PHOTO_DIR / f"{s}{ext}" for s in stems for ext in PHOTO_EXTENSIONS]


def menu_photo(name: str) -> str | None:
    """메뉴 사진 주소. 점주가 올린 사진(메뉴 이름) → 가상 데이터 사진(영문 이름) 순서로 찾는다.

    사진 파일이 없으면 None (화면은 이모지로 대신한다).
    """
    for path in _files_for(name):
        if path.is_file():
            return f"/static/menu/{quote(path.name)}"
    return None


def save_menu_photo(name: str, filename: str, data: bytes) -> str:
    """사진을 저장하고 주소를 돌려준다. 같은 메뉴의 예전 사진은 지운다."""
    ext = Path(filename or "").suffix.lower()
    if ext not in PHOTO_EXTENSIONS:
        raise MenuPhotoError("사진은 jpg, png, webp 파일만 올릴 수 있어요.")
    if not data:
        raise MenuPhotoError("빈 파일이에요. 사진을 다시 골라 주세요.")
    if len(data) > MAX_PHOTO_BYTES:
        raise MenuPhotoError("사진이 너무 커요. 5MB 이하로 올려 주세요.")
    if not data.startswith(_SIGNATURES[ext]):
        raise MenuPhotoError("사진 파일이 아니에요. jpg, png, webp 사진을 골라 주세요.")
    delete_menu_photo(name)
    MENU_PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    path = MENU_PHOTO_DIR / f"{_stem(name)}{ext}"
    path.write_bytes(data)
    return f"/static/menu/{quote(path.name)}"


def delete_menu_photo(name: str) -> bool:
    """메뉴 사진을 지운다. 지운 게 있으면 True."""
    removed = False
    for path in _files_for(name):
        if path.is_file():
            path.unlink()
            removed = True
    return removed
