from datetime import datetime, date
from sqlalchemy import String, Text, Integer, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_no: Mapped[str] = mapped_column(String(20), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    item_type: Mapped[str] = mapped_column(String(30))
    item_subtype: Mapped[str | None] = mapped_column(String(30), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    scheduled_date: Mapped[date] = mapped_column(Date)
    scheduled_time: Mapped[str] = mapped_column(String(10))  # morning/afternoon/evening
    pickup_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    cleaning_method: Mapped[str | None] = mapped_column(String(10), nullable=True)  # dry/wet
    area: Mapped[str | None] = mapped_column(String(20), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)  # cash/card/naver
    items_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # 복수 품목 JSON
    notify_messages: Mapped[str | None] = mapped_column(Text, nullable=True)  # 알림 메시지 ID 추적 JSON
    special_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    price: Mapped[int] = mapped_column(Integer, default=0)
    final_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    customer: Mapped["Customer"] = relationship("Customer")
    task_updates: Mapped[list["TaskUpdate"]] = relationship("TaskUpdate", back_populates="reservation")


from app.models.customer import Customer
from app.models.task_update import TaskUpdate
