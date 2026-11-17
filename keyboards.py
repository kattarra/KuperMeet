from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👀 Смотреть")],
        [KeyboardButton(text="📩 Сообщения"), KeyboardButton(text="⭐ Премиум")],
        [KeyboardButton(text="👤 Моя анкета")],
    ],
    resize_keyboard=True,
)

def moderation_keyboard(tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"mod:approve:{tg_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"mod:reject:{tg_id}"),
    ]])
