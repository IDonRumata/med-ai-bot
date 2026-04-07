import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot.config import settings
from bot.database.engine import init_db
from bot.handlers import start, analysis, symptoms, trends, export
from bot.middlewares.auth import AuthMiddleware
from bot.services.scheduler_service import start_scheduler, shutdown_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    await init_db()

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.message.middleware(AuthMiddleware())

    dp.include_router(start.router)
    dp.include_router(analysis.router)
    dp.include_router(symptoms.router)
    dp.include_router(trends.router)
    dp.include_router(export.router)

    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="profile", description="Мой профиль"),
        BotCommand(command="metrics", description="Список показателей"),
        BotCommand(command="trend", description="График динамики показателя"),
        BotCommand(command="export", description="Отчёт для врача"),
        BotCommand(command="help", description="Справка"),
    ])

    await start_scheduler(bot)
    logger.info("Bot started")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await shutdown_scheduler()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
