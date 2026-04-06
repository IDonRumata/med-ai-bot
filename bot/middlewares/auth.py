import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.config import settings

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        user_id = event.from_user.id if event.from_user else None

        if user_id != settings.allowed_user_id:
            logger.warning(
                "Unauthorized access attempt: user_id=%s, username=%s, text=%s",
                user_id,
                event.from_user.username if event.from_user else "unknown",
                (event.text or "")[:50],
            )
            return None  # silently ignore

        return await handler(event, data)
