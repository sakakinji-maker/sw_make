"""주요 엔티티 정의. (기획서 9절)"""

from datetime import datetime, time

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50))
    address: Mapped[str] = mapped_column(String(200))
    open_time: Mapped[time]
    close_time: Mapped[time]
    closed_days: Mapped[str] = mapped_column(String(50), default="")  # 예: "월,화"
    phone: Mapped[str] = mapped_column(String(30))
    capacity_per_hour: Mapped[int] = mapped_column(default=10)

    menu_items: Mapped[list["MenuItem"]] = relationship(back_populates="store")
    faqs: Mapped[list["FAQ"]] = relationship(back_populates="store")
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="store")
    inquiries: Mapped[list["Inquiry"]] = relationship(back_populates="store")
    contents: Mapped[list["MarketingContent"]] = relationship(back_populates="store")


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[int]
    description: Mapped[str] = mapped_column(String(300), default="")
    on_sale: Mapped[bool] = mapped_column(default=True)

    store: Mapped[Store] = relationship(back_populates="menu_items")


class FAQ(Base):
    __tablename__ = "faqs"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    question: Mapped[str] = mapped_column(String(300))
    answer: Mapped[str] = mapped_column(Text)

    store: Mapped[Store] = relationship(back_populates="faqs")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    phone: Mapped[str] = mapped_column(String(30))


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    reserved_at: Mapped[datetime]
    party_size: Mapped[int]
    request: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(10), default="요청")

    store: Mapped[Store] = relationship(back_populates="reservations")
    customer: Mapped[Customer] = relationship()
    histories: Mapped[list["ReservationHistory"]] = relationship(back_populates="reservation")


class ReservationHistory(Base):
    __tablename__ = "reservation_histories"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id"))
    from_status: Mapped[str] = mapped_column(String(10))
    to_status: Mapped[str] = mapped_column(String(10))
    changed_at: Mapped[datetime] = mapped_column(default=datetime.now)

    reservation: Mapped[Reservation] = relationship(back_populates="histories")


class Inquiry(Base):
    __tablename__ = "inquiries"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    content: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(default=datetime.now)
    status: Mapped[str] = mapped_column(String(10), default="미응답")
    ai_draft: Mapped[str | None] = mapped_column(Text, default=None)  # 검증 보고서용 원본
    final_answer: Mapped[str | None] = mapped_column(Text, default=None)
    check_result: Mapped[str | None] = mapped_column(Text, default=None)  # DB 대조 결과(JSON)

    store: Mapped[Store] = relationship(back_populates="inquiries")
    customer: Mapped[Customer] = relationship()


class MarketingContent(Base):
    __tablename__ = "marketing_contents"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    channel: Mapped[str] = mapped_column(String(20))
    target: Mapped[str] = mapped_column(String(100))
    keywords: Mapped[str] = mapped_column(String(200), default="")
    text: Mapped[str] = mapped_column(Text)
    check_result: Mapped[str | None] = mapped_column(Text, default=None)
    saved_at: Mapped[datetime] = mapped_column(default=datetime.now)

    store: Mapped[Store] = relationship(back_populates="contents")
