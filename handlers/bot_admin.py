from __future__ import annotations

import asyncio
import sys
import platform
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import ADMIN_IDS
from database.db import db

router = Router(name="bot_admin")


def is_bot_owner(user_id: int | None) -> bool:
    """Foydalanuvchi botning asosiy admini (egasi) ekanligini tekshiradi."""
    return user_id is not None and user_id in ADMIN_IDS


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton(text="📢 Barcha guruhlarga xabar yuborish", callback_data="admin_broadcast_help"),
        ],
        [
            InlineKeyboardButton(text="📋 Guruhlar ro'yxati", callback_data="admin_list_groups"),
            InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_refresh_panel"),
        ],
        [
            InlineKeyboardButton(text="ℹ️ Tizim va Server ma'lumotlari", callback_data="admin_sys_info"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def build_admin_panel_text(bot: Bot) -> str:
    stats = await db.get_global_stats()
    me = await bot.get_me()

    text = (
        f"👑 **GURUHCHI BOT — SUPER ADMIN BOSHQARUV PANELI**\n\n"
        f"🤖 **Bot:** @{me.username} ({me.first_name})\n"
        f"🟢 **Holat:** Faol va himoyada\n\n"
        f"📊 **UMUMIY TIZIM STATISTIKASI:**\n"
        f"• 👥 Ulangan guruhlar soni: **{stats['total_groups']}** ta\n"
        f"• 👤 Jami qayd etilgan a'zolar: **{stats['total_users']}** ta\n"
        f"• 💬 Jami yozilgan xabarlar: **{stats['total_messages']}** ta\n"
        f"• ➕ Taklif qilingan a'zolar: **{stats['total_invites']}** ta\n\n"
        f"📈 **BUGUNGI KUNLIK FAOLIYAT:**\n"
        f"• 💬 Bugungi xabarlar: **{stats['today_messages']}** ta\n"
        f"• ⚠️ Ogohlantirishlar: **{stats['today_warns']}** ta\n"
        f"• 🔇 Cheklovlar (Mute): **{stats['today_mutes']}** ta\n"
        f"• 🚫 Chetlatishlar (Ban): **{stats['today_bans']}** ta\n\n"
        f"⚡️ Boshqaruv tugmalaridan foydalanishingiz mumkin:"
    )
    return text


# ── /panel yoki /admin (Super Admin Paneli) ──────────────────────────
@router.message(Command("panel", "adminpanel", "owner", ignore_case=True))
async def cmd_admin_panel(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_bot_owner(user_id):
        await message.reply("❌ Ushbu panel faqat botning asosiy egasi (Super Admin) uchun!")
        return

    text = await build_admin_panel_text(bot)
    await message.reply(text, reply_markup=get_admin_panel_keyboard(), parse_mode="Markdown")


# ── Panelni yangilash ───────────────────────────────────────────────
@router.callback_query(F.data == "admin_refresh_panel")
async def cb_admin_refresh_panel(call: CallbackQuery, bot: Bot) -> None:
    if not is_bot_owner(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    text = await build_admin_panel_text(bot)
    try:
        await call.message.edit_text(text, reply_markup=get_admin_panel_keyboard(), parse_mode="Markdown")
    except Exception:
        pass
    await call.answer("Statistika yangilandi! 🔄")


# ── Guruhlar ro'yxatini ko'rish ─────────────────────────────────────
@router.callback_query(F.data == "admin_list_groups")
async def cb_admin_list_groups(call: CallbackQuery, bot: Bot) -> None:
    if not is_bot_owner(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    groups = await db.get_all_active_groups()
    if not groups:
        await call.answer("Hozircha bot ulangan guruhlar mavjud emas.", show_alert=True)
        return

    text = f"📋 **Bot ulangan guruhlar ro'yxati (Jami: {len(groups)} ta):**\n\n"
    for idx, g in enumerate(groups[:30], 1):
        title = g.get("title") or "Nomsiz guruh"
        cid = g.get("chat_id")
        text += f"{idx}. **{title}** (`{cid}`)\n"

    if len(groups) > 30:
        text += f"\n... va yana {len(groups) - 30} ta guruh."

    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Bosh menyuga qaytish", callback_data="admin_refresh_panel")]]
    )
    await call.message.edit_text(text, reply_markup=back_kb, parse_mode="Markdown")
    await call.answer()


# ── Broadcast bo'yicha ko'rsatma ────────────────────────────────────
@router.callback_query(F.data == "admin_broadcast_help")
async def cb_admin_broadcast_help(call: CallbackQuery) -> None:
    if not is_bot_owner(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    text = (
        "📢 **BARCHA GURUHLARGA XABAR YUBORISH (BROADCAST):**\n\n"
        "Xabar tarqatishning 2 xil oson usuli bor:\n\n"
        "1️⃣ **Matnli xabar tarqatish:**\n"
        "`/send [xabaringiz matni]`\n"
        "Masalan: `/send Assalomu alaykum, botimiz yangilandi!`\n\n"
        "2️⃣ **Rasm, Video yoki Faylli xabar tarqatish:**\n"
        "Istalgan rasm, video yoki postga **Reply** qilib `/send` deb yozing!\n\n"
        "Bot xabarni bir zumda barcha ulangan guruhlarga yetkazadi va hisobot beradi."
    )
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Bosh menyuga qaytish", callback_data="admin_refresh_panel")]]
    )
    await call.message.edit_text(text, reply_markup=back_kb, parse_mode="Markdown")
    await call.answer()


# ── Tizim va Server ma'lumotlari ────────────────────────────────────
@router.callback_query(F.data == "admin_sys_info")
async def cb_admin_sys_info(call: CallbackQuery) -> None:
    if not is_bot_owner(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    py_ver = sys.version.split()[0]
    os_name = f"{platform.system()} {platform.release()}"

    text = (
        "ℹ️ **TIZIM VA SERVER MA'LUMOTLARI:**\n\n"
        f"• 🐍 **Python:** {py_ver}\n"
        f"• 💻 **Operatsion tizim:** {os_name}\n"
        f"• ⚡️ **Platforma:** Telegram Bot API 8+\n"
        f"• 🛡️ **Xavfsizlik moduli:** APK Anti-Virus, Anti-Link, Anti-Spam, Anti-Forward\n"
        f"• 🗄 **Ma'lumotlar bazasi:** SQLite (aiosqlite)\n"
    )
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Bosh menyuga qaytish", callback_data="admin_refresh_panel")]]
    )
    await call.message.edit_text(text, reply_markup=back_kb, parse_mode="Markdown")
    await call.answer()


# ── /send yoki /broadcast (Barcha guruhlarga xabar yuborish) ─────────
@router.message(Command("send", "broadcast_all", ignore_case=True))
async def cmd_send_broadcast(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_bot_owner(user_id):
        return

    groups = await db.get_all_active_groups()
    if not groups:
        await message.reply("⚠️ Xabar yuborish uchun guruhlar mavjud emas.")
        return

    # Reply orqali xabar uzatish
    reply_msg = message.reply_to_message
    text_content = ""
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1:
        text_content = parts[1].strip()

    if not reply_msg and not text_content:
        await message.reply(
            "⚠️ **Xabar matnini kiriting!**\n\n"
            "Format: `/send [xabar matni]`\n"
            "Yoki rasm/faylga **Reply** qilib `/send` deb yozing.",
            parse_mode="Markdown",
        )
        return

    status_msg = await message.reply("🚀 Xabar guruhlarga yuborilmoqda, kuting...")

    success = 0
    fail = 0

    for g in groups:
        chat_id = g.get("chat_id")
        try:
            if reply_msg:
                await reply_msg.send_copy(chat_id=chat_id)
            else:
                await bot.send_message(chat_id=chat_id, text=text_content, parse_mode="Markdown")
            success += 1
            await asyncio.sleep(0.05)  # Telegram limits
        except Exception:
            fail += 1

    await status_msg.edit_text(
        f"✅ **Xabar tarqatish yakunlandi!**\n\n"
        f"📢 Yuborildi: **{success}** ta guruhga\n"
        f"❌ Xatolik (bot chiqarilgan yoki bloklangan): **{fail}** ta\n"
        f"📊 Jami guruhlar: **{len(groups)}** ta",
        parse_mode="Markdown",
    )
