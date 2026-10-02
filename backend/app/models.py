from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


class Kudos(Base):
    __tablename__ = "kudos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_type: Mapped[str] = mapped_column(String(20), nullable=False)
    recipient_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sender_name: Mapped[str] = mapped_column(
        String(100), nullable=False, default="Anonymous"
    )
    slack_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    slack_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
