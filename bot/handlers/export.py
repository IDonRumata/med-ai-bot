import logging
from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile

from bot.database.repository import Repository
from bot.services.ai_service import generate_doctor_report
from bot.utils.crypto import decrypt

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("export"))
async def cmd_export(message: Message) -> None:
    user_id = message.from_user.id
    await message.answer("📋 Формирую отчёт для врача...")

    try:
        profile = await Repository.get_user_profile(user_id)
        if not profile:
            await message.answer(
                "Сначала заполни профиль командой /profile "
                "(возраст, пол, хронические заболевания)."
            )
            return

        symptoms_raw = await Repository.get_recent_symptoms(user_id, days=90)
        symptoms = []
        for s in symptoms_raw:
            try:
                text = decrypt(s.complaint_text)
            except Exception:
                text = s.complaint_text
            symptoms.append({
                "date": s.logged_at.strftime("%d.%m.%Y"),
                "text": text,
            })

        tests_raw = await Repository.get_recent_test_results(user_id, days=90)
        tests = [
            {
                "date": t.test_date.strftime("%d.%m.%Y"),
                "metric": t.metric_name,
                "value": t.value,
                "unit": t.unit or "",
                "ref_min": t.ref_min,
                "ref_max": t.ref_max,
            }
            for t in tests_raw
        ]

        if not symptoms and not tests:
            await message.answer("Нет данных для отчёта. Загрузи анализы или опиши жалобы.")
            return

        report = await generate_doctor_report(profile, symptoms, tests)

        # Send as text message
        if len(report) <= 4000:
            await message.answer(f"<b>📄 Отчёт для врача</b>\n\n{report}")
        else:
            # Send as file if too long
            now = datetime.now().strftime("%Y-%m-%d")
            file_content = f"МЕДИЦИНСКИЙ ОТЧЁТ\nДата: {now}\n\n{report}"
            await message.answer_document(
                document=BufferedInputFile(
                    file_content.encode("utf-8"),
                    filename=f"medical_report_{now}.txt",
                ),
                caption="📄 Отчёт для врача (текстовый файл)",
            )

    except Exception as e:
        logger.error("Export failed: %s", e, exc_info=True)
        await message.answer(
            "⚠️ Ошибка при формировании отчёта. Повторите через 5 минут."
        )
