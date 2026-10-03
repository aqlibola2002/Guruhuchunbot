from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database.db import db

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
