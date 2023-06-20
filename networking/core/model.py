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


class Log(Base):
    __tablename__ = "log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)    
    created: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"), nullable=False)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False
    )
    chapter: Mapped[str] = mapped_column(String(32), nullable=False)
    check: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    user: Mapped[User] = relationship("User", back_populates="logs")


class Exam(Base):
    __tablename__ = "exam"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    test_points: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    ticket: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ticket_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    final_points: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    has_debt: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)

    user: Mapped[User] = relationship("User", back_populates="exam")

    def calculate_points(self, chapter_points: Decimal) -> Decimal:
        if self.final_points is not None:
            return self.final_points
        if self.has_debt:
            return min(self.test_points or 0 + chapter_points, Decimal(74))
        else:
            return min(self.test_points or 0 + chapter_points, Decimal(90))


User.attempts = relationship("Attempt", back_populates="user")
User.reports = relationship("Report", back_populates="user")
User.logs = relationship("Log", back_populates="user")
User.exam = relationship("Exam", back_populates="user", uselist=False)


__all__ = ["Attempt"]
