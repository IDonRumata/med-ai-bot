from datetime import datetime, date, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.engine import async_session
from bot.database.models import User, TestResult, SymptomLog, Reminder
from bot.utils.crypto import encrypt, decrypt


class Repository:

    @staticmethod
    async def get_or_create_user(user_id: int) -> User:
        async with async_session() as session:
            user = await session.get(User, user_id)
            if not user:
                user = User(id=user_id)
                session.add(user)
                await session.commit()
            return user

    @staticmethod
    async def update_user_profile(
        user_id: int,
        date_of_birth: date | None = None,
        sex: str | None = None,
        height_cm: float | None = None,
        weight_kg: float | None = None,
        chronic: str | None = None,
        allergies: str | None = None,
    ) -> None:
        async with async_session() as session:
            user = await session.get(User, user_id)
            if not user:
                return
            if date_of_birth is not None:
                user.date_of_birth = date_of_birth
            if sex is not None:
                user.sex = sex
            if height_cm is not None:
                user.height_cm = height_cm
            if weight_kg is not None:
                user.weight_kg = weight_kg
            if chronic is not None:
                user.chronic_conditions = encrypt(chronic)
            if allergies is not None:
                user.allergies = encrypt(allergies)
            await session.commit()

    @staticmethod
    async def save_test_results(user_id: int, results: list[dict]) -> int:
        async with async_session() as session:
            count = 0
            for r in results:
                tr = TestResult(
                    user_id=user_id,
                    test_date=r.get("date", date.today()),
                    metric_name=r["metric"],
                    value=r["value"],
                    unit=r.get("unit"),
                    ref_min=r.get("ref_min"),
                    ref_max=r.get("ref_max"),
                    source_file=r.get("source"),
                )
                session.add(tr)
                count += 1
            await session.commit()
            return count

    @staticmethod
    async def get_metric_history(
        user_id: int, metric_name: str, months: int = 12,
    ) -> list[TestResult]:
        since = date.today() - timedelta(days=months * 30)
        async with async_session() as session:
            stmt = (
                select(TestResult)
                .where(
                    and_(
                        TestResult.user_id == user_id,
                        TestResult.metric_name.ilike(
                            f"%{metric_name.replace('%', '').replace('_', '')}%"
                        ),
                        TestResult.test_date >= since,
                    )
                )
                .order_by(TestResult.test_date)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    @staticmethod
    async def get_all_metrics(user_id: int) -> list[str]:
        async with async_session() as session:
            stmt = (
                select(TestResult.metric_name)
                .where(TestResult.user_id == user_id)
                .distinct()
            )
            result = await session.execute(stmt)
            return [r[0] for r in result.all()]

    @staticmethod
    async def save_symptom(
        user_id: int, text: str, ai_assessment: str | None = None, severity: int | None = None,
    ) -> SymptomLog:
        async with async_session() as session:
            log = SymptomLog(
                user_id=user_id,
                complaint_text=encrypt(text),
                ai_assessment=ai_assessment,
                severity=severity,
            )
            session.add(log)
            await session.commit()
            await session.refresh(log)
            return log

    @staticmethod
    async def get_recent_symptoms(user_id: int, days: int = 30) -> list[SymptomLog]:
        since = datetime.utcnow() - timedelta(days=days)
        async with async_session() as session:
            stmt = (
                select(SymptomLog)
                .where(
                    and_(
                        SymptomLog.user_id == user_id,
                        SymptomLog.logged_at >= since,
                    )
                )
                .order_by(SymptomLog.logged_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    @staticmethod
    async def get_recent_test_results(user_id: int, days: int = 90) -> list[TestResult]:
        since = date.today() - timedelta(days=days)
        async with async_session() as session:
            stmt = (
                select(TestResult)
                .where(
                    and_(
                        TestResult.user_id == user_id,
                        TestResult.test_date >= since,
                    )
                )
                .order_by(TestResult.test_date.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    @staticmethod
    async def add_reminder(user_id: int, fire_at: datetime, message: str) -> Reminder:
        async with async_session() as session:
            r = Reminder(user_id=user_id, fire_at=fire_at, message=message)
            session.add(r)
            await session.commit()
            await session.refresh(r)
            return r

    @staticmethod
    async def get_pending_reminders() -> list[Reminder]:
        now = datetime.utcnow()
        async with async_session() as session:
            stmt = (
                select(Reminder)
                .where(and_(Reminder.sent == False, Reminder.fire_at <= now))
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    @staticmethod
    async def mark_reminder_sent(reminder_id: int) -> None:
        async with async_session() as session:
            r = await session.get(Reminder, reminder_id)
            if r:
                r.sent = True
                await session.commit()

    @staticmethod
    async def get_user_profile(user_id: int) -> dict | None:
        async with async_session() as session:
            user = await session.get(User, user_id)
            if not user:
                return None
            return {
                "age": user.age,  # computed property from date_of_birth
                "date_of_birth": user.date_of_birth.isoformat() if user.date_of_birth else None,
                "sex": user.sex,
                "height_cm": user.height_cm,
                "weight_kg": user.weight_kg,
                "chronic_conditions": decrypt(user.chronic_conditions) if user.chronic_conditions else None,
                "allergies": decrypt(user.allergies) if user.allergies else None,
            }
