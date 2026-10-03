from __future__ import annotations

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

from database.db import db
from filters.admin_filter import is_admin

router = Router(name="faq")


# ── /qoidalar va /rules ───────────────────────────────────────────
@router.message(Command("qoidalar", "rules"))
async def cmd_rules(message: Message) -> None:
    if message.chat.type in ("private",):
        await message.reply("Guruh qoidalarini ko'rish uchun ushbu buyruqni guruhda yuboring.")
        return

    rules = await db.get_group_rules(message.chat.id)
    if not rules:
        rules = (
            "📜 **Guruh qoidalari:**\n\n"
            "1. Barcha a'zolarga nisbatan hurmat bilan munosabatda bo'ling.\n"
            "2. Begona guruh/kanal havolalari (linklar) va tijoriy reklamalar taqiqlanadi.\n"
            "3. So'kinish, haqorat va behayo kontent qat'iyan man etiladi.\n"
            "4. Spam va ketma-ket bir xil xabarlar yubormang.\n"
            "5. Qoidani buzganlar ogohlantiriladi yoki yozish huquqidan mahrum qilinadi.\n\n"
            "ℹ️ *Adminlar yangi qoidalarni o'rnatishi uchun: `/yangiqoida [matn]`*"
        )
    await message.reply(rules, parse_mode="Markdown")


# ── /savollar va /faq ─────────────────────────────────────────────
@router.message(Command("savollar", "faq"))
async def cmd_faq(message: Message) -> None:
    if message.chat.type in ("private",):
        return

    faqs = await db.get_all_faqs(message.chat.id)
    if not faqs:
        await message.reply(
            "❓ Hozircha bu guruhda tez-tez so'raladigan savollar mavjud emas.\n\n"
            "👮‍♂️ **Adminlar yangi savol-javob qo'shishi uchun:**\n"
            "`/savolqoshish [kalit so'z] = [javob matni]`\n"
            "Masalan: `/savolqoshish narxlar = Kurs narxi oyiga 300 000 so'm.`",
            parse_mode="Markdown",
        )
        return

    text = f"❓ **'{message.chat.title}' guruhi bo'yicha ko'p beriladigan savollar:**\n\n"
    for item in faqs:
        text += f"🔹 **Savol:** {item['keyword'].capitalize()}\n💬 **Javob:** {item['answer']}\n\n"

    await message.reply(text, parse_mode="Markdown")


# ── /savolqoshish va /addfaq ──────────────────────────────────────
@router.message(Command("savolqoshish", "addfaq"))
async def cmd_addfaq(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        return

    if not await is_admin(bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or "=" not in parts[1]:
        await message.reply(
            "⚠️ Yangi savol-javob qo'shish formati:\n"
            "`/savolqoshish [savol/kalit so'z] = [javob matni]`\n\n"
            "Misol: `/savolqoshish aloqa = Admin bilan bog'lanish: @admin_username`"
        )
        return

    kw, ans = parts[1].split("=", 1)
    keyword = kw.strip().lower()
    answer = ans.strip()

    if not keyword or not answer:
        await message.reply("❌ Kalit so'z yoki javob bo'sh bo'lishi mumkin emas!")
        return

    await db.add_faq(message.chat.id, keyword, answer, message.from_user.id)
    await message.reply(
        f"✅ **Yangi savol-javob qo'shildi!**\n\n"
        f"🔹 Kalit so'z: `{keyword}`\n"
        f"💬 Javob: {answer}"
    )


# ── /savolochirish va /delfaq ────────────────────────────────────
@router.message(Command("savolochirish", "delfaq"))
async def cmd_delfaq(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        return

    if not await is_admin(bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("O'chirish uchun: `/savolochirish [kalit so'z]`")
        return

    keyword = parts[1].strip().lower()
    removed = await db.remove_faq(message.chat.id, keyword)
    if removed:
        await message.reply(f"✅ `{keyword}` bo'yicha savol-javob o'chirildi.")
    else:
        await message.reply(f"❌ `{keyword}` bo'yicha ma'lumot topilmadi.")
