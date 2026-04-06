from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.database.repository import Repository

router = Router()


class ProfileSetup(StatesGroup):
    age = State()
    sex = State()
    chronic = State()
    allergies = State()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await Repository.get_or_create_user(message.from_user.id)
    await message.answer(
        "👋 <b>Медицинский ИИ-ассистент</b>\n\n"
        "Я помогу отслеживать твоё здоровье:\n"
        "• Отправь <b>фото или PDF</b> анализов — я извлеку показатели\n"
        "• Напиши или запиши <b>голосовое</b> с жалобой — я проанализирую\n"
        "• /trend <i>название</i> — динамика показателя\n"
        "• /export — отчёт для врача\n"
        "• /profile — настроить профиль\n"
        "• /metrics — список всех показателей\n"
        "• /help — справка\n\n"
        "⚠️ Я не заменяю врача, но помогаю систематизировать данные."
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>Команды:</b>\n"
        "/profile — заполнить/обновить профиль (возраст, пол, хронические)\n"
        "/metrics — список сохранённых показателей\n"
        "/trend <i>название</i> — график и анализ динамики\n"
        "/export — сводный отчёт для врача\n\n"
        "<b>Отправка данных:</b>\n"
        "📄 PDF/фото анализов → извлечение и сохранение показателей\n"
        "🎤 Голосовое / текст → логирование жалоб и анализ\n"
    )


@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext) -> None:
    await state.set_state(ProfileSetup.age)
    await message.answer("Укажи свой возраст (число):")


@router.message(ProfileSetup.age)
async def process_age(message: Message, state: FSMContext) -> None:
    try:
        age = int(message.text.strip())
        if not 1 <= age <= 120:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer("Введи корректный возраст (число от 1 до 120):")
        return

    await state.update_data(age=age)
    await state.set_state(ProfileSetup.sex)
    await message.answer("Пол (М/Ж):")


@router.message(ProfileSetup.sex)
async def process_sex(message: Message, state: FSMContext) -> None:
    sex = message.text.strip().upper()
    if sex not in ("М", "Ж", "M", "F"):
        await message.answer("Введи М или Ж:")
        return

    sex_normalized = "М" if sex in ("М", "M") else "Ж"
    await state.update_data(sex=sex_normalized)
    await state.set_state(ProfileSetup.chronic)
    await message.answer("Хронические заболевания (или «нет»):")


@router.message(ProfileSetup.chronic)
async def process_chronic(message: Message, state: FSMContext) -> None:
    await state.update_data(chronic=message.text.strip())
    await state.set_state(ProfileSetup.allergies)
    await message.answer("Аллергии (или «нет»):")


@router.message(ProfileSetup.allergies)
async def process_allergies(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await Repository.update_user_profile(
        user_id=message.from_user.id,
        age=data["age"],
        sex=data["sex"],
        chronic=data["chronic"],
        allergies=message.text.strip(),
    )
    await state.clear()
    await message.answer("✅ Профиль сохранён!")


@router.message(Command("metrics"))
async def cmd_metrics(message: Message) -> None:
    metrics = await Repository.get_all_metrics(message.from_user.id)
    if not metrics:
        await message.answer("Пока нет сохранённых показателей. Отправь анализы!")
        return
    text = "<b>Сохранённые показатели:</b>\n" + "\n".join(f"• {m}" for m in sorted(metrics))
    await message.answer(text)
