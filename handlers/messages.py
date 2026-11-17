from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from db import (
    create_message_request,
    get_message_request,
    get_pending_message_requests,
    get_user,
    update_message_request,
)
from keyboards import message_request_keyboard

router = Router()


class ComposeMessage(StatesGroup):
    text = State()


@router.callback_query(F.data.startswith("msg:compose:"))
async def start_compose(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        target_id = int((callback.data or "").rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("Анкета не найдена.", show_alert=True)
        return

    sender = await get_user(callback.from_user.id)
    target = await get_user(target_id)
    if (
        not sender or not sender["approved"] or sender["banned"]
        or not target or not target["approved"] or target["banned"]
        or sender["age_segment"] != target["age_segment"]
    ):
        await callback.answer("Сейчас нельзя отправить запрос этому пользователю.", show_alert=True)
        return

    await state.update_data(target_id=target_id)
    await state.set_state(ComposeMessage.text)
    await callback.message.answer(
        f"Напиши сообщение для {target['name']} (до 300 символов).\n"
        "Это будет запрос на знакомство. Не отправляй телефон или личные данные.\n"
        "Для отмены отправь /cancel."
    )
    await callback.answer()


@router.message(Command("cancel"), ComposeMessage.text)
async def cancel_compose(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменил отправку.")


@router.message(ComposeMessage.text)
async def send_intro_request(message: Message, state: FSMContext) -> None:
    body = (message.text or "").strip()
    if not body:
        await message.answer("Отправь текстовое сообщение до 300 символов.")
        return
    if len(body) > 300:
        await message.answer(f"Слишком длинно: {len(body)}/300 символов. Сократи сообщение.")
        return

    data = await state.get_data()
    target_id = int(data["target_id"])
    try:
        request_id = await create_message_request(
            from_id=message.from_user.id,
            to_id=target_id,
            text=body,
        )
    except ValueError as exc:
        await message.answer(str(exc))
        await state.clear()
        return

    await state.clear()
    target = await get_user(target_id)
    try:
        await message.bot.send_message(
            target_id,
            f"💌 Новый запрос на знакомство от {message.from_user.full_name}:\n\n"
            f"«{body}»\n\n"
            "Принять запрос и открыть друг другу Telegram-профили?",
            reply_markup=message_request_keyboard(request_id),
        )
    except Exception:
        await message.answer(
            "Не получилось доставить запрос. Возможно, пользователь ещё не запускал бота. "
            "Попробуй позже."
        )
        return

    await message.answer(f"Запрос отправлен {target['name']} 💜")


@router.message(F.text == "📩 Сообщения")
async def inbox(message: Message) -> None:
    user = await get_user(message.from_user.id)
    if not user or not user["approved"] or user["banned"]:
        await message.answer("Раздел сообщений станет доступен после одобрения анкеты.")
        return

    requests = await get_pending_message_requests(message.from_user.id)
    if not requests:
        await message.answer("Пока новых запросов нет. Но всё ещё впереди 💜")
        return

    await message.answer(f"У тебя {len(requests)} новых запрос(ов):")
    for request in requests:
        caption = (
            f"💌 Запрос от {request['sender_name']}, {request['sender_age']}\n"
            f"📍 {request['sender_city']}\n\n"
            f"«{request['text']}»"
        )
        await message.answer(
            caption,
            reply_markup=message_request_keyboard(int(request["id"])),
        )


@router.callback_query(F.data.startswith("msg:accept:"))
@router.callback_query(F.data.startswith("msg:reject:"))
async def handle_request_decision(callback: CallbackQuery) -> None:
    try:
        action, raw_id = (callback.data or "").split(":")[1:]
        request_id = int(raw_id)
    except (ValueError, AttributeError):
        await callback.answer("Некорректный запрос.", show_alert=True)
        return

    request = await get_message_request(request_id)
    if not request or int(request["to_id"]) != callback.from_user.id:
        await callback.answer("Этот запрос не для тебя.", show_alert=True)
        return
    if request["status"] != "pending":
        await callback.answer("На этот запрос уже ответили.", show_alert=True)
        return

    recipient = await get_user(callback.from_user.id)
    sender = await get_user(int(request["from_id"]))
    if (
        not recipient or not recipient["approved"] or recipient["banned"]
        or not sender or not sender["approved"] or sender["banned"]
    ):
        await callback.answer("Один из профилей больше недоступен.", show_alert=True)
        return

    new_status = "accepted" if action == "accept" else "rejected"
    updated = await update_message_request(
        request_id,
        callback.from_user.id,
        new_status,
    )
    if not updated:
        await callback.answer("Запрос уже обработан.", show_alert=True)
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    if action == "accept":
        recipient_link = f"https://t.me/{recipient['username']}"
        sender_link = f"https://t.me/{sender['username']}"
        try:
            await callback.bot.send_message(
                int(request["from_id"]),
                f"💜 {recipient['name']} принял(а) твой запрос!\n"
                f"Можешь написать: {recipient_link}",
            )
        except Exception:
            pass
        try:
            await callback.bot.send_message(
                callback.from_user.id,
                f"Ты принял(а) запрос от {sender['name']} 💜\n"
                f"Можешь написать: {sender_link}",
            )
        except Exception:
            pass
        await callback.answer("Запрос принят 💜")
    else:
        try:
            await callback.bot.send_message(
                int(request["from_id"]),
                f"{recipient['name']} пока не готов(а) к знакомству. "
                "Не расстраивайся — впереди ещё много людей.",
            )
        except Exception:
            pass
        await callback.answer("Запрос отклонён.")
