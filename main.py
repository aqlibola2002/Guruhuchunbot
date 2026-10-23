import asyncio
import logging
import os
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
        BotCommand(command="admin", description="🛡 Bot holati va admin boshqaruv paneli"),
        BotCommand(command="sozlamalar", description="⚙️ Guruh himoya sozlamalari"),
        BotCommand(command="tun", description="🌙 Tungi rejimni sozlash (/tun on|off|23:00-07:00)"),
        BotCommand(command="zayafka", description="📥 Zayafkalarni avto-qabul qilish"),
        BotCommand(command="chekla", description="🔇 Yozishni cheklash (10m|2h|1d)"),
        BotCommand(command="hayda", description="🚫 Guruhdan chiqarish va bloklash (Ban)"),
        BotCommand(command="tozala", description="🧹 Xabarlarni tozalash (/tozala 20 yoki reply)"),
        BotCommand(command="elon", description="📢 E'lon va fayllarni qadash (pin)"),
        BotCommand(command="odam", description="👥 Majburiy a'zo talabi (/odam 5)"),
        BotCommand(command="nol", description="0️⃣ A'zo takliflarini 0 qilish (reply)"),
        BotCommand(command="kanal", description="📡 Majburiy kanal qo'shish/boshqarish"),
        BotCommand(command="takliflarim", description="📊 Siz qo'shgan a'zolar soni"),
        BotCommand(command="toptaklif", description="🥇 Eng ko'p odam qo'shganlar reytingi"),
        BotCommand(command="reyting", description="🏆 Faol a'zolar reytingi (TOP-10)"),
        BotCommand(command="statistika", description="📈 Guruh statistikasi va holati"),
        BotCommand(command="yordam", description="📖 Barcha buyruqlar qo'llanmasi"),
    ]

    private_commands = [
        BotCommand(command="start", description="Bot imkoniyatlari va ishga tushirish"),
        BotCommand(command="yordam", description="Qo'llanma va buyruqlar"),
        BotCommand(command="panel", description="👑 Super Admin boshqaruv paneli"),
        BotCommand(command="backup", description="💾 Baza zaxirasini yuklab olish (.db)"),
        BotCommand(command="send", description="📢 Barcha guruhlarga xabar yuborish"),
        BotCommand(command="send_users", description="👤 Barcha foydalanuvchilarga xabar yuborish"),
        BotCommand(command="send_all", description="🌐 Hammaga xabar yuborish"),
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
            short_description="💎 Telegram guruh va kanallari uchun eng kuchli, premium himoya va avtomatlashtirish boti! 🛡️⚡️"
        )
    except Exception as e:
        logger.warning(f"Qisqa bio o'rnatishda: {e}")

    try:
        desc = (
            "👑 GURUHCHI UZ — PREMIUM GURUH NAZORATCHISI VA HIMOYACHISI! 🛡\n\n"
            "Guruhingizni tartibga solish, reklama va viruslardan tozalash hamda a'zolarni oson ko'paytirish uchun 24/7 to'liq avtomatik ishlaydi.\n\n"
            "💎 ASOSIY PREMIUM IMKONIYATLAR:\n"
            "├ 🌙 Tungi rejim (guruhni tunda avto-yopish va ertalab ochish)\n"
            "├ ⚡️ Anti-Flood (soniyada xabar yog'diruvchi spamerlarni darhol cheklash)\n"
            "├ 📥 Zayafkalar avto-qabuli (guruh va kanal arizalarini 1 soniyada tasdiqlash)\n"
            "├ 🈲 Arab/Sharqiy reyd-botlar va xorijiy spamlarni bir zumda tozalash\n"
            "├ 🤖 Begona Inline-botlar va yashirin reklamalarni bloklash\n"
            "├ 🦠 Anti-APK xavfli virus/troyan fayllarini avtomatik yo'q qilish\n"
            "├ 🔗 Begona havola (link), reklama va so'kinishlarni o'chirish\n"
            "├ 👥 Majburiy odam qo'shish talabi va TOP Taklifchilar reytingi\n"
            "├ 📢 Majburiy homiy kanalga a'zo bo'lish tizimi\n"
            "├ 🧹 Xabarlarni chaqmoq tezligida tozalash (/tozala)\n"
            "└ ⚙️ Yagona zamonaviy tugmali boshqaruv paneli (/sozlamalar)\n\n"
            "🚀 Guruhingizga qo'shing va Administrator huquqini bering!"
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
        needed_updates = ["message", "edited_message", "callback_query", "chat_member", "my_chat_member", "chat_join_request"]
        resolved = dp.resolve_used_update_types() or []
        final_updates = list(set(list(resolved) + needed_updates))
        await dp.start_polling(bot, allowed_updates=final_updates)
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

