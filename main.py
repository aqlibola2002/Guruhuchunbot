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
        BotCommand(command="xavfsizlik", description="🛡 Guruhning to'liq kiber-himoya auditi"),
        BotCommand(command="qulf", description="🔒 Guruhni zudlik bilan qulflash/yopish"),
        BotCommand(command="ochish", description="🔓 Guruhni qayta ochish"),
        BotCommand(command="chekla", description="🔇 Yozishni cheklash (10m|2h|1d)"),
        BotCommand(command="unmute", description="🔊 Yozish cheklovini bekor qilish"),
        BotCommand(command="hayda", description="🚫 Guruhdan chiqarish va bloklash (Ban)"),
        BotCommand(command="unban", description="🕊 Foydalanuvchini bandan chiqarish"),
        BotCommand(command="sozqoshish", description="🛑 Taqiqlangan so'z qo'shish"),
        BotCommand(command="sozlar", description="📋 Taqiqlangan so'zlar ro'yxati"),
        BotCommand(command="tozala", description="🧹 Xabarlarni tozalash (/tozala 20)"),
        BotCommand(command="tun", description="🌙 Tungi rejimni sozlash (/tun on|off)"),
        BotCommand(command="sekin", description="⏳ Sekin rejim (/sekin 10|30|60|off)"),
        BotCommand(command="odam", description="👥 Majburiy a'zo talabi (/odam 5)"),
        BotCommand(command="nol", description="0️⃣ A'zo takliflarini 0 qilish (reply)"),
        BotCommand(command="kanal", description="📡 Majburiy kanal qo'shish/boshqarish"),
        BotCommand(command="takliflarim", description="📊 Siz qo'shgan a'zolar soni"),
        BotCommand(command="toptaklif", description="🥇 Eng ko'p odam qo'shganlar reytingi"),
        BotCommand(command="reyting", description="🏆 Faol a'zolar reytingi (TOP-10)"),
        BotCommand(command="statistika", description="📈 Guruh monitoringi va faollik"),
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

    # Bot ishga tushganda Super Adminlarga va guruhlarga onlayn xabarni yetkazish
    async def on_startup() -> None:
        from config import ADMIN_IDS
        from datetime import datetime
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stats = await db.get_global_stats()

        # 1. Super Adminlarga to'liq ishga tushish xabari
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"🚀 **GURUHCHI UZ — BOT MUVAFFAQIYATLI ISHGA TUSHDI!** 💎\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🤖 **Bot:** @{me.username} ({me.first_name})\n"
                        f"⚡️ **Tizim holati:** Barcha 100% kiber-himoya modullari faol\n"
                        f"🏛 **Ulangan guruhlar:** {stats['total_groups']} ta\n"
                        f"👤 **Jami a'zolar:** {stats['total_users']:,} nafar\n"
                        f"💬 **Qayd etilgan xabarlar:** {stats['total_messages']:,} ta\n"
                        f"👥 **Takliflar:** {stats['total_invites']:,} ta\n"
                        f"💾 **Baza xavfsizligi:** SQLite WAL rejimida to'liq tiklandi ✅\n"
                        f"⏱ **Vaqt:** `{now_str}`\n\n"
                        f"👑 Boshqaruv paneli: `/panel` | Guruhlar: `/guruhlar`"
                    ),
                    parse_mode="Markdown",
                )
            except Exception as ex:
                logger.warning(f"Adminga start xabarida: {ex}")

        # 2. Guruhlarga start xabari (agar yoqilgan bo'lsa)
        startup_notify = await db.get_bot_setting("startup_notify_groups", "1")
        if startup_notify == "1":
            groups = await db.get_all_active_groups()
            for g in groups:
                cid = g.get("chat_id")
                if not cid:
                    continue
                try:
                    msg = await bot.send_message(
                        chat_id=cid,
                        text=(
                            f"🛡 **GURUHCHI UZ — KIBER-HIMOYA TIZIMI ONLAYN!** 🟢\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"Hurmatli guruh a'zolari va administratorlar!\n"
                            f"Bot muvaffaqiyatli ishga tushirildi va guruhingiz 24/7 to'liq nazorat ostida:\n\n"
                            f"✅ Barcha so'kinish va haqoratlarni tozalash — Faol\n"
                            f"✅ Reklama, spam va begona havolalar filtri — Faol\n"
                            f"✅ Chet el (arab/sharqiy) spambotlar filtri — Faol\n"
                            f"✅ Zararli .APK viruslar blokirovkasi — Faol\n"
                            f"✅ A'zolar va qoidalar monitoringi — Faol\n\n"
                            f"👮‍♂️ Guruh xavfsiz va tinch muloqot uchun tayyor! ✨"
                        ),
                        parse_mode="Markdown",
                    )
                    async def _del_start(m, d=60):
                        await asyncio.sleep(d)
                        try:
                            await m.delete()
                        except Exception:
                            pass
                    asyncio.create_task(_del_start(msg, 60))
                    await asyncio.sleep(0.1)
                except Exception:
                    pass

    try:
        await on_startup()
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

