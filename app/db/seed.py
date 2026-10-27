"""가상 데이터를 DB에 넣는 스크립트. (11주차 담당: 각자 엔티티 분량)

실행: python -m app.db.seed
"""

from datetime import time

from app.db.database import SessionLocal, init_db
from app.models.models import FAQ, MenuItem, Store


def seed() -> None:
    init_db()
    with SessionLocal() as session:
        if session.query(Store).count() > 0:
            print("이미 데이터가 있습니다. 건너뜁니다.")
            return

        store = Store(
            name="온기 카페",
            category="카페",
            address="서울시 OO구 OO로 12",
            open_time=time(9, 0),
            close_time=time(21, 0),
            closed_days="월",
            phone="02-000-0000",
            capacity_per_hour=10,
        )
        store.menu_items = [
            MenuItem(name="아메리카노", price=4500, description="고소한 원두"),
            MenuItem(name="카페라떼", price=5000, description="우유 듬뿍"),
        ]
        store.faqs = [
            FAQ(question="주차 되나요?", answer="건물 뒤편에 2대 주차 가능합니다."),
        ]
        session.add(store)
        session.commit()
        print("가상 데이터 적재 완료")
        # TODO: 생성형 AI로 만든 가상 데이터(JSON)를 읽어 메뉴 10~15개, 고객 30명,
        #       예약 50건, 문의 30건, FAQ 10개를 채운다.


if __name__ == "__main__":
    seed()
