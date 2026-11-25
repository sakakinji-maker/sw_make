# AI-assisted (Claude) — 정회성 검토 완료
"""가상 데이터 적재 스크립트. `app/db/seed_data/*.json`을 읽어 DB에 넣는다.

실행:
    python -m app.db.seed           # 데이터가 없을 때만 적재
    python -m app.db.seed --reset   # 테이블을 비우고 다시 적재

파일 형식은 `app/db/seed_data/README.md` 참고. 없는 파일은 건너뛴다.
"""

import json
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.database import Base, SessionLocal, create_tables, engine
from app.models.models import (
    FAQ,
    Customer,
    Inquiry,
    MarketingContent,
    MenuItem,
    Reservation,
    ReservationHistory,
    Store,
)

DATA_DIR = Path(__file__).parent / "seed_data"

# 가상 예약의 상태 변경 이력 (11/24). 이력이 없으면 상세 화면에 '이력이 없습니다'만 보여 어색하다.
# 최종 상태까지 거쳐 온 단계. 손님 취소는 '요청'에서, 노쇼·방문완료는 '확정'에서 바뀐다.
STATUS_PATH = {
    "요청": ["요청"],
    "확정": ["요청", "확정"],
    "방문완료": ["요청", "확정", "방문완료"],
    "노쇼": ["요청", "확정", "노쇼"],
    "취소": ["요청", "취소"],
}
# 예약을 신청한 시각이 이 시각보다 뒤가 되지 않게 한다 (발표 전 미래에 신청한 것처럼 보이지 않게)
SEED_NOW = datetime(2026, 11, 23, 20, 0)


def history_rows(reserved_at: datetime, status: str, index: int) -> list[tuple[str, str, datetime]]:
    """(이전 상태, 바뀐 상태, 시각) 목록. 신청 → 확정 → 방문 순으로 시각이 흐르게 만든다."""
    requested = min(reserved_at - timedelta(days=3), SEED_NOW) - timedelta(minutes=17 * (index % 7))
    times = {
        "요청": requested,
        "확정": requested + timedelta(hours=2, minutes=index % 40),
        "취소": requested + timedelta(days=1),
        "방문완료": reserved_at + timedelta(hours=1, minutes=30),
        "노쇼": reserved_at + timedelta(minutes=30),
    }
    path = STATUS_PATH.get(status, ["요청"])
    froms = ["신규", *path[:-1]]
    return [(f, t, times[t]) for f, t in zip(froms, path, strict=True)]


class SeedDataError(Exception):
    """가상 데이터 파일의 형식이나 참조가 잘못되었을 때."""


def read_json(data_dir: Path, name: str) -> list[dict[str, Any]]:
    """`name.json`을 읽는다. 파일이 없으면 빈 리스트."""
    path = data_dir / f"{name}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


class SeedLoader:
    """JSON 데이터를 모델 객체로 바꿔 세션에 추가한다."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.stores: dict[str, Store] = {}
        self.customers: dict[str, Customer] = {}

    def store(self, key: str) -> Store:
        if key not in self.stores:
            raise SeedDataError(f"stores.json에 없는 매장 키: {key}")
        return self.stores[key]

    def customer(self, info: dict[str, str]) -> Customer:
        """연락처 기준으로 고객을 재사용한다. 처음 보는 연락처면 새로 만든다."""
        phone = info["phone"]
        if phone not in self.customers:
            self.customers[phone] = Customer(name=info["name"], phone=phone)
            self.session.add(self.customers[phone])
        return self.customers[phone]

    def load_stores(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            store = Store(
                name=row["name"],
                category=row["category"],
                address=row["address"],
                open_time=time.fromisoformat(row["open_time"]),
                close_time=time.fromisoformat(row["close_time"]),
                closed_days=row.get("closed_days", ""),
                phone=row["phone"],
                capacity_per_hour=row.get("capacity_per_hour", 10),
            )
            store.menu_items = [MenuItem(**item) for item in row.get("menu", [])]
            self.session.add(store)
            self.stores[row["key"]] = store

    def load_customers(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            self.customer(row)

    def load_faqs(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            self.session.add(
                FAQ(store=self.store(row["store"]), question=row["question"], answer=row["answer"])
            )

    def load_inquiries(self, rows: list[dict[str, Any]]) -> None:
        """검증용 필드(category, expected 등)는 DB에 넣지 않고 JSON에만 남긴다."""
        for row in rows:
            self.session.add(
                Inquiry(
                    store=self.store(row["store"]),
                    customer=self.customer(row["customer"]),
                    content=row["content"],
                    received_at=datetime.fromisoformat(row["received_at"]),
                    status=row.get("status", "미응답"),
                )
            )

    def load_reservations(self, rows: list[dict[str, Any]]) -> None:
        for index, row in enumerate(rows):
            reserved_at = datetime.fromisoformat(row["reserved_at"])
            status = row.get("status", "요청")
            reservation = Reservation(
                store=self.store(row["store"]),
                customer=self.customer(row["customer"]),
                reserved_at=reserved_at,
                party_size=row["party_size"],
                request=row.get("request", ""),
                status=status,
            )
            for from_status, to_status, at in history_rows(reserved_at, status, index):
                reservation.histories.append(
                    ReservationHistory(from_status=from_status, to_status=to_status, changed_at=at)
                )
            self.session.add(reservation)

    def load_contents(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            self.session.add(
                MarketingContent(
                    store=self.store(row["store"]),
                    channel=row["channel"],
                    target=row["target"],
                    keywords=", ".join(row.get("keywords", [])),
                    text=row["text"],
                )
            )


def load_all(session: Session, data_dir: Path = DATA_DIR) -> dict[str, int]:
    """모든 JSON을 순서대로 적재하고 파일별 건수를 돌려준다. 커밋은 호출한 쪽에서 한다."""
    loader = SeedLoader(session)
    steps = [
        ("stores", loader.load_stores),
        ("customers", loader.load_customers),
        ("faqs", loader.load_faqs),
        ("inquiries", loader.load_inquiries),
        ("reservations", loader.load_reservations),
        ("contents", loader.load_contents),
    ]
    counts = {}
    for name, load in steps:
        rows = read_json(data_dir, name)
        load(rows)
        counts[name] = len(rows)
    return counts


def seed(reset: bool = False) -> None:
    create_tables()
    if reset:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        if not reset and session.query(Store).count() > 0:
            print("이미 데이터가 있습니다. 다시 넣으려면 --reset 을 붙이세요.")
            return
        counts = load_all(session)
        session.commit()
    print("가상 데이터 적재 완료:", ", ".join(f"{k} {v}건" for k, v in counts.items()))


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
