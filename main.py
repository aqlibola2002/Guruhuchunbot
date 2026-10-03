import asyncio
import logging
import sys

# Windows konsolida emojilarni to'g'ri chiqarish
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllChatAdministrators,
)

from config import TELEGRAM_TOKEN
from database.db import init_db
from handlers import (
    admin_router,
    events_router,
    stats_router,
    faq_router,
    common_router,
    moderation_router,
    bot_admin_router,
)
from services.scheduler import setup_scheduler

# Log tizimi
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


import os
from aiohttp import web

async def start_render_health_server() -> web.AppRunner | None:
    """Render.com va boshqa bulutli serverlar uchun salomatlik tekshiruvi serveri."""
    port_str = os.environ.get("PORT")
    if not port_str:
        return None
    try:
        port = int(port_str)
        app = web.Application()

        async def handle_ping(request):
            return web.Response(text="Guruhchi Uz Bot is active and healthy! 🛡️🤖", content_type="text/plain")

        app.router.add_get("/", handle_ping)
        app.router.add_get("/health", handle_ping)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Render health server muvaffaqiyatli ishga tushdi (port: {port}) 🌐")
        return runner
    except Exception as e:
        logger.warning(f"Veb-serverni ishga tushirishda xatolik: {e}")
        return None


async def set_bot_commands_and_bio(bot: Bot) -> None:
    """Telegram menyusida buyruqlarni o'rnatish va Bio/Description sozlash."""
    all_group_commands = [
        BotCommand(command="start", description="🤖 Bot imkoniyatlari va ma'lumotlar"),
        BotCommand(command="odam", description="👥 Majburiy a'zo talabi (/odam 5)"),
        BotCommand(command="takliflarim", description="📊 A'zo takliflari (reply qilib)"),
        BotCommand(command="reyting", description="🏆 Faol a'zolar reytingi (TOP-10)"),
        BotCommand(command="statistika", description="📈 Guruh statistikasi va holati"),
        BotCommand(command="qoidalar", description="📜 Guruh qoidalarini ko'rish"),
        BotCommand(command="ogohlantir", description="⚠️ Ogohlantirish (@ id yoki reply)"),
        BotCommand(command="chekla", description="🔇 Yozishni cheklash (10m|2h|1d)"),
        BotCommand(command="hayda", description="🚫 Guruhdan chiqarish (Ban)"),
        BotCommand(command="kechir", description="🔓 Blokdan va cheklovdan ochish"),
        BotCommand(command="tozala", description="🧹 Xabarlarni tozalash (/tozala 20)"),
        BotCommand(command="sozlamalar", description="⚙️ Guruh himoya sozlamalari"),
        BotCommand(command="yangiqoida", description="📝 Yangi guruh qoidasi belgilash"),
        BotCommand(command="elon", description="📢 E'lon va fayllarni qadash (pin)"),
        BotCommand(command="taklifchilar", description="🌟 Ko'p odam qo'shganlar (TOP-10)"),
        BotCommand(command="yordam", description="📖 Barcha buyruqlar qo'llanmasi"),
    ]

    private_commands = [
        BotCommand(command="start", description="Bot imkoniyatlari va ishga tushirish"),
        BotCommand(command="yordam", description="Qo'llanma va buyruqlar"),
        BotCommand(command="panel", description="👑 Super Admin boshqaruv paneli"),
    ]

    try:
        await bot.set_my_commands(all_group_commands, scope=BotCommandScopeDefault())
        await bot.set_my_commands(all_group_commands, scope=BotCommandScopeAllGroupChats())
        await bot.set_my_commands(all_group_commands, scope=BotCommandScopeAllChatAdministrators())
        await bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
        logger.info("Bot buyruqlari muvaffaqiyatli o'rnatildi ✅")
    except Exception as e:
        logger.warning(f"Buyruqlarni o'rnatishda xatolik: {e}")

    try:
        await bot.set_my_short_description(
            short_description="Guruh himoyachisi, APK virus filtri, majburiy a'zo (/odam) va guruh nazorat boti!"
        )
    except Exception as e:
        logger.warning(f"Qisqa bio o'rnatishda: {e}")

    try:
        desc = (
            "Guruhchi — Telegram guruhlarini professional himoya qilish va boshqarish boti!\n\n"
            "Asosiy imkoniyatlar:\n"
            "• APK virus fayllarini avtomatik o'chirish\n"
            "• Forward qilingan xabarlarni o'chirish\n"
            "• Majburiy a'zo talabi (/odam 5)\n"
            "• Qo'shilgan a'zolarni sanash (/takliflarim)\n"
            "• Reklama va spam xabarlarni o'chirish\n"
            "• Begona havolalarni (linklar) bloklash\n"
            "• Xabarlarni tozalash (/tozala 20)\n"
            "• Jazo choralari (/ogohlantir, /chekla, /hayda, /kechir)\n"
            "• Statistika va reyting (/statistika, /reyting)\n"
            "• Guruh qoidalari (/qoidalar, /yangiqoida)\n\n"
            "Meni guruhingizga qo'shib, Admin huquqini bering!"
        )
        await bot.set_my_description(description=desc)
        logger.info("Bot bio va tavsifi muvaffaqiyatli yangilandi ✅")
    except Exception as e:
        logger.warning(f"Tavsif o'rnatishda: {e}")


async def main() -> None:
    logger.info("Bot ishga tushirilmoqda...")

    # Ma'lumotlar bazasini ishga tushirish
    await init_db()
    logger.info("Ma'lumotlar bazasi tayyorlandi ✅")

    # Render yoki bulutli serverlar uchun veb-server
    web_runner = await start_render_health_server()

    # Bot va Dispatcher
    bot = Bot(
        token=TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Rejalashtirilgan xabarlar (Scheduler)
    scheduler = setup_scheduler(bot)

    # Buyruqlar menyusini va Bio/Description sozlash
    await set_bot_commands_and_bio(bot)

    # Routerlarni to'g'ri ketma-ketlikda ulash
    dp.include_router(bot_admin_router)
    dp.include_router(admin_router)
    dp.include_router(events_router)
    dp.include_router(stats_router)
    dp.include_router(faq_router)
    dp.include_router(common_router)
    dp.include_router(moderation_router)  # Moderatsiya oxirida bo'lishi shart

    # Bot ma'lumotlarini olish
    me = await bot.get_me()
    logger.info(f"Bot muvaffaqiyatli ulandi: @{me.username} ({me.first_name}) 🚀")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        if web_runner:
            await web_runner.cleanup()
        await bot.session.close()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Dastur to'xtatildi.")
