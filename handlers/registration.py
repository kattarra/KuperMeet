from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from config import settings
from db import create_user, get_user
from keyboards import MAIN_MENU, moderation_keyboard

router = Router()


class Registration(StatesGroup):
    name = State()
    age = State()
    city = State()
    photo = State()
    bio = State()


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await get_user(message.from_user.id)
    if user:
        if user["banned"]:
            await message.answer("Доступ к KuperMeet ограничен.")
        elif user["approved"]:
            await message.answer(
                f"С возвращением, {user['name']}! 💜",
                reply_markup=MAIN_MENU,
            )
        else:
            await message.answer("Твоя анкета уже отправлена на модерацию. Скоро вернёмся 💜")
        return

    if not message.from_user.username:
        await message.answer(
            "Для регистрации нужен Telegram username.\n"
            "Установи его в настройках Telegram и снова нажми /start."
        )
        return

    await state.set_state(Registration.name)
    await message.answer(
        "Привет! Это KuperMeet 💜\n\n"
        "Давай создадим твою анкету. Как тебя зовут? (до 30 символов)"
    )


@router.message(Registration.name)
async def get_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name or len(name) > 30:
        await message.answer("Имя должно быть от 1 до 30 символов. Попробуй ещё раз.")
        return
    await state.update_data(name=name)
    await state.set_state(Registration.age)
    await message.answer("Сколько тебе лет? Введи число.")


@router.message(Registration.age)
async def get_age(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit() or not 14 <= int(raw) <= 99:
        await message.answer("Укажи возраст числом от 14 до 99 лет.")
        return
    age = int(raw)
    if age < 18:
        await state.clear()
        await message.answer(
            "Подростковый сегмент KuperMeet пока закрыт. "
            "Мы не будем собирать или публиковать анкету до запуска отдельной "
            "проверки возраста и защитных механизмов. 💜"
        )
        return
    await state.update_data(age=age)
    await state.set_state(Registration.city)
    await message.answer("Из какого ты города? Сейчас KuperMeet запускается в Омске.")


@router.message(Registration.city)
async def get_city(message: Message, state: FSMContext) -> None:
    city = (message.text or "").strip()
    if not city or len(city) > 50:
        await message.answer("Напиши название города (до 50 символов).")
        return
    await state.update_data(city=city)
    await state.set_state(Registration.photo)
    await message.answer("Отправь одно своё фото для анкеты 📸")


@router.message(Registration.photo)
async def get_photo(message: Message, state: FSMContext) -> None:
    if not message.photo:
        await message.answer("Нужно именно фото, отправленное как фотография, а не файл.")
        return
    await state.update_data(photo_id=message.photo[-1].file_id)
    await state.set_state(Registration.bio)
    await message.answer("Напиши пару слов о себе. До 100 символов. Можно отправить «Пропустить».")


@router.message(Registration.bio)
async def get_bio(message: Message, state: FSMContext) -> None:
    bio = (message.text or "").strip()
    if bio.lower() in {"пропустить", "пропустить."}:
        bio = ""
    elif not message.text:
        await message.answer("Напиши описание текстом или отправь «Пропустить».")
        return
    elif len(bio) > 100:
        await message.answer("Описание — максимум 100 символов. Сократи немного 🙂")
        return

    data = await state.get_data()
    try:
        await create_user(
            tg_id=message.from_user.id,
            username=message.from_user.username or "",
            name=data["name"],
            age=data["age"],
            city=data["city"],
            photo_id=data["photo_id"],
            bio=bio,
        )
    except Exception:
        await message.answer("Не получилось сохранить анкету. Попробуй ещё раз через /start.")
        await state.clear()
        raise

    await state.clear()
    caption = (
        "🆕 Новая анкета на модерацию\n\n"
        f"Имя: {data['name']}\n"
        f"Возраст: {data['age']}\n"
        f"Город: {data['city']}\n"
        f"Описание: {bio or '—'}\n"
        f"Telegram: @{message.from_user.username}\n"
        f"ID: {message.from_user.id}"
    )
    keyboard = moderation_keyboard(message.from_user.id)

    if settings.moderation_channel:
        try:
            await message.bot.send_photo(
                chat_id=settings.moderation_channel,
                photo=data["photo_id"],
                caption=caption,
                reply_markup=keyboard,
            )
        except Exception:
            await message.answer(
                "Анкета сохранена, но не удалось отправить её в канал модерации. "
                "Администратор должен проверить MOD_CHANNEL."
            )
            return
    elif settings.admin_ids:
        for admin_id in settings.admin_ids:
            try:
                await message.bot.send_photo(
                    chat_id=admin_id,
                    photo=data["photo_id"],
                    caption=caption,
                    reply_markup=keyboard,
                )
            except Exception:
                continue
    else:
        await message.answer(
            "Анкета сохранена, но модерация пока не настроена. "
            "Администратор должен добавить ADMIN_IDS или MOD_CHANNEL в .env."
        )
        return

    await message.answer(
        "Готово! 🎉 Анкета отправлена на модерацию. "
        "Как только её проверят, я напишу тебе сюда."
    )
