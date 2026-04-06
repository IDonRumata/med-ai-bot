import logging

from aiogram import Router, F
from aiogram.types import Message

from bot.database.repository import Repository
from bot.services.ai_service import analyze_symptoms
from bot.services.voice_service import transcribe_voice
from bot.utils.crypto import decrypt

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.voice)
async def handle_voice(message: Message) -> None:
    await message.answer("🎤 Голосовое получено, расшифровываю...")

    try:
        file = await message.bot.get_file(message.voice.file_id)
        data = await message.bot.download_file(file.file_path)
        ogg_bytes = data.read()

        text = await transcribe_voice(ogg_bytes)
        await message.answer(f"📝 Расшифровка:\n<i>{text}</i>")

        await _process_complaint(message, text)

    except Exception as e:
        logger.error("Voice processing failed: %s", e, exc_info=True)
        await message.answer(
            "⚠️ Ошибка при обработке голосового. Повторите через 5 минут."
        )


@router.message(F.text)
async def handle_text(message: Message) -> None:
    if message.text.startswith("/"):
        return  # skip commands handled by other routers

    await _process_complaint(message, message.text)


async def _process_complaint(message: Message, complaint_text: str) -> None:
    user_id = message.from_user.id
    await message.answer("🔍 Анализирую жалобу в контексте твоих данных...")

    try:
        profile = await Repository.get_user_profile(user_id)

        recent_symptoms_raw = await Repository.get_recent_symptoms(user_id, days=30)
        recent_symptoms = []
        for s in recent_symptoms_raw:
            try:
                decrypted = decrypt(s.complaint_text)
            except Exception:
                decrypted = s.complaint_text
            recent_symptoms.append({
                "date": s.logged_at.strftime("%d.%m.%Y"),
                "text": decrypted,
            })

        recent_tests_raw = await Repository.get_recent_test_results(user_id, days=90)
        recent_tests = [
            {
                "metric": t.metric_name,
                "value": t.value,
                "unit": t.unit,
                "ref_min": t.ref_min,
                "ref_max": t.ref_max,
                "date": t.test_date.strftime("%d.%m.%Y"),
            }
            for t in recent_tests_raw
        ]

        assessment = await analyze_symptoms(
            complaint_text, recent_symptoms, recent_tests, profile,
        )

        severity = _estimate_severity(assessment)

        await Repository.save_symptom(
            user_id=user_id,
            text=complaint_text,
            ai_assessment=assessment,
            severity=severity,
        )

        await message.answer(f"📋 <b>Анализ:</b>\n\n{assessment}")

    except Exception as e:
        logger.error("Symptom analysis failed: %s", e, exc_info=True)
        await message.answer(
            "⚠️ Произошла ошибка связи с сервером анализа. Повторите запрос через 5 минут."
        )
        # Still save the complaint locally
        try:
            await Repository.save_symptom(user_id=user_id, text=complaint_text)
        except Exception:
            pass


def _estimate_severity(assessment: str) -> int:
    """Simple local severity estimation to avoid extra API call."""
    text = assessment.lower()
    urgent_words = ["срочно", "немедленно", "скорая", "вызов", "экстренн", "опасн"]
    high_words = ["обратиться к врачу", "обследовани", "рекомендую", "важно"]
    medium_words = ["наблюдени", "контроль", "следить"]

    if any(w in text for w in urgent_words):
        return 8
    if any(w in text for w in high_words):
        return 5
    if any(w in text for w in medium_words):
        return 3
    return 2
