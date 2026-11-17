from datetime import date

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from db import (
    create_match,
    get_daily_like_count,
    get_next_profile,
    get_user,
    get_user_like_limit,
    has_liked,
    increment_daily_likes,
    record_view,
)
from keyboards import profile_keyboard

router = Router()


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
    if user["banned"]:
        await message.answer("Доступ к KuperMeet ограничен.")
        return
    status = "Одобрена ✅" if user["approved"] else "На модерации ⏳"
    caption = (
        f"👤 {user['name']}, {user['age']}\n"
        f"📍 {user['city']}\n"
        f"Статус: {status}\n\n"
        f"{user['bio'] or 'Описание не добавлено.'}"
    )
    await message.answer_photo(photo=user["photo_id"], caption=caption)


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

    if action == "like":
        today = date.today()
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
