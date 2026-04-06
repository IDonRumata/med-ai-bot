from datetime import datetime, date
from sqlalchemy import (
    BigInteger, String, Text, Float, Date, DateTime, Boolean, ForeignKey, Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    age: Mapped[int | None]
    sex: Mapped[str | None] = mapped_column(String(10))
    chronic_conditions: Mapped[str | None] = mapped_column(Text)  # encrypted
    allergies: Mapped[str | None] = mapped_column(Text)  # encrypted
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    test_results: Mapped[list["TestResult"]] = relationship(back_populates="user")
    symptom_logs: Mapped[list["SymptomLog"]] = relationship(back_populates="user")
    reminders: Mapped[list["Reminder"]] = relationship(back_populates="user")


class TestResult(Base):
    __tablename__ = "test_results"
    __table_args__ = (
        Index("ix_test_results_metric_date", "metric_name", "test_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    test_date: Mapped[date] = mapped_column(Date)
    metric_name: Mapped[str] = mapped_column(String(200))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(50))
    ref_min: Mapped[float | None] = mapped_column(Float)
    ref_max: Mapped[float | None] = mapped_column(Float)
    source_file: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="test_results")


class SymptomLog(Base):
    __tablename__ = "symptom_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    logged_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    complaint_text: Mapped[str] = mapped_column(Text)  # encrypted
    ai_assessment: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[int | None]  # 1-10

    user: Mapped["User"] = relationship(back_populates="symptom_logs")


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    fire_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    message: Mapped[str] = mapped_column(Text)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="reminders")
