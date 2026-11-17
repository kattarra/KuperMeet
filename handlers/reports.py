from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import settings
from db import (
    ban_user,
    create_report,
    get_report,
    get_user,
    resolve_report,
)
from keyboards import report_moderation_keyboard

router = Router()


class ReportFlow(StatesGroup):
    reason = State()


@router.callback_query(F.data.startswith("report:begin:"))
async def begin_report(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        target_id = int((callback.data or "").rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("Анкета не найдена.", show_alert=True)
        return

    reporter = await get_user(callback.from_user.id)
    target = await get_user(target_id)
    if (
        not reporter or not reporter["approved"] or reporter["banned"]
        or not target or not target["approved"] or target["banned"]
        or target_id == callback.from_user.id
    ):
        await callback.answer("Нельзя отправить жалобу на эту анкету.", show_alert=True)
        return

    await state.update_data(target_id=target_id)
    await state.set_state(ReportFlow.reason)
    await callback.message.answer(
        f"Почему ты хочешь пожаловаться на анкету {target['name']}?\n"
        "Опиши проблему одним сообщением (до 200 символов).\n"
        "Для отмены отправь /cancel."
    )
    await callback.answer()


@router.message(Command("cancel"), ReportFlow.reason)
async def cancel_report(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Жалоба отменена.")


@router.message(ReportFlow.reason)
async def submit_report(message: Message, state: FSMContext) -> None:
    reason = (message.text or "").strip()
    if not reason:
        await message.answer("Напиши причину жалобы текстом или отправь /cancel.")
        return
    if len(reason) > 200:
        await message.answer(f"Слишком длинно: {len(reason)}/200 символов. Сократи текст.")
        return

    data = await state.get_data()
    target_id = int(data["target_id"])
    reporter_id = message.from_user.id
    try:
        report_id = await create_report(reporter_id, target_id, reason)
    except ValueError as exc:
        await message.answer(str(exc))
        await state.clear()
        return

    await state.clear()
    report = await get_report(report_id)
    if not report:
        await message.answer("Жалоба сохранена, но не удалось загрузить её карточку.")
        return

    caption = (
        f"⚠️ ЖАЛОБА №{report_id}\n\n"
        f"На пользователя: {report['target_name']}, {report['target_age']}\n"
        f"Telegram ID: {target_id}\n"
        f"Username: @{report['target_username'] or 'не указан'}\n"
        f"От: {report['reporter_name']} (ID {reporter_id})\n\n"
        f"Причина: {reason}"
    )
    keyboard = report_moderation_keyboard(report_id, target_id)
    delivered = False

    if settings.report_channel:
        try:
            await message.bot.send_photo(
                chat_id=settings.report_channel,
                photo=report["target_photo"],
                caption=caption,
                reply_markup=keyboard,
            )
            delivered = True
        except Exception:
            delivered = False
    else:
        for admin_id in settings.admin_ids:
            try:
                await message.bot.send_photo(
                    chat_id=admin_id,
                    photo=report["target_photo"],
                    caption=caption,
                    reply_markup=keyboard,
                )
                delivered = True
            except Exception:
                continue

    if delivered:
        await message.answer("Жалоба отправлена модераторам. Спасибо, что помогаешь сохранять порядок 💜")
    else:
        await message.answer(
            "Жалоба сохранена, но уведомление модераторам не доставлено. "
            "Администратор должен проверить REPORT_CHANNEL или ADMIN_IDS."
        )


@router.callback_query(F.data.startswith("report:ban:"))
@router.callback_query(F.data.startswith("report:dismiss:"))
async def moderate_report(callback: CallbackQuery) -> None:
    if callback.from_user.id not in settings.admin_ids:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    parts = (callback.data or "").split(":")
    try:
        action = parts[1]
        report_id = int(parts[2])
        target_id = int(parts[3]) if action == "ban" else None
    except (ValueError, IndexError):
        await callback.answer("Некорректная команда.", show_alert=True)
        return

    report = await get_report(report_id)
    if not report or report["status"] != "pending":
        await callback.answer("Жалоба уже обработана или не найдена.", show_alert=True)
        return

    if action == "ban":
        if target_id != int(report["target_id"]):
            await callback.answer("ID пользователя не совпадает с жалобой.", show_alert=True)
            return
        await ban_user(target_id)
        await resolve_report(report_id, "actioned")
        try:
            await callback.bot.send_message(
                target_id,
                "Твой профиль KuperMeet заблокирован после проверки жалобы модерацией. "
                "Если считаешь это ошибкой, обратись к администрации.",
            )
        except Exception:
            pass
        result_text = "\n\n⛔ ПОЛЬЗОВАТЕЛЬ ЗАБЛОКИРОВАН"
        await callback.answer("Пользователь заблокирован.")
    elif action == "dismiss":
        await resolve_report(report_id, "dismissed")
        result_text = "\n\n🟢 ЖАЛОБА ОТКЛОНЕНА"
        await callback.answer("Жалоба отклонена.")
    else:
        await callback.answer("Неизвестное действие.", show_alert=True)
        return

    await callback.message.edit_caption(
        caption=(callback.message.caption or "") + result_text,
        reply_markup=None,
    )
