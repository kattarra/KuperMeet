import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import settings
from db import init_db
from handlers.moderation import router as moderation_router\nfrom handlers.discovery import router as discovery_router
from handlers.registration import router as registration_router


async def main() -> None:
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is missing. Copy .env.example to .env and set your token.")

    logging.basicConfig(level=logging.INFO)
    await init_db()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(moderation_router)\n    dp.include_router(discovery_router)
    dp.include_router(registration_router)

    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
