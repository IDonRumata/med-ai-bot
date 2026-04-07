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
            KeyboardButton(text="🏥 Медкарта"),
            KeyboardButton(text="❓ Помощь"),
        ],
    ],
    resize_keyboard=True,
    persistent=True,
)


class ProfileSetup(StatesGroup):
    dob = State()
    sex = State()
    height = State()
    weight = State()
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
        "🏥 <b>Медкарта</b> — полный профиль + хронические + аллергии\n"
        "👤 <b>Профиль</b> — обновить личные данные\n\n"
        "<b>Отправка данных:</b>\n"
        "📄 PDF/фото анализов → извлечение и сохранение показателей\n"
        "🎤 Голосовое / текст → логирование жалоб и анализ\n\n"
        "<b>Доп. команды:</b>\n"
        "/addchronic — добавить хроническое заболевание\n"
        "/addallergy — добавить аллергию",
        reply_markup=MAIN_MENU,
    )


@router.message(Command("card"))
@router.message(F.text == "🏥 Медкарта")
async def cmd_card(message: Message) -> None:
    from datetime import date as date_type
    user_id = message.from_user.id
    profile = await Repository.get_user_profile(user_id)

    if not profile:
        await message.answer(
            "Профиль не заполнен. Нажми 👤 Профиль чтобы внести данные.",
            reply_markup=MAIN_MENU,
        )
        return

    age = profile.get("age", "—")
    sex = profile.get("sex") or "—"
    height = profile.get("height_cm")
    weight = profile.get("weight_kg")
    chronic = profile.get("chronic_conditions") or "не указаны"
    allergies = profile.get("allergies") or "не указаны"
    dob_iso = profile.get("date_of_birth")

    bmi_str = ""
    if height and weight:
        bmi = weight / (height / 100) ** 2
        category = (
            "недостаточный вес" if bmi < 18.5
            else "норма" if bmi < 25
            else "избыточный вес" if bmi < 30
            else "ожирение"
        )
        bmi_str = f"\n🔢 ИМТ: {bmi:.1f} ({category})"

    if dob_iso:
        from datetime import date as date_type
        dob = date_type.fromisoformat(dob_iso)
        dob_str = dob.strftime("%d.%m.%Y")
    else:
        dob_str = "—"

    metrics_count = len(await Repository.get_all_metrics(user_id))

    text = (
        f"🏥 <b>Медицинская карта</b>\n\n"
        f"📅 Дата рождения: {dob_str}\n"
        f"🎂 Возраст: {age} лет\n"
        f"⚧ Пол: {sex}\n"
        f"📏 Рост: {f'{height:.0f} см' if height else '—'}\n"
        f"⚖️ Вес: {f'{weight:.1f} кг' if weight else '—'}"
        f"{bmi_str}\n\n"
        f"🩺 <b>Хронические заболевания:</b>\n{chronic}\n\n"
        f"⚠️ <b>Аллергии:</b>\n{allergies}\n\n"
        f"📊 Показателей в базе: {metrics_count}"
    )
    await message.answer(text, reply_markup=MAIN_MENU)


@router.message(Command("addchronic"))
async def cmd_addchronic(message: Message) -> None:
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "Укажи заболевание после команды:\n<code>/addchronic Гипотиреоз</code>"
        )
        return

    addition = args[1].strip()[:500]
    user_id = message.from_user.id
    profile = await Repository.get_user_profile(user_id)
    existing = (profile or {}).get("chronic_conditions") or ""

    if existing and existing.lower() != "нет":
        new_value = existing.rstrip(", ") + ", " + addition
    else:
        new_value = addition

    await Repository.update_user_profile(user_id, chronic=new_value)
    await message.answer(f"✅ Добавлено: <b>{addition}</b>\n\nТекущий список: {new_value}")


@router.message(Command("addallergy"))
async def cmd_addallergy(message: Message) -> None:
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "Укажи аллергию после команды:\n<code>/addallergy Пенициллин</code>"
        )
        return

    addition = args[1].strip()[:500]
    user_id = message.from_user.id
    profile = await Repository.get_user_profile(user_id)
    existing = (profile or {}).get("allergies") or ""

    if existing and existing.lower() != "нет":
        new_value = existing.rstrip(", ") + ", " + addition
    else:
        new_value = addition

    await Repository.update_user_profile(user_id, allergies=new_value)
    await message.answer(f"✅ Добавлено: <b>{addition}</b>\n\nТекущий список: {new_value}")


@router.message(Command("profile"))
@router.message(F.text == "👤 Профиль")
async def cmd_profile(message: Message, state: FSMContext) -> None:
    await state.set_state(ProfileSetup.dob)
    await message.answer(
        "Укажи дату рождения в формате ДД.ММ.ГГГГ\n<i>Например: 27.06.1981</i>",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(ProfileSetup.dob)
async def process_dob(message: Message, state: FSMContext) -> None:
    from datetime import date as date_type
    text = message.text.strip()
    try:
        parts = text.replace("-", ".").replace("/", ".").split(".")
        if len(parts) == 3:
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            dob = date_type(y, m, d)
            age = date_type.today().year - dob.year - (
                (date_type.today().month, date_type.today().day) < (dob.month, dob.day)
            )
            if not 1 <= age <= 120:
                raise ValueError
        else:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer("Неверный формат. Введи дату как ДД.ММ.ГГГГ, например: 27.06.1981")
        return

    await state.update_data(dob=dob.isoformat())
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
    await state.set_state(ProfileSetup.height)
    await message.answer(
        "Рост в сантиметрах (число):\n<i>Например: 178</i>",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(ProfileSetup.height)
async def process_height(message: Message, state: FSMContext) -> None:
    try:
        h = float(message.text.strip().replace(",", "."))
        if not 50 <= h <= 250:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer("Введи рост числом в сантиметрах (например: 178):")
        return

    await state.update_data(height=h)
    await state.set_state(ProfileSetup.weight)
    await message.answer("Вес в килограммах (число):\n<i>Например: 82.5</i>")


@router.message(ProfileSetup.weight)
async def process_weight(message: Message, state: FSMContext) -> None:
    try:
        w = float(message.text.strip().replace(",", "."))
        if not 20 <= w <= 300:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer("Введи вес числом в килограммах (например: 82.5):")
        return

    await state.update_data(weight=w)
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
    from datetime import date as date_type
    data = await state.get_data()
    await Repository.update_user_profile(
        user_id=message.from_user.id,
        date_of_birth=date_type.fromisoformat(data["dob"]),
        sex=data["sex"],
        height_cm=data["height"],
        weight_kg=data["weight"],
        chronic=data["chronic"],
        allergies=message.text.strip(),
    )
    await state.clear()

    dob = date_type.fromisoformat(data["dob"])
    age = date_type.today().year - dob.year - (
        (date_type.today().month, date_type.today().day) < (dob.month, dob.day)
    )
    bmi = data["weight"] / (data["height"] / 100) ** 2

    await message.answer(
        f"✅ <b>Профиль сохранён!</b>\n\n"
        f"📅 Дата рождения: {dob.strftime('%d.%m.%Y')} ({age} лет)\n"
        f"⚧ Пол: {data['sex']}\n"
        f"📏 Рост: {data['height']:.0f} см\n"
        f"⚖️ Вес: {data['weight']:.1f} кг\n"
        f"🔢 ИМТ: {bmi:.1f}",
        reply_markup=MAIN_MENU,
    )


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
