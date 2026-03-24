from sqlalchemy import String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Pricing(Base):
    __tablename__ = "pricing"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_type: Mapped[str] = mapped_column(String(30))  # 카시트/매트리스/소파
    item_subtype: Mapped[str] = mapped_column(String(30))  # 일반/가죽/스웨이드
    price: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
