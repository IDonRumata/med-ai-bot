import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from bot.config import settings
from bot.database.repository import Repository

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.tz)


async def _check_reminders(bot: Bot) -> None:
    """Fire pending reminders."""
    pending = await Repository.get_pending_reminders()
    for reminder in pending:
        try:
            await bot.send_message(
                chat_id=reminder.user_id,
                text=f"🔔 <b>Напоминание:</b>\n{reminder.message}",
            )
            await Repository.mark_reminder_sent(reminder.id)
            logger.info("Reminder %d sent to user %d", reminder.id, reminder.user_id)
        except Exception as e:
            logger.error("Failed to send reminder %d: %s", reminder.id, e)


async def _daily_health_check(bot: Bot) -> None:
    """Daily proactive check: follow-ups on recent symptoms."""
    user_id = settings.allowed_user_id
    symptoms = await Repository.get_recent_symptoms(user_id, days=7)

    if symptoms:
        latest = symptoms[0]
        days_ago = (datetime.utcnow() - latest.logged_at).days
        if days_ago >= 2:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    f"👋 Привет! {days_ago} дней назад ты жаловался на:\n"
                    f"<i>«{latest.complaint_text[:100]}...»</i>\n\n"
                    f"Как самочувствие сейчас? Напиши или запиши голосовое."
                ),
            )


async def start_scheduler(bot: Bot) -> None:
    scheduler.add_job(
        _check_reminders,
        "interval",
        minutes=5,
        args=[bot],
        id="check_reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        _daily_health_check,
        "cron",
        hour=10,
        minute=0,
        args=[bot],
        id="daily_health_check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started")


async def shutdown_scheduler() -> None:
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
