from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class TaskUpdate(Base):
    __tablename__ = "task_updates"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id"))
    stage: Mapped[str] = mapped_column(String(20))  # pickup/clean/delivery
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    completed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    reservation: Mapped["Reservation"] = relationship("Reservation", back_populates="task_updates")
    employee: Mapped["Employee"] = relationship("Employee")


from app.models.reservation import Reservation
from app.models.employee import Employee
