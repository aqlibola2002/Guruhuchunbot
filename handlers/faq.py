from __future__ import annotations

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

from database.db import db
from filters.admin_filter import is_admin

router = Router(name="faq")


# ── /qoidalar va /rules ───────────────────────────────────────────
@router.message(Command("qoidalar", "rules", ignore_case=True))
async def cmd_rules(message: Message) -> None:
    if message.chat.type in ("private",):
        await message.reply("Guruh qoidalarini ko'rish uchun ushbu buyruqni guruhda yuboring.")
        return

    rules = await db.get_group_rules(message.chat.id)
    if not rules:
        rules = (
            "📜 **GURUH QOIDALARI**\n\n"
            "1️⃣ **HURMAT** — Har bir a'zoga hurmat bilan muomala qiling. "
            "Haqorat, kamsitish, millat yoki dinga tegishli haqoratli so'zlar qat'iyan taqiqlanadi.\n\n"
            "2️⃣ **SPAM & REKLAMA** — Ruxsatsiz reklama, havola (link), kanal va guruh targ'iboti taqiqlanadi. "
            "Qoidabuzarlar darhol guruhdan chiqariladi.\n\n"
            "3️⃣ **SIYOSAT & ZIDDIYAT** — Siyosiy tortishuvlar, urush targ'iboti va provokatsion xabarlar taqiqlanadi.\n\n"
            "4️⃣ **YOLG'ON AXBOROT** — Tasdiqlanmagan yangilik, soxta skrinshotlar va yolg'on ma'lumot "
            "tarqatish taqiqlanadi. Manbani tekshiring!\n\n"
            "5️⃣ **APK & ZARARLI FAYLLAR** — Har qanday .apk, .exe va noma'lum fayl yuborish taqiqlanadi. "
            "Telegram orqali tarqalayotgan viruslardan ehtiyot bo'ling!\n\n"
            "6️⃣ **SHAXSIY MA'LUMOT** — Boshqalarning telefon raqami, manzili yoki shaxsiy ma'lumotlarini "
            "ruxsatsiz tarqatish (doxing) taqiqlanadi.\n\n"
            "7️⃣ **FIRIBGARLIK (SCAM)** — \"Pul ishlash\", \"investitsiya\", \"kripto\" bahonasida aldash "
            "urinishlari darhol ban bilan jazolanadi.\n\n"
            "8️⃣ **FORWARD XABARLAR** — Boshqa kanal va guruhlardan xabarlarni forward qilish taqiqlanadi.\n\n"
            "9️⃣ **18+ KONTENT** — Voyaga etmaganlar uchun noma'qul, zo'ravonlik va shok materiallar mutlaqo taqiqlanadi.\n\n"
            "🔟 **DEEPFAKE & AI SOXTA KONTENT** — AI yordamida yaratilgan soxta surat/video tarqatish taqiqlanadi.\n\n"
            "⚠️ **OGOHLANTIRISH TIZIMI:**\n"
            "• 1-ogohlantirish: Xabar o'chiriladi\n"
            "• 2-ogohlantirish: 24 soat sukut (yozish taqiqlanadi)\n"
            "• 3-ogohlantirish: Guruhdan chiqarish\n\n"
            "✅ *Guruhda yozish uchun qoidalarni qabul qilgan deb hisoblanasiz!*\n"
            "ℹ️ *Adminlar: `/yangiqoida [matn]` orqali qoidalarni o'zgartiring*"
        )
    await message.reply(rules, parse_mode="Markdown")


# ── /savollar [Guruhdagi avto-javoblar ro'yxati] ───────────────────
@router.message(Command("savollar", "faqs", "faq", ignore_case=True))
async def cmd_faqs_list(message: Message) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Ushbu buyruq faqat guruhlarda ishlaydi.")
        return

    faqs = await db.get_all_faqs(message.chat.id)
    if not faqs:
        await message.reply(
            "❓ **Guruhda avto-javoblar hali mavjud emas.**\n\n"
            "Adminlar yangi avto-javob qo'shishi mumkin:\n"
            "`/savolqoshish kalit_so'z = javob matni`\n\n"
            "Masalan:\n"
            "`/savolqoshish manzil = Bizning manzil: Toshkent shahar, Chilonzor tumani`",
            parse_mode="Markdown",
        )
        return

    text = f"❓ **'{message.chat.title}' guruhining avto-javoblari (FAQ):**\n\n"
    for idx, f in enumerate(faqs, 1):
        text += f"**{idx}.** `{f['keyword']}` ➔ _{f['answer']}_\n"

    text += (
        "\n💡 *A'zolar ushbu kalit so'zlarni xabarda yozishganda, bot avtomatik javob beradi.*\n"
        "➕ **Qo'shish:** `/savolqoshish so'z = javob`\n"
        "➖ **O'chirish:** `/savolochir so'z`"
    )
    await message.reply(text, parse_mode="Markdown")


# ── /savolqoshish [kalit = javob] ─────────────────────────────────
@router.message(Command("savolqoshish", "addfaq", ignore_case=True))
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
            "`/savolqoshish [kalit so'z] = [javob matni]`\n\n"
            "Masalan:\n"
            "`/savolqoshish narxlar = Xizmat narxlari bilan @kanalimiz orqali tanishishingiz mumkin.`\n"
            "`/savolqoshish qayerda = Biz Chilonzorda joylashganmiz.`",
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
@router.message(Command("savolochir", "delfaq", ignore_case=True))
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
