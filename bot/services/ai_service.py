import logging
import json
from openai import AsyncOpenAI

from bot.config import settings
from bot.services.anonymizer import anonymize
from bot.utils.rate_limiter import ai_limiter

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=60.0)


def _check_rate_limit() -> None:
    if not ai_limiter.is_allowed():
        wait = ai_limiter.seconds_until_reset()
        raise RuntimeError(f"RATE_LIMIT:{wait}")

SYSTEM_PROMPT = (
    "Ты — медицинский ИИ-аналитик. Ты помогаешь пользователю отслеживать его здоровье. "
    "Ты не ставишь диагнозы и не заменяешь врача, но анализируешь тренды, "
    "указываешь на отклонения от нормы и рекомендуешь обратиться к конкретному специалисту. "
    "Отвечай на русском языке. Будь точным и структурированным. "
    "Если данных недостаточно — скажи об этом прямо."
)


def _safe(text: str, max_len: int = 500) -> str:
    """Truncate and strip prompt-injection attempts from user-controlled strings."""
    if not text:
        return ""
    # Remove common injection patterns
    cleaned = text.replace("ignore previous", "").replace("forget instructions", "")
    return cleaned[:max_len]


async def analyze_test_results(
    extracted_text: str,
    user_profile: dict | None = None,
) -> dict:
    """Parse lab results from extracted text. Returns structured JSON."""
    _check_rate_limit()
    profile_ctx = ""
    if user_profile:
        profile_ctx = f"\nПрофиль пациента: пол {user_profile.get('sex', 'не указан')}, возраст {user_profile.get('age', 'не указан')}."

    prompt = (
        f"Извлеки из следующего текста лабораторных анализов все показатели. "
        f"Верни JSON-массив объектов с полями: metric, value (число), unit, ref_min, ref_max, date (YYYY-MM-DD). "
        f"Если какое-то поле неизвестно, поставь null. "
        f"После массива дай краткую сводку на русском в поле summary."
        f"{profile_ctx}"
        f"\n\nТекст анализов:\n{anonymize(extracted_text)}"
    )

    response = await client.chat.completions.create(
        model=settings.openai_model_light,  # parsing is straightforward — use mini
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=2000,
    )

    return json.loads(response.choices[0].message.content)


async def analyze_symptoms(
    complaint: str,
    recent_symptoms: list[dict],
    recent_tests: list[dict],
    user_profile: dict | None = None,
) -> str:
    """Analyze new complaint in context of recent health data."""
    _check_rate_limit()
    profile_ctx = ""
    if user_profile:
        bmi_str = ""
        h = user_profile.get("height_cm")
        w = user_profile.get("weight_kg")
        if h and w:
            bmi = w / (h / 100) ** 2
            bmi_str = f", рост {h:.0f} см, вес {w:.1f} кг, ИМТ {bmi:.1f}"
        profile_ctx = (
            f"Профиль: пол {user_profile.get('sex', 'н/д')}, "
            f"возраст {user_profile.get('age', 'н/д')}{bmi_str}, "
            f"хронические: {_safe(user_profile.get('chronic_conditions') or 'нет')}, "
            f"аллергии: {_safe(user_profile.get('allergies') or 'нет')}."
        )

    symptoms_ctx = ""
    if recent_symptoms:
        symptoms_ctx = "Недавние жалобы:\n" + "\n".join(
            f"- {s['date']}: {s['text']}" for s in recent_symptoms[-10:]
        )

    tests_ctx = ""
    if recent_tests:
        tests_ctx = "Свежие анализы:\n" + "\n".join(
            f"- {t['metric']}: {t['value']} {t.get('unit', '')} "
            f"(норма {t.get('ref_min', '?')}-{t.get('ref_max', '?')})"
            for t in recent_tests[-15:]
        )

    prompt = (
        f"Новая жалоба пациента: {anonymize(complaint)}\n\n"
        f"{profile_ctx}\n{symptoms_ctx}\n{tests_ctx}\n\n"
        f"Проанализируй жалобу в контексте всех данных. "
        f"Дай краткую оценку, возможные причины, и рекомендацию (к какому врачу обратиться, какие анализы сдать)."
    )

    response = await client.chat.completions.create(
        model=settings.openai_model_heavy,  # complex medical reasoning
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=1500,
    )

    return response.choices[0].message.content


async def analyze_trend(
    metric_name: str,
    data_points: list[dict],
    user_profile: dict | None = None,
) -> str:
    """Analyze metric trend over time."""
    profile_ctx = ""
    if user_profile:
        profile_ctx = f"Пациент: пол {user_profile.get('sex', 'н/д')}, возраст {user_profile.get('age', 'н/д')}."

    data_str = "\n".join(
        f"  {d['date']}: {d['value']} {d.get('unit', '')}" for d in data_points
    )

    prompt = (
        f"Проанализируй динамику показателя «{metric_name}» за последний период:\n"
        f"{data_str}\n\n{profile_ctx}\n"
        f"Оцени тренд (улучшение/ухудшение/стабильно), укажи отклонения от нормы, "
        f"дай рекомендацию."
    )

    response = await client.chat.completions.create(
        model=settings.openai_model_light,  # trend analysis is simpler
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=800,
    )

    return response.choices[0].message.content


async def analyze_image(image_bytes: bytes, user_profile: dict | None = None) -> dict:
    """Analyze a medical image (lab results photo) using Vision API."""
    import base64

    b64 = base64.b64encode(image_bytes).decode()

    profile_ctx = ""
    if user_profile:
        profile_ctx = f"\nПрофиль: пол {user_profile.get('sex', 'н/д')}, возраст {user_profile.get('age', 'н/д')}."

    response = await client.chat.completions.create(
        model=settings.openai_model_heavy,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Извлеки из этого изображения все лабораторные показатели. "
                            f"Верни JSON с полями: results (массив {{metric, value, unit, ref_min, ref_max, date}}), summary (текст).{profile_ctx}"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                ],
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=2000,
    )

    return json.loads(response.choices[0].message.content)


async def generate_doctor_report(
    user_profile: dict,
    symptoms: list[dict],
    tests: list[dict],
) -> str:
    """Generate a structured report for a doctor visit."""
    prompt = (
        f"Составь структурированный медицинский отчёт для лечащего врача.\n\n"
        f"Профиль: пол {user_profile.get('sex', 'н/д')}, возраст {user_profile.get('age', 'н/д')}, "
        f"хронические заболевания: {user_profile.get('chronic_conditions', 'нет')}, "
        f"аллергии: {user_profile.get('allergies', 'нет')}.\n\n"
        f"Жалобы за последние 3 месяца:\n"
        + "\n".join(f"- [{s['date']}] {s['text']}" for s in symptoms)
        + f"\n\nАнализы за последние 3 месяца:\n"
        + "\n".join(
            f"- [{t['date']}] {t['metric']}: {t['value']} {t.get('unit', '')} "
            f"(норма {t.get('ref_min', '?')}-{t.get('ref_max', '?')})"
            for t in tests
        )
        + "\n\nФормат отчёта: Анамнез, Текущие жалобы, Результаты обследований, "
        "Отклонения от нормы, Рекомендуемые дополнительные обследования."
    )

    response = await client.chat.completions.create(
        model=settings.openai_model_heavy,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=3000,
    )

    return response.choices[0].message.content
