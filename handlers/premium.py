from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from config import settings
from db import (
    get_user,
    register_premium_payment,
    set_channel_subscription,
)
from keyboards import premium_keyboard

router = Router()

PREMIUM_PRICE = 299
PREMIUM_PAYLOAD = "kupermeet_premium_lifetime_v1"


def configured_channels() -> tuple[str, ...]:
    channels = tuple(
        channel.strip()
        for channel in settings.channels
        if channel.strip() and "your_channel" not in channel.lower()
    )
    # The benefit is explicitly tied to all five configured channels.
    return channels if len(channels) == 5 else ()


async def refresh_channel_subscription(bot, user_id: int) -> bool:
    """Check all five channels against Telegram and persist the result.

    The bot must be an administrator in each channel for reliable membership
    checks. Any missing channel or API error fails closed.
    """
    channels = configured_channels()
    if not channels:
        await set_channel_subscription(user_id, False)
        return False

    for channel in channels:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in {"creator", "administrator", "member"}:
                continue
            if member.status == "restricted" and getattr(member, "is_member", False):
                continue
            await set_channel_subscription(user_id, False)
            return False
        except Exception:
            await set_channel_subscription(user_id, False)
            return False

    await set_channel_subscription(user_id, True)
    return True


@router.message(F.text == "⭐ Премиум")
async def premium_page(message: Message) -> None:
    user = await get_user(message.from_user.id)
    if not user or not user["approved"] or user["banned"]:
        await message.answer("Сначала нужна одобренная анкета KuperMeet 💜")
        return

    if user["is_premium"]:
        text = (
            "⭐ KuperMeet Premium уже активен навсегда!\n\n"
            "Тебе доступны 100 лайков в день и приоритет в выдаче анкет."
        )
    else:
        text = (
            "⭐ KuperMeet Premium\n\n"
            "299 Telegram Stars — единоразовая оплата, доступ навсегда.\n"
            "• 100 лайков в день\n"
            "• Приоритет в выдаче анкет\n\n"
            "Либо подпишись на все пять каналов Kuper — это тоже откроет "
            "100 лайков в день, пока подписки подтверждаются."
        )
    await message.answer(text, reply_markup=premium_keyboard(bool(user["is_premium"])))


@router.callback_query(F.data == "premium:check")
async def check_channels(callback: CallbackQuery) -> None:
    user = await get_user(callback.from_user.id)
    if not user or not user["approved"] or user["banned"]:
        await callback.answer("Нужна активная анкета.", show_alert=True)
        return

    if user["is_premium"]:
        await callback.answer("Premium уже активен 💜")
        return

    channels = configured_channels()
    if not channels:
        await set_channel_subscription(callback.from_user.id, False)
        await callback.answer(
            "Администратор ещё не настроил все пять каналов.",
            show_alert=True,
        )
        return

    is_subscribed = await refresh_channel_subscription(
        callback.bot,
        callback.from_user.id,
    )
    if is_subscribed:
        await callback.message.answer(
            "Все пять подписок подтверждены! Теперь у тебя 100 лайков в день 💜"
        )
        await callback.answer("Подписки подтверждены!")
    else:
        await callback.answer(
            "Не вижу подписку на все пять каналов. Подпишись и проверь ещё раз.",
            show_alert=True,
        )


@router.callback_query(F.data == "premium:buy")
async def buy_premium(callback: CallbackQuery) -> None:
    user = await get_user(callback.from_user.id)
    if not user or not user["approved"] or user["banned"]:
        await callback.answer("Нужна активная анкета.", show_alert=True)
        return
    if user["is_premium"]:
        await callback.answer("Premium уже активен 💜", show_alert=True)
        return

    await callback.message.answer_invoice(
        title="KuperMeet Premium",
        description=(
            "Бессрочный Premium: 100 лайков в день и приоритет "
            "в выдаче анкет. Единоразовая оплата."
        ),
        payload=PREMIUM_PAYLOAD,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="KuperMeet Premium навсегда", amount=PREMIUM_PRICE)],
    )
    await callback.answer()


@router.pre_checkout_query()
async def process_pre_checkout(query: PreCheckoutQuery) -> None:
    user = await get_user(query.from_user.id)
    valid = (
        query.invoice_payload == PREMIUM_PAYLOAD
        and query.currency == "XTR"
        and query.total_amount == PREMIUM_PRICE
        and user is not None
        and bool(user["approved"])
        and not bool(user["banned"])
        and not bool(user["is_premium"])
    )
    if not valid:
        await query.answer(
            ok=False,
            error_message="Не удалось подтвердить покупку. Открой Premium и попробуй снова.",
        )
        return
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_premium_payment(message: Message) -> None:
    payment = message.successful_payment
    if (
        payment.invoice_payload != PREMIUM_PAYLOAD
        or payment.currency != "XTR"
        or payment.total_amount != PREMIUM_PRICE
    ):
        await message.answer(
            "Платёж получен, но его параметры не совпали с Premium. "
            "Напиши администрации, не отправляй оплату повторно."
        )
        return

    status = await register_premium_payment(
        user_id=message.from_user.id,
        telegram_charge_id=payment.telegram_payment_charge_id,
        amount=payment.total_amount,
        currency=payment.currency,
    )

    if status == "duplicate":
        # Telegram may redeliver the same update; the original payment is already handled.
        return

    if status == "already_premium":
        try:
            await message.bot.refund_star_payment(
                user_id=message.from_user.id,
                telegram_payment_charge_id=payment.telegram_payment_charge_id,
            )
            await message.answer(
                "У тебя уже был активен Premium, поэтому повторная оплата "
                "автоматически возвращена. ⭐"
            )
        except Exception:
            await message.answer(
                "Похоже, Premium уже был активен до этой оплаты. "
                "Не оплачивай повторно — напиши /paysupport, мы проверим возврат."
            )
        return

    if status != "activated":
        try:
            await message.bot.refund_star_payment(
                user_id=message.from_user.id,
                telegram_payment_charge_id=payment.telegram_payment_charge_id,
            )
        except Exception:
            pass
        await message.answer(
            "Не удалось активировать Premium для этого профиля. "
            "Если платёж списался, напиши /paysupport."
        )
        return

    await message.answer(
        "Оплата прошла успешно! ⭐\n\n"
        "KuperMeet Premium активирован навсегда. "
        "Теперь у тебя 100 лайков в день и приоритет в выдаче. 💜"
    )


@router.message(Command("terms"))
async def premium_terms(message: Message) -> None:
    await message.answer(
        "Условия KuperMeet Premium\n\n"
        "1. Premium стоит 299 Telegram Stars и приобретается единоразово.\n"
        "2. После подтверждения платежа доступ активируется бессрочно для "
        "Telegram-аккаунта, с которого совершена оплата.\n"
        "3. Premium предоставляет лимит до 100 лайков в сутки и приоритет "
        "анкеты в выдаче.\n"
        "4. Premium не гарантирует взаимные симпатии, сообщения или конкретное "
        "количество просмотров.\n"
        "5. При блокировке аккаунта за нарушение правил сервиса доступ к "
        "функциям может быть ограничен.\n"
        "6. По вопросам оплаты и возврата используй команду /paysupport."
    )


@router.message(Command("paysupport"))
async def premium_payment_support(message: Message) -> None:
    if not settings.admin_ids:
        await message.answer(
            "Поддержка платежей пока не настроена. Попробуй позже."
        )
        return

    support_text = (
        "🧾 Запрос по оплате KuperMeet Premium\n"
        f"Пользователь: {message.from_user.full_name}\n"
        f"Telegram ID: {message.from_user.id}\n"
        f"Username: @{message.from_user.username or 'не указан'}\n\n"
        f"Сообщение: {message.text or '/paysupport'}"
    )
    delivered = False
    for admin_id in settings.admin_ids:
        try:
            await message.bot.send_message(admin_id, support_text)
            delivered = True
        except Exception:
            continue

    if delivered:
        await message.answer(
            "Запрос отправлен администрации. Мы проверим платёж и ответим тебе 💜"
        )
    else:
        await message.answer(
            "Не удалось связаться с поддержкой. Попробуй позже."
        )
