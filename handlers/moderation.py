from aiogram import F, Router
from aiogram.types import CallbackQuery

from config import settings
from db import get_user, set_user_approved, delete_user
from keyboards import MAIN_MENU

router = Router()


@router.callback_query(F.data.startswith("mod:"))
async def moderate_profile(callback: CallbackQuery) -> None:
    if callback.from_user.id not in settings.admin_ids:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    try:
        _, action, raw_id = (callback.data or "").split(":", 2)
        tg_id = int(raw_id)
    except (ValueError, AttributeError):
        await callback.answer("Некорректная команда.", show_alert=True)
        return

    if action not in {"approve", "reject"}:
        await callback.answer("Неизвестное действие.", show_alert=True)
        return

    user = await get_user(tg_id)
    if not user:
        await callback.answer("Анкета уже удалена.", show_alert=True)
        return

    if user["banned"]:
        await callback.answer("Пользователь заблокирован.", show_alert=True)
        return

    if action == "approve":
        await set_user_approved(tg_id, True)
        try:
            await callback.bot.send_message(
                tg_id,
                "Твоя анкета прошла модерацию! 💜\nДобро пожаловать в KuperMeet.",
                reply_markup=MAIN_MENU,
            )
        except Exception:
            pass
        await callback.message.edit_caption(
            caption=(callback.message.caption or "") + "\n\n✅ ОДОБРЕНО",
            reply_markup=None,
        )
        await callback.answer("Анкета одобрена.")
    else:
        await delete_user(tg_id)
        try:
            await callback.bot.send_message(
                tg_id,
                "К сожалению, анкета не прошла модерацию. "
                "Можешь создать новую, исправив спорные моменты: /start",
            )
        except Exception:
            pass
        await callback.message.edit_caption(
            caption=(callback.message.caption or "") + "\n\n❌ ОТКЛОНЕНО",
            reply_markup=None,
        )
        await callback.answer("Анкета отклонена и удалена.")
