from __future__ import annotations

import asyncio
import os
import sys
import platform
from datetime import datetime, timezone
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)

from config import ADMIN_IDS, DB_PATH
from database.db import db

router = Router(name="bot_admin")

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
    maint_btn_text = "🟢 Oddiy rejim (Profilaktika: O'chirilgan)" if not maintenance else "🟡 Profilaktika: YOQILGAN"
    kb = [
        [
            InlineKeyboardButton(text="📢 Rassilka markazi", callback_data="admin_broadcast_menu"),
            InlineKeyboardButton(text="💾 Baza zaxirasi (.db)", callback_data="admin_backup_db"),
        ],
        [
            InlineKeyboardButton(text="📋 Guruhlar boshqaruvi", callback_data="admin_list_groups"),
            InlineKeyboardButton(text="🚫 Qora ro'yxat", callback_data="admin_blacklist_menu"),
        ],
        [
            InlineKeyboardButton(text=maint_btn_text, callback_data="admin_toggle_maintenance"),
        ],
        [
            InlineKeyboardButton(text="💻 Server & Uptime", callback_data="admin_sys_info"),
            InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_refresh_panel"),
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

    bl_count = len(await db.get_blacklist())

    text = (
        f"👑 **GURUHCHI BOT — SUPER ADMIN BOSHQARUV PANELI**\n\n"
        f"🤖 **Bot:** @{me.username} ({me.first_name})\n"
        f"⚡️ **Holat:** {maint_status}\n"
        f"⏱ **Ishlash vaqti (Uptime):** {uptime}\n"
        f"💾 **Baza hajmi:** {db_size}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 **GLOBAL STATISTIKA:**\n"
        f"• 👥 Ulangan guruhlar: **{stats['total_groups']}** ta\n"
        f"• 👤 Qayd etilgan a'zolar: **{stats['total_users']}** ta\n"
        f"• 💬 Jami yozilgan xabarlar: **{stats['total_messages']}** ta\n"
        f"• ➕ Guruhga qo'shilgan takliflar: **{stats['total_invites']}** ta\n"
        f"• 🚫 Global qora ro'yxat: **{bl_count}** nafar\n\n"
        f"📈 **BUGUNGI STATISTIKA:**\n"
        f"• 💬 Bugungi xabarlar: **{stats['today_messages']}** ta\n"
        f"• ⚠️ Ogohlantirishlar (Warn): **{stats['today_warns']}** ta\n"
        f"• 🔇 Cheklovlar (Mute): **{stats['today_mutes']}** ta\n"
        f"• 🚫 Guruhdan haydash (Ban): **{stats['today_bans']}** ta\n\n"
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

    size_str = format_bytes(os.path.getsize(DB_PATH))
    stats = await db.get_global_stats()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    caption = (
        f"💾 **MA'LUMOTLAR BAZASI ZAXIRA NUSXASI (BACKUP)**\n\n"
        f"📅 **Sana:** `{now_str}`\n"
        f"📦 **Fayl hajmi:** `{size_str}`\n"
        f"👥 **Guruhlar:** {stats['total_groups']} ta\n"
        f"👤 **A'zolar:** {stats['total_users']} ta\n"
        f"💬 **Xabarlar:** {stats['total_messages']} ta\n\n"
        f"🔒 Ushbu faylni xavfsiz joyda saqlang."
    )

    doc = FSInputFile(DB_PATH, filename=f"group_bot_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db")
    await bot.send_document(chat_id=chat_id, document=doc, caption=caption, parse_mode="Markdown")


# ── 📋 Guruhlar boshqaruvi ──────────────────────────────────────────
@router.callback_query(F.data == "admin_list_groups")
async def cb_admin_list_groups(call: CallbackQuery, bot: Bot) -> None:
    if not is_bot_owner(call.from_user.id):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    groups = await db.get_all_active_groups_detailed()
    if not groups:
        await call.answer("Hozircha bot ulangan guruhlar mavjud emas.", show_alert=True)
        return

    text = f"📋 **BOT ULANGAN GURUHLAR RO'YXATI (Jami: {len(groups)} ta):**\n\n"
    for idx, g in enumerate(groups[:25], 1):
        title = g.get("title") or "Nomsiz guruh"
        cid = g.get("chat_id")
        m_cnt = g.get("member_count", 0)
        t_msg = g.get("total_messages", 0)
        text += f"**{idx}. {title}**\n   🆔 ID: `{cid}` | 👥 A'zolar: **{m_cnt}** | 💬 Xabarlar: **{t_msg}**\n"

    if len(groups) > 25:
        text += f"\n... va yana {len(groups) - 25} ta guruh.\n"

    text += (
        "\n📌 **Guruh boshqaruv buyruqlari:**\n"
        "• `/guruh [chat_id]` — Guruh haqida batafsil ma'lumot\n"
        "• `/chiq [chat_id]` — Botni ko'rsatilgan guruhdan chiqarish"
    )

    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Bosh menyuga qaytish", callback_data="admin_refresh_panel")]]
    )
    await call.message.edit_text(text, reply_markup=back_kb, parse_mode="Markdown")
    await call.answer()


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
        bot_member = await bot.get_chat_member(cid, bot.id)
        is_bot_adm = bot_member.status in ("administrator", "creator")

        group_db = await db.get_or_create_group(cid)
        min_inv = group_db.get("min_invites", 0)

        invite_link = chat.invite_link or "Yo'q"

        text = (
            f"ℹ️ **GURUH MA'LUMOTLARI:**\n\n"
            f"📌 **Nomi:** {chat.title}\n"
            f"🆔 **ID:** `{chat.id}`\n"
            f"👥 **A'zolar soni:** {members_count} ta\n"
            f"🤖 **Bot huquqi:** {'✅ Administrator' if is_bot_adm else '❌ Oddiy a'zo'}\n"
            f"👥 **Majburiy taklif:** {min_inv} ta\n"
            f"🔗 **Havola:** {invite_link}\n\n"
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
        "📢 **SUPER ADMIN RASSILKA MARKAZI:**\n\n"
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
        "💻 **SERVER VA TIZIM PARAMETRLARI:**\n\n"
        f"• 🐍 **Python versiyasi:** `{py_ver}`\n"
        f"• 🖥 **Operatsion tizim:** `{os_name}`\n"
        f"• ⏱ **Uptime (Ishlash vaqti):** `{uptime}`\n"
        f"• 💾 **SQLite baza hajmi:** `{db_size}`\n"
        f"• ⚡️ **Telegram Bot API:** 8.0+ (aiogram 3.x)\n"
        f"• 🛡️ **Himoya modullari:** Anti-APK, Anti-Link, Anti-Spam, Anti-Forward, Profanity Filter\n"
        f"• 🌐 **Web Server:** Render health server (Active)"
    )
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Bosh menyuga qaytish", callback_data="admin_refresh_panel")]]
    )
    await call.message.edit_text(text, reply_markup=back_kb, parse_mode="Markdown")
    await call.answer()
