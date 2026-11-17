from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👀 Смотреть")],
        [KeyboardButton(text="📩 Сообщения"), KeyboardButton(text="⭐ Премиум")],
        [KeyboardButton(text="👤 Моя анкета")],
    ],
    resize_keyboard=True,
)

def registration_gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👨 Парень", callback_data="reg:gender:male"),
        InlineKeyboardButton(text="👩 Девушка", callback_data="reg:gender:female"),
    ]])


def registration_looking_for_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👨 Парней", callback_data="reg:looking:male"),
            InlineKeyboardButton(text="👩 Девушек", callback_data="reg:looking:female"),
        ],
        [InlineKeyboardButton(text="💜 Всех", callback_data="reg:looking:all")],
    ])


def moderation_keyboard(tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"mod:approve:{tg_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"mod:reject:{tg_id}"),
    ]])


def profile_keyboard(target_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Нравится", callback_data=f"feed:like:{target_id}"),
            InlineKeyboardButton(text="👎 Пропустить", callback_data=f"feed:skip:{target_id}"),
        ],
        [InlineKeyboardButton(text="✉️ Написать", callback_data=f"msg:compose:{target_id}")],
        [InlineKeyboardButton(text="⚠️ Пожаловаться", callback_data=f"report:begin:{target_id}")],
    ])


def message_request_keyboard(message_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Принять", callback_data=f"msg:accept:{message_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"msg:reject:{message_id}"),
    ]])


def report_moderation_keyboard(report_id: int, target_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⛔ Заблокировать", callback_data=f"report:ban:{report_id}:{target_id}"),
        InlineKeyboardButton(text="🟢 Отклонить жалобу", callback_data=f"report:dismiss:{report_id}"),
    ]])


def premium_keyboard(is_premium: bool = False) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text="🔎 Проверить подписки на 5 каналов",
        callback_data="premium:check",
    )]]
    if not is_premium:
        rows.append([InlineKeyboardButton(
            text="⭐ Купить Premium — 299 Stars",
            callback_data="premium:buy",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)
