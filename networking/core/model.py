from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    ForeignKey,
    BigInteger, Boolean, DateTime, Numeric, String, Text,
    text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quirck.auth.model import User
from quirck.db.base import Base
    

class Attempt(Base):
    __tablename__ = "attempt"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    submitted: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"), nullable=False)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False
    )
    chapter: Mapped[str] = mapped_column(String(32), nullable=False)
    task: Mapped[str] = mapped_column(String(32), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    points: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="attempts")


class Report(Base):
    __tablename__ = "report"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    submitted: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"), nullable=False)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False
    )
    chapter: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    user: Mapped[User] = relationship("User", back_populates="reports")


User.attempts = relationship("Attempt", back_populates="user")
User.reports = relationship("Report", back_populates="user")


__all__ = ["Attempt"]
