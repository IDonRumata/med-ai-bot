import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile

from bot.database.repository import Repository
from bot.services.ai_service import analyze_trend
from bot.services.chart_service import build_metric_chart

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("trend"))
async def cmd_trend(message: Message) -> None:
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        metrics = await Repository.get_all_metrics(message.from_user.id)
        if metrics:
            text = "Укажи название показателя после /trend\n\n<b>Доступные:</b>\n"
            text += "\n".join(f"• <code>{m}</code>" for m in sorted(metrics))
        else:
            text = "Нет сохранённых показателей. Сначала загрузи анализы."
        await message.answer(text)
        return

    metric_name = args[1].strip()
    user_id = message.from_user.id

    history = await Repository.get_metric_history(user_id, metric_name)

    if not history:
        await message.answer(
            f"Показатель «{metric_name}» не найден. Проверь название командой /metrics"
        )
        return

    if len(history) < 2:
        await message.answer(
            f"Для тренд-анализа нужно минимум 2 измерения «{metric_name}». "
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
        await message.answer(
            "⚠️ Ошибка при построении тренда. Повторите через 5 минут."
        )
