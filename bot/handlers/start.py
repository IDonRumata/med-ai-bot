from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.database.repository import Repository

router = Router()

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📊 Мои показатели"),
            KeyboardButton(text="📈 Тренд"),
        ],
        [
            KeyboardButton(text="📋 Отчёт для врача"),
            KeyboardButton(text="👤 Профиль"),
        ],
        [
            KeyboardButton(text="❓ Помощь"),
        ],
    ],
    resize_keyboard=True,
    persistent=True,
)


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
        "• Отправь <b>фото или PDF</b> анализов — извлеку показатели\n"
        "• Напиши или запиши <b>голосовое</b> с жалобой — проанализирую\n\n"
        "⚠️ Я не заменяю врача, но помогаю систематизировать данные.",
        reply_markup=MAIN_MENU,
    )


@router.message(Command("help"))
@router.message(F.text == "❓ Помощь")
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>Команды и кнопки:</b>\n\n"
        "📊 <b>Мои показатели</b> — список всех сохранённых метрик\n"
        "📈 <b>Тренд</b> — график динамики показателя\n"
        "📋 <b>Отчёт для врача</b> — структурированный отчёт\n"
        "👤 <b>Профиль</b> — возраст, пол, хронические, аллергии\n\n"
        "<b>Отправка данных:</b>\n"
        "📄 PDF/фото анализов → извлечение и сохранение показателей\n"
        "🎤 Голосовое / текст → логирование жалоб и анализ",
        reply_markup=MAIN_MENU,
    )


@router.message(Command("profile"))
@router.message(F.text == "👤 Профиль")
async def cmd_profile(message: Message, state: FSMContext) -> None:
    await state.set_state(ProfileSetup.age)
    await message.answer(
        "Укажи свой возраст (число):",
        reply_markup=ReplyKeyboardRemove(),
    )


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

    sex_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="М"), KeyboardButton(text="Ж")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.answer("Пол:", reply_markup=sex_kb)


@router.message(ProfileSetup.sex)
async def process_sex(message: Message, state: FSMContext) -> None:
    sex = message.text.strip().upper()
    if sex not in ("М", "Ж", "M", "F"):
        await message.answer("Нажми кнопку или введи М / Ж:")
        return

    sex_normalized = "М" if sex in ("М", "M") else "Ж"
    await state.update_data(sex=sex_normalized)
    await state.set_state(ProfileSetup.chronic)
    await message.answer(
        "Хронические заболевания (или напиши «нет»):",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="нет")]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )


@router.message(ProfileSetup.chronic)
async def process_chronic(message: Message, state: FSMContext) -> None:
    await state.update_data(chronic=message.text.strip())
    await state.set_state(ProfileSetup.allergies)
    await message.answer(
        "Аллергии (или напиши «нет»):",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="нет")]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )


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
    await message.answer("✅ Профиль сохранён!", reply_markup=MAIN_MENU)


@router.message(Command("metrics"))
@router.message(F.text == "📊 Мои показатели")
async def cmd_metrics(message: Message) -> None:
    metrics = await Repository.get_all_metrics(message.from_user.id)
    if not metrics:
        await message.answer(
            "Пока нет сохранённых показателей.\nОтправь фото или PDF анализов!",
            reply_markup=MAIN_MENU,
        )
        return
    text = "<b>Сохранённые показатели:</b>\n" + "\n".join(f"• {m}" for m in sorted(metrics))
    await message.answer(text, reply_markup=MAIN_MENU)
