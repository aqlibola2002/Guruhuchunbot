from __future__ import annotations

import asyncio
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
                await asyncio.sleep(0.05)
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
                await asyncio.sleep(0.05)
    except Exception as err:
        logger.error(f"Kechki xabarlar xatosi: {err}")


from datetime import datetime
from aiogram.types import ChatPermissions

def is_in_time_range(now_str: str, start_str: str, end_str: str) -> bool:
    """now_str 'HH:MM' vaqti start_str va end_str oralig'idami?"""
    try:
        now_t = datetime.strptime(now_str, "%H:%M").time()
        start_t = datetime.strptime(start_str, "%H:%M").time()
        end_t = datetime.strptime(end_str, "%H:%M").time()
        if start_t <= end_t:
            return start_t <= now_t < end_t
        else:
            return now_t >= start_t or now_t < end_t
    except Exception:
        return False


async def check_night_mode(bot: Bot) -> None:
    """Barcha guruhlarda Tungi rejim (Night Mode) vaqtini tekshirib, guruhni yopish yoki ochish."""
    try:
        now_str = datetime.now().strftime("%H:%M")
        groups = await db.get_all_active_groups()
        for g in groups:
            if g.get("night_mode_enabled", 0) == 1:
                chat_id = g["chat_id"]
                start_t = g.get("night_mode_start", "23:00") or "23:00"
                end_t = g.get("night_mode_end", "07:00") or "07:00"
                is_night = is_in_time_range(now_str, start_t, end_t)
                is_locked = g.get("night_mode_is_locked", 0) == 1

                if is_night and not is_locked:
                    try:
                        await bot.set_chat_permissions(
                            chat_id=chat_id,
                            permissions=ChatPermissions(can_send_messages=False),
                        )
                        await db.set_night_mode_lock_state(chat_id, 1)
                        await bot.send_message(
                            chat_id=chat_id,
                            text=(
                                f"🌙 **TUNGI REJIM FAOL** 😴\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                f"Guruh tungi osoyishtalik rejimiga o'tkazildi.\n"
                                f"⏰ **Sukunat vaqti:** `{start_t}` — `{end_t}`\n\n"
                                f"✨ *Tongda soat {end_t} da guruh avtomatik qayta ochiladi. Barchaga xayrli tun!* 🌌"
                            ),
                            parse_mode="Markdown",
                        )
                    except Exception as e:
                        logger.debug(f"Tungi rejimni yoqishda xatolik ({chat_id}): {e}")

                elif not is_night and is_locked:
                    try:
                        await bot.set_chat_permissions(
                            chat_id=chat_id,
                            permissions=ChatPermissions(
                                can_send_messages=True,
                                can_send_other_messages=True,
                                can_add_web_page_previews=True,
                                can_send_polls=True,
                            ),
                        )
                        await db.set_night_mode_lock_state(chat_id, 0)
                        await bot.send_message(
                            chat_id=chat_id,
                            text=(
                                f"☀️ **XAYRLI TONG, DO'STLAR!** ☕️✨\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                f"Tungi sukunat rejimi yakunlandi.\n"
                                f"🔓 Guruhda samimiy muloqot qayta ochildi!\n\n"
                                f"🌟 *Barchangizga mazmunli va omadli kun tilaymiz!* 😊"
                            ),
                            parse_mode="Markdown",
                        )
                    except Exception as e:
                        logger.debug(f"Tungi rejimni ochishda xatolik ({chat_id}): {e}")

                await asyncio.sleep(0.05)
    except Exception as err:
        logger.error(f"Night mode scheduler xatosi: {err}")


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

    # Har 1 daqiqada Tungi rejimni tekshirish
    scheduler.add_job(
        check_night_mode,
        trigger="interval",
        minutes=1,
        args=[bot],
        id="night_mode_checker",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("⏰ Rejalashtirilgan xabarlar va Tungi rejim xizmati ishga tushdi.")
    return scheduler
