from __future__ import annotations

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

from database.db import db
from filters.admin_filter import is_admin
from services.ui_utils import escape_md, safe_reply

router = Router(name="faq")




# ── /savollar [Guruhdagi avto-javoblar ro'yxati] ───────────────────
@router.message(Command("savollar", "faqs", "faq", "filtrlar", "filters", ignore_case=True))
async def cmd_faqs_list(message: Message) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Ushbu buyruq faqat guruhlarda ishlaydi.")
        return

    faqs = await db.get_all_faqs(message.chat.id)
    if not faqs:
        await safe_reply(
            message,
            "❓ **Guruhda avto-javoblar (filtrlar) hali mavjud emas.**\n\n"
            "Adminlar yangi avto-javob qo'shishi mumkin:\n"
            "`/filtrqosh [kalit_so'z] = [javob matni]` yoki `/savolqoshish [kalit] = [javob]`\n\n"
            "Masalan:\n"
            "`/filtrqosh manzil = Bizning manzil: Toshkent shahar, Chilonzor tumani`",
        )
        return

    safe_title = escape_md(message.chat.title)
    text = f"❓ **'{safe_title}' guruhining avto-javoblari (Filtrlar):**\n\n"
    for idx, f in enumerate(faqs, 1):
        kw = escape_md(f['keyword'])
        ans = escape_md(f['answer'])
        text += f"**{idx}.** `{kw}` ➔ _{ans}_\n"

    text += (
        "\n💡 *A'zolar ushbu kalit so'zlarni yozganda, bot avtomatik javob beradi.*\n"
        "➕ **Qo'shish:** `/filtrqosh so'z = javob`\n"
        "➖ **O'chirish:** `/filtrochir so'z`"
    )
    await safe_reply(message, text)


# ── /savolqoshish [kalit = javob] ─────────────────────────────────
@router.message(Command("savolqoshish", "addfaq", "filtrqosh", "filter", ignore_case=True))
async def cmd_add_faq(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        return

    user_id = message.from_user.id if message.from_user else None
    if not await is_admin(bot, message.chat.id, user_id, message=message):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    raw_text = (message.text or "").split(maxsplit=1)
    if len(raw_text) < 2 or "=" not in raw_text[1]:
        await safe_reply(
            message,
            "📝 **Yangi avto-javob qo'shish formati:**\n\n"
            "`/filtrqosh [kalit so'z] = [javob matni]`\n\n"
            "Masalan:\n"
            "`/filtrqosh narxlar = Xizmat narxlari bilan @kanalimiz orqali tanishishingiz mumkin.`\n"
            "`/filtrqosh qayerda = Biz Chilonzorda joylashganmiz.`",
        )
        return

    payload = raw_text[1]
    kw, ans = payload.split("=", maxsplit=1)
    keyword = kw.strip().lower()
    answer = ans.strip()

    if not keyword or not answer:
        await message.reply("❌ Kalit so'z yoki javob matni bo'sh bo'lishi mumkin emas!")
        return

    creator_id = user_id or 0
    await db.add_faq(message.chat.id, keyword, answer, creator_id)
    safe_kw = escape_md(keyword)
    safe_ans = escape_md(answer)
    await safe_reply(
        message,
        f"✅ **Avto-javob saqlandi!**\n\n"
        f"🔑 **Kalit so'z:** `{safe_kw}`\n"
        f"💬 **Javob:** {safe_ans}\n\n"
        f"Endi biror a'zo guruhda `{safe_kw}` so'zini ishlatsa, bot avtomatik javob beradi.",
    )


# ── /savolochir [kalit] ───────────────────────────────────────────
@router.message(Command("savolochir", "delfaq", "filtrochir", "delfilter", ignore_case=True))
async def cmd_remove_faq(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        return

    user_id = message.from_user.id if message.from_user else None
    if not await is_admin(bot, message.chat.id, user_id, message=message):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await safe_reply(message, "Format: `/savolochir [kalit so'z]`\nMasalan: `/savolochir narxlar`")
        return

    keyword = parts[1].strip().lower()
    removed = await db.remove_faq(message.chat.id, keyword)
    safe_kw = escape_md(keyword)
    if removed:
        await safe_reply(message, f"✅ `{safe_kw}` kalit so'zidagi avto-javob o'chirildi!")
    else:
        await safe_reply(message, f"❌ `{safe_kw}` bo'yicha avto-javob topilmadi.")
