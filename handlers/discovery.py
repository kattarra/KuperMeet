from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from db import (
    create_match,
    delete_user,
    get_daily_like_count,
    get_next_profile,
    get_user,
    get_user_like_limit,
    has_liked,
    increment_daily_likes,
    record_view,
    update_profile_field,
)
from keyboards import (
    confirm_delete_profile_keyboard,
    edit_gender_keyboard,
    edit_looking_for_keyboard,
    profile_management_keyboard,
    profile_keyboard,
)

router = Router()


class ProfileEditing(StatesGroup):
    value = State()


async def send_next_profile(message: Message, viewer_id: int) -> None:
    viewer = await get_user(viewer_id)
    if not viewer or not viewer["approved"] or viewer["banned"]:
        await message.answer("Сначала дождись одобрения анкеты модератором 💜")
        return

    profile = await get_next_profile(viewer_id)
    if not profile:
        await message.answer(
            "Пока анкеты закончились 🥲\n"
            "Мы покажем новых людей, когда они появятся. Загляни чуть позже!"
        )
        return

    caption = (
        f"{profile['name']}, {profile['age']}\n"
        f"{'👨 Парень' if profile['gender'] == 'male' else '👩 Девушка'}\n"
        f"📍 {profile['city']}\n\n"
        f"{profile['bio'] or 'Пока ничего не рассказал(а) о себе.'}"
    )
    await message.answer_photo(
        photo=profile["photo_id"],
        caption=caption,
        reply_markup=profile_keyboard(int(profile["tg_id"])),
    )


@router.message(F.text == "👀 Смотреть")
async def open_feed(message: Message) -> None:
    await send_next_profile(message, message.from_user.id)


@router.message(F.text == "👤 Моя анкета")
async def my_profile(message: Message) -> None:
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала создай анкету командой /start.")
        return
    status = (
        "Доступ ограничен ⛔" if user["banned"]
        else "Одобрена ✅" if user["approved"]
        else "На модерации ⏳"
    )
    caption = (
        f"👤 {user['name']}, {user['age']}\n"
        f"📍 {user['city']}\n"
        f"Статус: {status}\n\n"
        f"{user['bio'] or 'Описание не добавлено.'}"
    )
    await message.answer_photo(
        photo=user["photo_id"],
        caption=caption,
        reply_markup=profile_management_keyboard(),
    )


@router.callback_query(F.data.startswith("profile:edit:"))
async def begin_profile_edit(callback: CallbackQuery, state: FSMContext) -> None:
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Анкета не найдена.", show_alert=True)
        return
    if user["banned"]:
        await callback.answer("Изменение анкеты недоступно.", show_alert=True)
        return
    field = (callback.data or "").rsplit(":", 1)[-1]
    prompts = {
        "name": "Введи новое имя (от 1 до 30 символов).",
        "age": "Введи новый возраст числом от 18 до 99 лет.",
        "city": "Введи название города (до 50 символов).",
        "bio": "Напиши новое описание (до 100 символов). Чтобы очистить описание, отправь «—».",
        "photo": "Отправь новое фото как обычную фотографию, не файлом.",
    }
    if field == "gender":
        await callback.answer()
        await callback.message.answer("Выбери свой пол:", reply_markup=edit_gender_keyboard())
        return
    if field == "looking_for":
        await callback.answer()
        await callback.message.answer("С кем хочешь знакомиться?", reply_markup=edit_looking_for_keyboard())
        return
    if field not in prompts:
        await callback.answer("Неизвестное поле.", show_alert=True)
        return
    await state.set_state(ProfileEditing.value)
    await state.update_data(edit_field=field)
    await callback.answer()
    await callback.message.answer(prompts[field])


@router.callback_query(F.data.startswith("profile:value:"))
async def set_profile_choice(callback: CallbackQuery) -> None:
    try:
        _, _, field, value = (callback.data or "").split(":", 3)
    except ValueError:
        await callback.answer("Не удалось сохранить настройку.", show_alert=True)
        return
    if field == "gender" and value not in {"male", "female"}:
        await callback.answer("Некорректный вариант.", show_alert=True)
        return
    if field == "looking_for" and value not in {"male", "female", "all"}:
        await callback.answer("Некорректный вариант.", show_alert=True)
        return
    if field not in {"gender", "looking_for"}:
        await callback.answer("Неизвестная настройка.", show_alert=True)
        return
    user = await get_user(callback.from_user.id)
    if not user or user["banned"]:
        await callback.answer("Анкета недоступна.", show_alert=True)
        return
    await update_profile_field(callback.from_user.id, field, value)
    await callback.answer("Сохранено 💜")
    await callback.message.answer("Настройки анкеты обновлены 💜")


@router.message(ProfileEditing.value, Command("cancel"))
async def cancel_profile_edit(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Изменение отменено.")


@router.message(ProfileEditing.value)
async def save_profile_edit(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = data.get("edit_field")
    user = await get_user(message.from_user.id)
    if not user or user["banned"]:
        await state.clear()
        await message.answer("Анкета недоступна.")
        return

    if field == "photo":
        if not message.photo:
            await message.answer("Отправь именно фотографию или /cancel для отмены.")
            return
        value = message.photo[-1].file_id
    else:
        raw = (message.text or "").strip()
        if not raw:
            await message.answer("Отправь текстовое значение или /cancel для отмены.")
            return
        if field == "age":
            if not raw.isdigit():
                await message.answer("Возраст нужно указать числом от 18 до 99.")
                return
            value = int(raw)
        elif field == "bio" and raw == "—":
            value = ""
        else:
            value = raw

    try:
        await update_profile_field(message.from_user.id, field, value)
    except ValueError as error:
        await message.answer(f"{error}. Попробуй ещё раз или отправь /cancel.")
        return
    await state.clear()
    await message.answer("Готово! Данные анкеты обновлены 💜")


@router.callback_query(F.data == "profile:delete")
async def request_profile_deletion(callback: CallbackQuery) -> None:
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Анкета уже удалена.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        "⚠️ Удалить анкету без возможности восстановления?\n\n"
        "Твой профиль исчезнет из поиска. Также удалятся лайки, совпадения, "
        "запросы на знакомство и жалобы, связанные с анкетой. "
        "Платёжные записи Premium сохраняются для учёта платежей.",
        reply_markup=confirm_delete_profile_keyboard(),
    )


@router.callback_query(F.data == "profile:delete:cancel")
async def cancel_profile_deletion(callback: CallbackQuery) -> None:
    await callback.answer("Удаление отменено.")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data == "profile:delete:confirm")
async def confirm_profile_deletion(callback: CallbackQuery) -> None:
    deleted = await delete_user(callback.from_user.id)
    await callback.answer("Анкета удалена." if deleted else "Анкета уже удалена.")
    await callback.message.edit_reply_markup(reply_markup=None)
    if deleted:
        await callback.message.answer(
            "Твоя анкета и связанные действия удалены. 💜\n"
            "Если захочешь вернуться — нажми /start."
        )


@router.callback_query(F.data.startswith("feed:"))
async def react_to_profile(callback: CallbackQuery) -> None:
    try:
        _, action, raw_target_id = (callback.data or "").split(":", 2)
        target_id = int(raw_target_id)
    except (ValueError, AttributeError):
        await callback.answer("Не удалось обработать реакцию.", show_alert=True)
        return

    if action not in {"like", "skip"}:
        await callback.answer("Неизвестная реакция.", show_alert=True)
        return

    viewer_id = callback.from_user.id
    viewer = await get_user(viewer_id)
    target = await get_user(target_id)

    if not viewer or not viewer["approved"] or viewer["banned"]:
        await callback.answer("Твоя анкета ещё не активна.", show_alert=True)
        return
    if not target or not target["approved"] or target["banned"]:
        await callback.answer("Эта анкета больше недоступна.", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    from gender_filter import are_genders_compatible
    if not are_genders_compatible(
        viewer.get("gender"), viewer.get("looking_for"),
        target.get("gender"), target.get("looking_for"),
    ):
        await callback.answer("Эти анкеты не подходят друг другу по настройкам.", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        await send_next_profile(callback.message, viewer_id)
        return

    if action == "like":
        today = date.today()
        if not viewer["is_premium"]:
            from handlers.premium import refresh_channel_subscription
            await refresh_channel_subscription(callback.bot, viewer_id)
        limit = await get_user_like_limit(viewer_id)
        used = await get_daily_like_count(viewer_id, today)
        if used >= limit:
            await callback.answer(
                f"Лимит лайков на сегодня исчерпан: {limit}.",
                show_alert=True,
            )
            return

        await record_view(viewer_id, target_id, "like")
        await increment_daily_likes(viewer_id, today)
        mutual = await has_liked(target_id, viewer_id)
        if mutual:
            await create_match(viewer_id, target_id)
            viewer_link = f"https://t.me/{viewer['username']}"
            target_link = f"https://t.me/{target['username']}"
            try:
                await callback.bot.send_message(
                    viewer_id,
                    f"💜 Взаимная симпатия с {target['name']}!\n"
                    f"Напиши: {target_link}",
                )
            except Exception:
                pass
            try:
                await callback.bot.send_message(
                    target_id,
                    f"💜 Взаимная симпатия с {viewer['name']}!\n"
                    f"Напиши: {viewer_link}",
                )
            except Exception:
                pass
            await callback.answer("Это взаимно! 💜")
        else:
            await callback.answer("Лайк отправлен ❤️")
    else:
        await record_view(viewer_id, target_id, "dislike")
        await callback.answer("Анкета пропущена.")

    await callback.message.edit_reply_markup(reply_markup=None)
    await send_next_profile(callback.message, viewer_id)
