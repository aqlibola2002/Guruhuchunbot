from __future__ import annotations

import asyncio
import os
import sys
import platform
import math
from datetime import datetime, timezone
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
    BufferedInputFile,
)

from config import ADMIN_IDS, DB_PATH
from database.db import db

router = Router(name="bot_admin")
# Ushbu router faqat Bot Egasi (Super Admin) ga tegishli
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))

BOT_START_TIME = datetime.now()


def is_bot_owner(user_id: int | None) -> bool:
    """Foydalanuvchi botning asosiy egasi (Super Admin) ekanligini tekshiradi."""
    return user_id is not None and user_id in ADMIN_IDS


def format_bytes(size: int) -> str:
    """Fayl hajmini odam tushunadigan formatga aylantirish (KB, MB)."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def get_uptime() -> str:
    """Bot qancha vaqtdan beri to'xtovsiz ishlayotganini hisoblaydi."""
    delta = datetime.now() - BOT_START_TIME
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days > 0:
        parts.append(f"{days} kun")
    if hours > 0:
        parts.append(f"{hours} soat")
    if minutes > 0:
        parts.append(f"{minutes} daqiqa")
    parts.append(f"{seconds} soniya")
    return " ".join(parts)


def get_admin_panel_keyboard(maintenance: bool = False) -> InlineKeyboardMarkup:
    maint_btn_text = "🟢 Oddiy rejim (Profilaktika: Yo'q)" if not maintenance else "🟡 Profilaktika: YOQILGAN"
    kb = [
        [
            InlineKeyboardButton(text="📢 Rassilka markazi", callback_data="admin_broadcast_menu"),
            InlineKeyboardButton(text="📋 Guruhlar & Havolalar", callback_data="admin_list_groups:1"),
        ],
        [
            InlineKeyboardButton(text="💾 Baza zaxirasi (.db)", callback_data="admin_backup_db"),
            InlineKeyboardButton(text="📥 Bazani tiklash", callback_data="admin_restore_db"),
        ],
        [
            InlineKeyboardButton(text="🚫 Global qora ro'yxat", callback_data="admin_blacklist_menu"),
            InlineKeyboardButton(text="⚙️ Bot sozlamalari", callback_data="admin_settings_menu"),
        ],
        [
            InlineKeyboardButton(text=maint_btn_text, callback_data="admin_toggle_maintenance"),
            InlineKeyboardButton(text="💻 Server & Uptime", callback_data="admin_sys_info"),
        ],
        [
            InlineKeyboardButton(text="🔄 Panelni yangilash", callback_data="admin_refresh_panel"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def build_admin_panel_text(bot: Bot) -> str:
    stats = await db.get_global_stats()
    me = await bot.get_me()
    uptime = get_uptime()

    db_size = "Noma'lum"
    if os.path.exists(DB_PATH):
        db_size = format_bytes(os.path.getsize(DB_PATH))

    maintenance_val = await db.get_bot_setting("maintenance", "off")
    maint_status = "🟡 Profilaktika yoqilgan" if maintenance_val == "on" else "🟢 Faol va himoyada"

    startup_notify = await db.get_bot_setting("startup_notify_groups", "1")
    startup_status = "Yoqilgan 🔔" if startup_notify == "1" else "O'chirilgan 🔕"

    bl_count = len(await db.get_blacklist())

    text = (
        f"👑 **SUPER ADMIN BOSHQARUV PANELI** 💎\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 **Bot:** @{me.username} ({me.first_name})\n"
        f"⚡️ **Tizim holati:** {maint_status}\n"
        f"⏱ **Uptime:** {uptime}\n"
        f"💾 **Baza hajmi (WAL):** {db_size} (Avto-tiklash faol ✅)\n"
        f"📢 **Guruhlarga start xabari:** {startup_status}\n\n"
        f"📊 **GLOBAL STATISTIKA:**\n"
        f"├ 🏛 Ulangan guruhlar: **{stats['total_groups']:,}** ta\n"
        f"├ 👤 Qayd etilgan a'zolar: **{stats['total_users']:,}** nafar\n"
        f"├ 💬 Jami yozilgan xabarlar: **{stats['total_messages']:,}** ta\n"
        f"├ 👥 Guruhga taklif qilinganlar: **{stats['total_invites']:,}** ta\n"
        f"└ 🚫 Global qora ro'yxat: **{bl_count:,}** nafar\n\n"
        f"📈 **BUGUNGI INTIZOM VA FAOLLIK:**\n"
        f"├ 💬 Bugungi xabarlar: **{stats['today_messages']:,}** ta\n"
        f"├ ⚠️ Ogohlantirishlar (Warn): **{stats['today_warns']:,}** ta\n"
        f"├ 🔇 Cheklovlar (Mute): **{stats['today_mutes']:,}** ta\n"
        f"└ 🚫 Guruhdan haydash (Ban): **{stats['today_bans']:,}** ta\n\n"
        f"⚡️ Kerakli bo'limni tanlang:"
    )
    return text


# ── /panel yoki /owner (Super Admin Dashboard) ───────────────────────
@router.message(Command("panel", "adminpanel", "owner", "superadmin", ignore_case=True))
async def cmd_admin_panel(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_bot_owner(user_id):
        await message.reply("❌ Ushbu panel faqat bot egasi (Super Admin) uchun!")
        return

    maint = (await db.get_bot_setting("maintenance", "off")) == "on"
    text = await build_admin_panel_text(bot)
    await message.reply(text, reply_markup=get_admin_panel_keyboard(maint), parse_mode="Markdown")


# ── Panelni yangilash ───────────────────────────────────────────────
@router.callback_query(F.data == "admin_refresh_panel")
async def cb_admin_refresh_panel(call: CallbackQuery, bot: Bot) -> None:
    if not is_bot_owner(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    maint = (await db.get_bot_setting("maintenance", "off")) == "on"
    text = await build_admin_panel_text(bot)
    try:
        await call.message.edit_text(text, reply_markup=get_admin_panel_keyboard(maint), parse_mode="Markdown")
    except Exception:
        pass
    await call.answer("Panel muvaffaqiyatli yangilandi! 🔄")


# ── 💾 Baza zaxirasini yuklab olish (/backup yoki tugma) ─────────────
@router.callback_query(F.data == "admin_backup_db")
async def cb_admin_backup_db(call: CallbackQuery, bot: Bot) -> None:
    if not is_bot_owner(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    await send_database_backup(call.message.chat.id, bot)
    await call.answer("Baza zaxirasi yuborildi! 💾")


@router.message(Command("backup", "db", "bazazaxirasi", ignore_case=True))
async def cmd_database_backup(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_bot_owner(user_id):
        return
    await send_database_backup(message.chat.id, bot)


async def send_database_backup(chat_id: int, bot: Bot) -> None:
    if not os.path.exists(DB_PATH):
        await bot.send_message(chat_id, "❌ Baza fayli topilmadi!")
        return

    # WAL faylini asosiy DB ga sinxronlash
    try:
        await db.auto_backup()
    except Exception:
        pass

    size_str = format_bytes(os.path.getsize(DB_PATH))
    stats = await db.get_global_stats()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    caption = (
        f"💾 **MA'LUMOTLAR BAZASI ZAXIRA NUSXASI (BACKUP)** 🛡\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 **Sana:** `{now_str}`\n"
        f"📦 **Fayl hajmi:** `{size_str}`\n"
        f"🏛 **Guruhlar:** {stats['total_groups']} ta\n"
        f"👤 **A'zolar:** {stats['total_users']:,} nafar\n"
        f"💬 **Xabarlar:** {stats['total_messages']:,} ta\n"
        f"👥 **Takliflar:** {stats['total_invites']:,} ta\n\n"
        f"🔒 Ushbu faylni saqlang. Bot o'chib yonsa ham barcha ma'lumotlar avtomatik saqlanadi. "
        f"Zarur bo'lsa, ushbu `.db` faylni botga yuborib qayta tiklashingiz (Restore) mumkin."
    )

    doc = FSInputFile(DB_PATH, filename=f"group_bot_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db")
    await bot.send_document(chat_id=chat_id, document=doc, caption=caption, parse_mode="Markdown")


# ── 📥 Baza ma'lumotlarini tiklash (Restore) ─────────────────────────
@router.callback_query(F.data == "admin_restore_db")
async def cb_admin_restore_db(call: CallbackQuery) -> None:
    if not is_bot_owner(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    text = (
        "📥 **MA'LUMOTLAR BAZASINI TIKLASH (RESTORE):**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Barcha ma'lumotlarni (guruhlar, sozlamalar, takliflar, ogohlantirishlar) to'liq tiklash uchun:\n\n"
        "👉 **Avvalgi `.db` zaxira faylini ushbu chatga Fayl (Document) ko'rinishida yuboring!**\n\n"
        "⚡️ Bot faylni tekshirib, xavfsiz tarzda barcha ma'lumotlarni qayta tiklaydi."
    )
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Bosh menyuga qaytish", callback_data="admin_refresh_panel")]]
    )
    await call.message.edit_text(text, reply_markup=back_kb, parse_mode="Markdown")
    await call.answer()


@router.message(F.document)
async def handle_db_restore_upload(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_bot_owner(user_id):
        return

    doc = message.document
    if not doc or not doc.file_name or not doc.file_name.endswith(".db"):
        return

    status_msg = await message.reply("⏳ Zaxira fayli qabul qilindi, tekshirilmoqda va tiklanmoqda...")

    temp_dir = os.path.join(os.path.dirname(DB_PATH), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"restore_{datetime.now().strftime('%Y%m%d%H%M%S')}.db")

    try:
        await bot.download(doc, destination=temp_path)
        success, msg = await db.restore_database(temp_path)

        if success:
            stats = await db.get_global_stats()
            res_text = (
                f"🎉 **MA'LUMOTLAR BAZASI MUVAFFAQIYATLI TIKLANDI!** ✅\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🏛 **Ulangan guruhlar:** {stats['total_groups']} ta\n"
                f"👤 **Qayd etilgan a'zolar:** {stats['total_users']:,} ta\n"
                f"💬 **Xabarlar soni:** {stats['total_messages']:,} ta\n"
                f"👥 **Takliflar:** {stats['total_invites']:,} ta\n\n"
                f"🔒 Barcha guruhlar, sozlamalar va kiber-himoya qoidalari to'liq faol holatga keltirildi!"
            )
            await status_msg.edit_text(res_text, parse_mode="Markdown")
        else:
            await status_msg.edit_text(f"❌ Xatolik yuz berdi:\n{msg}")
    except Exception as err:
        await status_msg.edit_text(f"❌ Faylni yuklab olishda xatolik: {err}")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


# ── Guruh havolasini aniqlash va bazaga saqlash yordamchisi ────────
async def resolve_group_link(bot: Bot, group: dict) -> str:
    """Guruh havolasini olish (mavjud bo'lmasa, Telegram orqali olib bazada saqlash)."""
    cid = group.get("chat_id")
    link = group.get("invite_link") or ""
    username = group.get("username") or ""

    if link:
        return link

    if username:
        link = f"https://t.me/{username.lstrip('@')}"
        await db.update_group_link(cid, link, username)
        return link

    try:
        chat = await bot.get_chat(cid)
        if chat.username:
            link = f"https://t.me/{chat.username}"
            await db.update_group_link(cid, link, chat.username)
            return link
        elif chat.invite_link:
            link = chat.invite_link
            await db.update_group_link(cid, link)
            return link
        else:
            try:
                link = await bot.export_chat_invite_link(cid)
                await db.update_group_link(cid, link)
                return link
            except Exception:
                pass
    except Exception:
        pass

    return link


# ── 📋 Guruhlar va ularning havolalari boshqaruvi ──────────────────
GROUPS_PER_PAGE = 5


@router.callback_query(F.data.startswith("admin_list_groups"))
async def cb_admin_list_groups(call: CallbackQuery, bot: Bot) -> None:
    if not is_bot_owner(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    parts = call.data.split(":")
    page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

    await render_groups_page(call.message, bot, page, is_callback=True)
    await call.answer()


@router.message(Command("guruhlar", "groups", "guruh_havolalari", ignore_case=True))
async def cmd_admin_list_groups(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_bot_owner(user_id):
        return
    await render_groups_page(message, bot, page=1, is_callback=False)


async def render_groups_page(message: Message, bot: Bot, page: int = 1, is_callback: bool = True) -> None:
    groups = await db.get_all_active_groups_detailed()
    if not groups:
        text = "ℹ️ Hozircha bot ulangan guruhlar mavjud emas."
        back_kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="◀️ Bosh menyuga qaytish", callback_data="admin_refresh_panel")]]
        )
        if is_callback:
            await message.edit_text(text, reply_markup=back_kb)
        else:
            await message.reply(text, reply_markup=back_kb)
        return

    total_groups = len(groups)
    total_pages = max(1, math.ceil(total_groups / GROUPS_PER_PAGE))
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * GROUPS_PER_PAGE
    end_idx = start_idx + GROUPS_PER_PAGE
    page_groups = groups[start_idx:end_idx]

    text = (
        f"📋 **BOT ULANGAN BARCHA GURUHLAR VA HAVOLALARI** 🏛\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 **Jami guruhlar:** **{total_groups} ta** | 📄 **Sahifa:** `{page}/{total_pages}`\n\n"
    )

    url_buttons: list[list[InlineKeyboardButton]] = []

    for i, g in enumerate(page_groups, start=start_idx + 1):
        title = g.get("title") or "Nomsiz guruh"
        cid = g.get("chat_id")
        m_cnt = g.get("member_count", 0)
        t_msg = g.get("total_messages", 0)

        # Havolani aniqlash
        link = await resolve_group_link(bot, g)

        link_display = f"[Guruhga o'tish]({link})" if link else "_Havola olinmadi (bot admin qilinmagan)_"
        raw_link_info = f"\n   🔗 **Link:** `{link}`" if link else ""

        text += (
            f"**{i}. {title}**\n"
            f"   🆔 ID: `{cid}`\n"
            f"   👥 A'zolar: **{m_cnt:,}** ta | 💬 Xabarlar: **{t_msg:,}** ta\n"
            f"   🌐 Havola: {link_display}{raw_link_info}\n\n"
        )

        if link:
            short_name = (title[:18] + "..") if len(title) > 20 else title
            url_buttons.append([InlineKeyboardButton(text=f"🌐 {i}. {short_name}", url=link)])

    # Sahifalash tugmalari
    nav_buttons: list[InlineKeyboardButton] = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"admin_list_groups:{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data=f"admin_list_groups:{page}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"admin_list_groups:{page + 1}"))

    all_kb: list[list[InlineKeyboardButton]] = []
    all_kb.extend(url_buttons)
    if nav_buttons:
        all_kb.append(nav_buttons)

    all_kb.append([
        InlineKeyboardButton(text="📋 Barcha havolalarni olish (.txt)", callback_data="admin_export_links_txt"),
    ])
    all_kb.append([
        InlineKeyboardButton(text="◀️ Bosh menyuga qaytish", callback_data="admin_refresh_panel"),
    ])

    markup = InlineKeyboardMarkup(inline_keyboard=all_kb)
    if is_callback:
        try:
            await message.edit_text(text, reply_markup=markup, parse_mode="Markdown", disable_web_page_preview=True)
        except Exception:
            pass
    else:
        await message.reply(text, reply_markup=markup, parse_mode="Markdown", disable_web_page_preview=True)


# ── 📋 Barcha guruh havolalarini bitta fayl (.txt) qilib yuklash ─────
@router.callback_query(F.data == "admin_export_links_txt")
async def cb_admin_export_links_txt(call: CallbackQuery, bot: Bot) -> None:
    if not is_bot_owner(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    await send_all_links_txt(call.message.chat.id, bot)
    await call.answer("Barcha guruh havolalari yuborildi! 📋")


@router.message(Command("guruhlar_txt", "links_txt", ignore_case=True))
async def cmd_export_links_txt(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_bot_owner(user_id):
        return
    await send_all_links_txt(message.chat.id, bot)


async def send_all_links_txt(chat_id: int, bot: Bot) -> None:
    groups = await db.get_all_active_groups_detailed()
    if not groups:
        await bot.send_message(chat_id, "ℹ️ Hozircha bot ulangan guruhlar mavjud emas.")
        return

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "===========================================================",
        "GURUHCHI UZ — BARCHA ULANGAN GURUHLAR VA ULARNING HAVOLALARI",
        f"Yuklangan sana: {now_str}",
        f"Jami guruhlar soni: {len(groups)} ta",
        "===========================================================\n",
    ]

    for idx, g in enumerate(groups, 1):
        title = g.get("title") or "Nomsiz guruh"
        cid = g.get("chat_id")
        m_cnt = g.get("member_count", 0)
        t_msg = g.get("total_messages", 0)
        link = await resolve_group_link(bot, g)

        lines.append(f"{idx}. Guruh nomi: {title}")
        lines.append(f"   ID raqami: {cid}")
        lines.append(f"   A'zolar soni: {m_cnt:,} ta")
        lines.append(f"   Xabarlar soni: {t_msg:,} ta")
        lines.append(f"   Havola (Link): {link or 'Olinmadi (bot admin emas)'}")
        lines.append("-" * 55)

    content = "\n".join(lines).encode("utf-8")
    doc = BufferedInputFile(content, filename=f"barcha_guruhlar_havolalari_{datetime.now().strftime('%Y%m%d_%H%M')}.txt")
    await bot.send_document(
        chat_id=chat_id,
        document=doc,
        caption=(
            f"📋 **BARCHA GURUHLAR VA ULARNING HAVOLALARI RO'YXATI**\n\n"
            f"🏛 **Jami guruhlar:** {len(groups)} ta\n"
            f"📅 **Sana:** `{now_str}`\n\n"
            f"Har bir guruhning nomi, ID raqami, a'zolari va Telegram havolasi yuqoridagi faylda to'liq saqlangan."
        ),
        parse_mode="Markdown",
    )


# ── ⚙️ Bot Global Sozlamalari Menusi ────────────────────────────────
@router.callback_query(F.data == "admin_settings_menu")
async def cb_admin_settings_menu(call: CallbackQuery) -> None:
    if not is_bot_owner(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    startup_val = await db.get_bot_setting("startup_notify_groups", "1")
    startup_btn = "🟢 Guruhga start xabari: YOQILGAN" if startup_val == "1" else "🔴 Guruhga start xabari: O'CHIRILGAN"

    kb = [
        [InlineKeyboardButton(text=startup_btn, callback_data="admin_toggle_startup_notify")],
        [InlineKeyboardButton(text="💾 Baza holati: SQLite WAL (Auto-Active)", callback_data="admin_noop")],
        [InlineKeyboardButton(text="◀️ Bosh menyuga qaytish", callback_data="admin_refresh_panel")],
    ]

    text = (
        "⚙️ **BOT GLOBAL XAVFSIZLIK VA ISHLASH SOZLAMALARI:**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ **Guruhlarga start xabari:**\n"
        "Bot ishga tushganda yoki qayta yoqilganda barcha guruhlarga xavfsizlik tizimi onlayn ekanligi haqida 60 soniyali tasdiq yuborish.\n\n"
        "2️⃣ **Avtomatik tiklanish (SQLite WAL):**\n"
        "Bot server o'chib yonsa ham hech qanday ma'lumot yo'qolmasdan to'liq tiklanishini ta'minlaydi.\n\n"
        "Kerakli sozlamani o'zgartirish uchun tugmani bosing:"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await call.answer()


@router.callback_query(F.data == "admin_toggle_startup_notify")
async def cb_admin_toggle_startup_notify(call: CallbackQuery) -> None:
    if not is_bot_owner(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    curr = await db.get_bot_setting("startup_notify_groups", "1")
    new_v = "0" if curr == "1" else "1"
    await db.set_bot_setting("startup_notify_groups", new_v)

    alert_text = "Guruhlarga start xabari YOQILDI 🟢" if new_v == "1" else "Guruhlarga start xabari O'CHIRILDI 🔴"
    await call.answer(alert_text, show_alert=True)
    await cb_admin_settings_menu(call)


@router.callback_query(F.data == "admin_noop")
async def cb_admin_noop(call: CallbackQuery) -> None:
    await call.answer("Bu doimiy faol tizim hisoblanadi ✅", show_alert=False)


# ── /guruh [chat_id] (Guruh haqida batafsil) ─────────────────────────
@router.message(Command("guruh", "groupinfo", ignore_case=True))
async def cmd_group_info(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_bot_owner(user_id):
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.reply("Format: `/guruh [chat_id]`", parse_mode="Markdown")
        return

    try:
        cid = int(parts[1])
    except ValueError:
        await message.reply("❌ Noto'g'ri guruh ID raqami!")
        return

    try:
        chat = await bot.get_chat(cid)
        members_count = await bot.get_chat_member_count(cid)
        bot_id = int(bot.token.split(":")[0])
        bot_member = await bot.get_chat_member(cid, bot_id)
        is_bot_adm = bot_member.status in ("administrator", "creator")

        group_db = await db.get_or_create_group(cid)
        min_inv = group_db.get("min_invites", 0)

        invite_link = await resolve_group_link(bot, group_db)
        bot_perm_text = "✅ Administrator" if is_bot_adm else "❌ Oddiy a'zo"

        text = (
            f"ℹ️ **GURUH MA'LUMOTLARI:**\n\n"
            f"📌 **Nomi:** {chat.title}\n"
            f"🆔 **ID:** `{chat.id}`\n"
            f"👥 **A'zolar soni:** {members_count:,} ta\n"
            f"🤖 **Bot huquqi:** {bot_perm_text}\n"
            f"👥 **Majburiy taklif:** {min_inv} ta\n"
            f"🔗 **Havola:** {invite_link or 'Mavjud emas'}\n\n"
            f"Chiqarib yuborish: `/chiq {cid}`"
        )
        await message.reply(text, parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Guruh ma'lumotini olishda xatolik: {e}\n(Bot guruhdan chiqarilgan bo'lishi mumkin).")


# ── /chiq [chat_id] (Guruhdan masofadan chiqish) ─────────────────────
@router.message(Command("chiq", "leave", "tark", ignore_case=True))
async def cmd_leave_group(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_bot_owner(user_id):
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.reply("Format: `/chiq [chat_id]`", parse_mode="Markdown")
        return

    try:
        cid = int(parts[1])
    except ValueError:
        await message.reply("❌ Noto'g'ri guruh ID raqami!")
        return

    try:
        await bot.leave_chat(cid)
        await db.delete_group(cid)
        await message.reply(f"✅ Bot `{cid}` guruhidan muvaffaqiyatli chiqdi va bazadan o'chirildi!", parse_mode="Markdown")
    except Exception as e:
        await db.delete_group(cid)
        await message.reply(f"⚠️ Telegram orqali chiqishda xato bo'ldi: {e}\nLekin guruh bazadan o'chirildi.")


# ── 📢 Rassilka markazi ──────────────────────────────────────────────
@router.callback_query(F.data == "admin_broadcast_menu")
async def cb_admin_broadcast_menu(call: CallbackQuery) -> None:
    if not is_bot_owner(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    text = (
        "📢 **SUPER ADMIN RASSILKA MARKAZI:**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Xabar tarqatishning kuchaytirilgan usullari:\n\n"
        "1️⃣ **Faqat barcha guruhlarga yuborish:**\n"
        "`/send [xabar matni]`\n"
        "*(Yoki rasm, video, faylga Reply qilib `/send` deb yozing)*\n\n"
        "2️⃣ **Guruhlarga yuborish va QADASH (PIN):**\n"
        "`/send_pin [xabar matni]`\n"
        "*(Xabar barcha guruhlarga yuboriladi va tepaga qadaladi)*\n\n"
        "3️⃣ **Faqat shaxsiy bot foydalanuvchilariga (PM):**\n"
        "`/send_users [xabar matni]`\n\n"
        "4️⃣ **HAMMAGA (Ham guruhlar, ham foydalanuvchilarga):**\n"
        "`/send_all [xabar matni]`"
    )
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Bosh menyuga qaytish", callback_data="admin_refresh_panel")]]
    )
    await call.message.edit_text(text, reply_markup=back_kb, parse_mode="Markdown")
    await call.answer()


# ── /send (Guruhlarga) ───────────────────────────────────────────────
@router.message(Command("send", "broadcast", "broadcast_groups", ignore_case=True))
async def cmd_broadcast_groups(message: Message, bot: Bot) -> None:
    await handle_broadcast(message, bot, target_type="groups", pin=False)


# ── /send_pin (Guruhlarga yuborish va qadash) ────────────────────────
@router.message(Command("send_pin", "broadcast_pin", ignore_case=True))
async def cmd_broadcast_pin(message: Message, bot: Bot) -> None:
    await handle_broadcast(message, bot, target_type="groups", pin=True)


# ── /send_users (Shaxsiy foydalanuvchilarga) ─────────────────────────
@router.message(Command("send_users", "broadcast_users", ignore_case=True))
async def cmd_broadcast_users(message: Message, bot: Bot) -> None:
    await handle_broadcast(message, bot, target_type="users", pin=False)


# ── /send_all (Barchaga: Guruhlar + Foydalanuvchilar) ────────────────
@router.message(Command("send_all", "broadcast_all", ignore_case=True))
async def cmd_broadcast_all(message: Message, bot: Bot) -> None:
    await handle_broadcast(message, bot, target_type="all", pin=False)


async def handle_broadcast(message: Message, bot: Bot, target_type: str = "groups", pin: bool = False) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_bot_owner(user_id):
        return

    reply_msg = message.reply_to_message
    parts = (message.text or "").split(maxsplit=1)
    text_content = parts[1].strip() if len(parts) > 1 else ""

    if not reply_msg and not text_content:
        await message.reply(
            "⚠️ **Xabar matnini kiriting!**\n\n"
            "Format: buyruqdan keyin matn yozing yoki rasm/faylga **Reply** qilib yuboring.",
            parse_mode="Markdown",
        )
        return

    targets: list[int] = []
    if target_type in ("groups", "all"):
        groups = await db.get_all_active_groups()
        targets.extend([g["chat_id"] for g in groups])

    if target_type in ("users", "all"):
        users = await db.get_all_user_ids()
        targets.extend(users)

    targets = list(set(targets))
    if not targets:
        await message.reply("⚠️ Xabar yuborish uchun qabul qiluvchilar topilmadi.")
        return

    label = "guruhlarga" if target_type == "groups" else ("foydalanuvchilarga" if target_type == "users" else "barchaga")
    pin_label = " (avtomatik qadash bilan)" if pin else ""
    status_msg = await message.reply(f"🚀 Xabar **{len(targets)}** ta manzilga yuborilmoqda{pin_label}, kuting...")

    success = 0
    fail = 0

    for cid in targets:
        try:
            sent_msg = None
            if reply_msg:
                sent_msg = await reply_msg.send_copy(chat_id=cid)
            else:
                sent_msg = await bot.send_message(chat_id=cid, text=text_content, parse_mode="Markdown")

            if pin and sent_msg:
                try:
                    await bot.pin_chat_message(chat_id=cid, message_id=sent_msg.message_id, disable_notification=False)
                except Exception:
                    pass

            success += 1
            await asyncio.sleep(0.04)  # Anti flood-limit
        except Exception:
            fail += 1

    await status_msg.edit_text(
        f"✅ **Rassilka yakunlandi!**\n\n"
        f"📢 Yetkazildi: **{success}** ta {label}\n"
        f"❌ Yetib bormadi (bloklangan/chiqarilgan): **{fail}** ta\n"
        f"📊 Jami manzillar: **{len(targets)}** ta",
        parse_mode="Markdown",
    )


# ── 🚫 Global Qora Ro'yxat (Blacklist) ───────────────────────────────
@router.callback_query(F.data == "admin_blacklist_menu")
async def cb_admin_blacklist_menu(call: CallbackQuery) -> None:
    if not is_bot_owner(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    bl = await db.get_blacklist()
    text = f"🚫 **GLOBAL QORA RO'YXAT (Jami: {len(bl)} nafar):**\n\n"
    if not bl:
        text += "Hozirda qora ro'yxatda hech kim yo'q. Barcha a'zolar toza.\n"
    else:
        for idx, item in enumerate(bl[:20], 1):
            text += f"{idx}. 🆔 `{item['user_id']}` | 📝 Sabab: {item.get('reason') or 'Sababsiz'}\n"

    text += (
        "\n📌 **Buyruqlar:**\n"
        "• `/ban_global [user_id] [sabab]` — Qora ro'yxatga qo'shish\n"
        "• `/unban_global [user_id]` — Qora ro'yxatdan chiqarish"
    )

    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Bosh menyuga qaytish", callback_data="admin_refresh_panel")]]
    )
    await call.message.edit_text(text, reply_markup=back_kb, parse_mode="Markdown")
    await call.answer()


@router.message(Command("ban_global", "blacklist", ignore_case=True))
async def cmd_ban_global(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_bot_owner(user_id):
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply(
            "Format: `/ban_global [user_id] [sabab]`\nMasalan: `/ban_global 123456789 Firibgarlik`",
            parse_mode="Markdown",
        )
        return

    target_id = int(parts[1])
    reason = parts[2].strip() if len(parts) > 2 else "Bot egasi tomonidan cheklangan"

    if target_id in ADMIN_IDS:
        await message.reply("❌ Bot egasini qora ro'yxatga kiritib bo'lmaydi!")
        return

    await db.add_to_blacklist(target_id, reason)
    await message.reply(
        f"🚫 **Foydalanuvchi global qora ro'yxatga kiritildi!**\n🆔 ID: `{target_id}`\n📝 Sabab: {reason}\n"
        f"U endi botdan va bot ulangan barcha guruhlardan cheklanadi.",
        parse_mode="Markdown",
    )


@router.message(Command("unban_global", "unblacklist", ignore_case=True))
async def cmd_unban_global(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_bot_owner(user_id):
        return

    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("Format: `/unban_global [user_id]`", parse_mode="Markdown")
        return

    target_id = int(parts[1])
    removed = await db.remove_from_blacklist(target_id)
    if removed:
        await message.reply(f"🔓 Foydalanuvchi (`{target_id}`) global qora ro'yxatdan chiqarildi!", parse_mode="Markdown")
    else:
        await message.reply(f"ℹ️ Foydalanuvchi (`{target_id}`) qora ro'yxatda mavjud emas edi.")


# ── 🛠 Texnik profilaktika (Maintenance) ─────────────────────────────
@router.callback_query(F.data == "admin_toggle_maintenance")
async def cb_admin_toggle_maintenance(call: CallbackQuery, bot: Bot) -> None:
    if not is_bot_owner(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    current = await db.get_bot_setting("maintenance", "off")
    new_val = "off" if current == "on" else "on"
    await db.set_bot_setting("maintenance", new_val)

    status_str = "YOQILDI 🟡" if new_val == "on" else "O'CHIRILDI 🟢"
    await call.answer(f"Texnik profilaktika rejimi {status_str}", show_alert=True)

    maint = new_val == "on"
    text = await build_admin_panel_text(bot)
    try:
        await call.message.edit_text(text, reply_markup=get_admin_panel_keyboard(maint), parse_mode="Markdown")
    except Exception:
        pass


@router.message(Command("profilaktika", "maintenance", ignore_case=True))
async def cmd_toggle_maintenance(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_bot_owner(user_id):
        return

    parts = (message.text or "").split()
    if len(parts) > 1:
        arg = parts[1].lower()
        new_val = "on" if arg in ("on", "yoq", "1") else "off"
    else:
        current = await db.get_bot_setting("maintenance", "off")
        new_val = "off" if current == "on" else "on"

    await db.set_bot_setting("maintenance", new_val)
    status_str = "YOQILDI 🟡" if new_val == "on" else "O'CHIRILDI 🟢"
    await message.reply(f"⚙️ **Texnik profilaktika rejimi {status_str}**", parse_mode="Markdown")


# ── 💻 Tizim va Server ma'lumotlari ──────────────────────────────────
@router.callback_query(F.data == "admin_sys_info")
async def cb_admin_sys_info(call: CallbackQuery) -> None:
    if not is_bot_owner(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    py_ver = sys.version.split()[0]
    os_name = f"{platform.system()} {platform.release()}"
    uptime = get_uptime()

    db_size = format_bytes(os.path.getsize(DB_PATH)) if os.path.exists(DB_PATH) else "Mavjud emas"

    text = (
        "💻 **SERVER VA TIZIM PARAMETRLARI:**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"• 🐍 **Python versiyasi:** `{py_ver}`\n"
        f"• 🖥 **Operatsion tizim:** `{os_name}`\n"
        f"• ⏱ **Uptime (Ishlash vaqti):** `{uptime}`\n"
        f"• 💾 **SQLite baza hajmi:** `{db_size}` (WAL rejimida)\n"
        f"• ⚡️ **Telegram Bot API:** 8.0+ (aiogram 3.x)\n"
        f"• 🛡️ **Himoya modullari:** Anti-APK, Anti-Link, Anti-Spam, Anti-Forward, Universal Profanity Filter\n"
        f"• 🌐 **Web Server:** Render health server (Active)\n"
        f"• 🔒 **Zaxira nusxalari:** `data/backups/` papkasida avtomatik saqlanmoqda"
    )
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Bosh menyuga qaytish", callback_data="admin_refresh_panel")]]
    )
    await call.message.edit_text(text, reply_markup=back_kb, parse_mode="Markdown")
    await call.answer()
