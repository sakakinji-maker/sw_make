"""홍보 문구 저장·목록 조회 Repository 테스트 (F-04-3)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.models import MarketingContent, Store
from app.repositories.marketing_repository import (
    list_marketing_contents,
    save_marketing_content,
)


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_save_and_list_marketing_contents():
    session = make_session()
    store = Store(
        name="테스트 매장",
        category="카페",
        address="서울",
        phone="02-000-0000",
        open_time=__import__("datetime").time(9, 0),
        close_time=__import__("datetime").time(21, 0),
    )
    session.add(store)
    session.commit()

    saved = save_marketing_content(
        session=session,
        store_id=store.id,
        channel="instagram",
        target="20대",
        keywords=["커피", "신메뉴"],
        text="신메뉴가 나왔어요! #커피 #신메뉴 #카페",
        check_result=[],
    )

    results = list_marketing_contents(session, store.id)

    assert saved.id is not None
    assert saved.keywords == "커피, 신메뉴"
    assert results == [saved]
    assert results[0].check_result == "[]"
    session.close()
