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
            "📜 **Guruh qoidalari:**\n\n"
            "1. Barcha a'zolarga nisbatan hurmat bilan munosabatda bo'ling.\n"
            "2. Begona guruh/kanal havolalari (linklar) va tijoriy reklamalar taqiqlanadi.\n"
            "3. So'kinish, haqorat va behayo kontent qat'iyan man etiladi.\n"
            "4. Har qanday APK (.apk) fayllar va viruslar tarqatish taqiqlanadi.\n"
            "5. Spam va ketma-ket bir xil xabarlar yubormang.\n"
            "6. Qoidani buzganlar ogohlantiriladi yoki yozish huquqidan mahrum qilinadi.\n\n"
            "ℹ️ *Adminlar yangi qoidalarni o'rnatishi uchun: `/yangiqoida [matn]`*"
        )
    await message.reply(rules, parse_mode="Markdown")
