from __future__ import annotations

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from database.db import db

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")


async def send_morning_message(bot: Bot) -> None:
    """Barcha guruhlarga ertalabki salom yo'llash."""
    try:
        groups = await db.get_all_active_groups()
        for g in groups:
            if g.get("scheduled_enabled", 1) == 1:
                chat_id = g["chat_id"]
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=(
                            "☀️ **Xayrli tong, aziz guruh a'zolari!**\n\n"
                            "Barchangizga yangi kunda omad, baraka va a'lo kayfiyat tilaymiz! 🌟\n"
                            "Guruhimizda bir-biringizga hurmat bilan muloqot qilishingizni eslatib o'tamiz. 😊"
                        ),
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.debug(f"Guruhga ({chat_id}) ertalabki xabar yuborishda xatolik: {e}")
    except Exception as err:
        logger.error(f"Ertalabki xabarlar xatosi: {err}")


async def send_evening_message(bot: Bot) -> None:
    """Barcha guruhlarga kechki xayrli tun xabarini yo'llash."""
    try:
        groups = await db.get_all_active_groups()
        for g in groups:
            if g.get("scheduled_enabled", 1) == 1:
                chat_id = g["chat_id"]
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=(
                            "🌙 **Xayrli tun, hurmatli do'stlar!**\n\n"
                            "Kuningiz mazmunli o'tgan bo'lsin. Guruh a'zolarining osoyishtaligini "
                            "saqlash maqsadida kechki payt ortiqcha xabarlar yozmaslikni so'raymiz. "
                            "Yaxshi dam oling! 😴✨"
                        ),
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.debug(f"Guruhga ({chat_id}) kechki xabar yuborishda xatolik: {e}")
    except Exception as err:
        logger.error(f"Kechki xabarlar xatosi: {err}")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Rejalashtirilgan xabarlar xizmatini ishga tushirish."""
    # Har kuni ertalab soat 08:30 da
    scheduler.add_job(
        send_morning_message,
        trigger="cron",
        hour=8,
        minute=30,
        args=[bot],
        id="morning_greeting",
        replace_existing=True,
    )

    # Har kuni kechasi soat 22:30 da
    scheduler.add_job(
        send_evening_message,
        trigger="cron",
        hour=22,
        minute=30,
        args=[bot],
        id="evening_greeting",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("⏰ Rejalashtirilgan xabarlar (Scheduler) ishga tushdi.")
    return scheduler
