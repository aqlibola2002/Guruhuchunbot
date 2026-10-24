from __future__ import annotations

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

from database.db import db
from filters.admin_filter import is_admin

router = Router(name="faq")




# ── /savollar [Guruhdagi avto-javoblar ro'yxati] ───────────────────
@router.message(Command("savollar", "faqs", "faq", "filtrlar", "filters", ignore_case=True))
async def cmd_faqs_list(message: Message) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Ushbu buyruq faqat guruhlarda ishlaydi.")
        return

    faqs = await db.get_all_faqs(message.chat.id)
    if not faqs:
        await message.reply(
            "❓ **Guruhda avto-javoblar (filtrlar) hali mavjud emas.**\n\n"
            "Adminlar yangi avto-javob qo'shishi mumkin:\n"
            "`/filtrqosh [kalit_so'z] = [javob matni]` yoki `/savolqoshish [kalit] = [javob]`\n\n"
            "Masalan:\n"
            "`/filtrqosh manzil = Bizning manzil: Toshkent shahar, Chilonzor tumani`",
            parse_mode="Markdown",
        )
        return

    text = f"❓ **'{message.chat.title}' guruhining avto-javoblari (Filtrlar):**\n\n"
    for idx, f in enumerate(faqs, 1):
        text += f"**{idx}.** `{f['keyword']}` ➔ _{f['answer']}_\n"

    text += (
        "\n💡 *A'zolar ushbu kalit so'zlarni yozganda, bot avtomatik javob beradi.*\n"
        "➕ **Qo'shish:** `/filtrqosh so'z = javob`\n"
        "➖ **O'chirish:** `/filtrochir so'z`"
    )
    await message.reply(text, parse_mode="Markdown")


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
        await message.reply(
            "📝 **Yangi avto-javob qo'shish formati:**\n\n"
            "`/filtrqosh [kalit so'z] = [javob matni]`\n\n"
            "Masalan:\n"
            "`/filtrqosh narxlar = Xizmat narxlari bilan @kanalimiz orqali tanishishingiz mumkin.`\n"
            "`/filtrqosh qayerda = Biz Chilonzorda joylashganmiz.`",
            parse_mode="Markdown",
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
    await message.reply(
        f"✅ **Avto-javob saqlandi!**\n\n"
        f"🔑 **Kalit so'z:** `{keyword}`\n"
        f"💬 **Javob:** {answer}\n\n"
        f"Endi biror a'zo guruhda `{keyword}` so'zini ishlatsa, bot avtomatik javob beradi.",
        parse_mode="Markdown",
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
        await message.reply("Format: `/savolochir [kalit so'z]`\nMasalan: `/savolochir narxlar`", parse_mode="Markdown")
        return

    keyword = parts[1].strip().lower()
    removed = await db.remove_faq(message.chat.id, keyword)
    if removed:
        await message.reply(f"✅ `{keyword}` kalit so'zidagi avto-javob o'chirildi!", parse_mode="Markdown")
    else:
        await message.reply(f"❌ `{keyword}` bo'yicha avto-javob topilmadi.", parse_mode="Markdown")
