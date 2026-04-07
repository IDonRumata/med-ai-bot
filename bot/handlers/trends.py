import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, BufferedInputFile, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from bot.database.repository import Repository
from bot.services.ai_service import analyze_trend
from bot.services.chart_service import build_metric_chart

logger = logging.getLogger(__name__)
router = Router()


def _build_metrics_keyboard(metrics: list[str]) -> InlineKeyboardMarkup:
    """Build inline keyboard with metric buttons (2 per row)."""
    buttons = [
        InlineKeyboardButton(text=m, callback_data=f"trend:{m[:50]}")
        for m in sorted(metrics)
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("trend"))
@router.message(F.text == "📈 Тренд")
async def cmd_trend(message: Message) -> None:
    args = message.text.split(maxsplit=1) if message.text else []
    user_id = message.from_user.id

    # If called as "📈 Тренд" button or /trend without argument — show picker
    if len(args) < 2 or message.text == "📈 Тренд":
        metrics = await Repository.get_all_metrics(user_id)
        if not metrics:
            await message.answer("Нет сохранённых показателей. Сначала загрузи анализы.")
            return
        await message.answer(
            "Выбери показатель:",
            reply_markup=_build_metrics_keyboard(metrics),
        )
        return

    await _show_trend(message, user_id, args[1].strip())


@router.callback_query(F.data.startswith("trend:"))
async def callback_trend(query: CallbackQuery) -> None:
    metric_name = query.data.split(":", 1)[1]
    await query.answer()
    await query.message.edit_text(f"📊 Строю график «{metric_name}»...")
    await _show_trend(query.message, query.from_user.id, metric_name)


async def _show_trend(message: Message, user_id: int, metric_name: str) -> None:
    history = await Repository.get_metric_history(user_id, metric_name)

    if not history:
        await message.answer(
            f"Показатель «{metric_name}» не найден. Проверь название кнопкой 📊 Мои показатели"
        )
        return

    if len(history) < 2:
        await message.answer(
            f"Для тренда нужно минимум 2 измерения «{metric_name}».\n"
            f"Пока есть только одно: {history[0].value} от {history[0].test_date}"
        )
        return

    await message.answer(f"📊 Строю график «{metric_name}»...")

    try:
        dates = [h.test_date for h in history]
        values = [h.value for h in history]
        ref_min = next((h.ref_min for h in history if h.ref_min is not None), None)
        ref_max = next((h.ref_max for h in history if h.ref_max is not None), None)

        chart_png = build_metric_chart(metric_name, dates, values, ref_min, ref_max)

        data_points = [
            {"date": h.test_date.isoformat(), "value": h.value, "unit": h.unit}
            for h in history
        ]
        profile = await Repository.get_user_profile(user_id)
        ai_analysis = await analyze_trend(metric_name, data_points, profile)

        await message.answer_photo(
            photo=BufferedInputFile(chart_png, filename=f"{metric_name}.png"),
            caption=f"📈 <b>{metric_name}</b>\n\n{ai_analysis}",
        )

    except Exception as e:
        logger.error("Trend analysis failed: %s", e, exc_info=True)
        await message.answer("⚠️ Ошибка при построении тренда. Повторите через 5 минут.")
