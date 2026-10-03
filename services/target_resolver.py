from __future__ import annotations

from dataclasses import dataclass
from aiogram.enums import MessageEntityType
from aiogram.types import Message
from database.db import db


@dataclass
class TargetResult:
    user_id: int | None = None
    full_name: str | None = None
    username: str | None = None
    remaining_text: str = ""
    error: str | None = None


async def resolve_target(message: Message) -> TargetResult:
    """
    Xabardan jazolanadigan yoki tekshiriladigan foydalanuvchini aniqlash:
    1. Reply qilingan xabar orqali
    2. Matndagi @username orqali
    3. Matndagi Telegram ID orqali
    4. Text mention orqali
    """
    raw_text = (message.text or message.caption or "").strip()
    parts = raw_text.split()
    remaining = " ".join(parts[1:]) if len(parts) > 1 else ""

    # 1. Reply to message tekshiruvi (eng aniq va ishonchli usul)
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        return TargetResult(
            user_id=target.id,
            full_name=target.full_name,
            username=target.username,
            remaining_text=remaining,
        )

    # 2. Text mention (Telegram entity orqali to'g'ridan-to'g'ri foydalanuvchi obyekti)
    if message.entities:
        for ent in message.entities:
            if ent.type == MessageEntityType.TEXT_MENTION and ent.user:
                return TargetResult(
                    user_id=ent.user.id,
                    full_name=ent.user.full_name,
                    username=ent.user.username,
                    remaining_text=" ".join(parts[2:]) if len(parts) > 2 else "",
                )

    # 3. Argumentlar mavjud bo'lsa (ID yoki @username)
    if len(parts) > 1:
        first_arg = parts[1].strip()

        # Agar raqam bo'lsa (Telegram User ID)
        if first_arg.isdigit():
            target_id = int(first_arg)
            user_db = await db.get_user_by_id(message.chat.id, target_id)
            full_name = user_db["full_name"] if user_db else f"ID: {target_id}"
            username = user_db["username"] if user_db else None
            return TargetResult(
                user_id=target_id,
                full_name=full_name,
                username=username,
                remaining_text=" ".join(parts[2:]) if len(parts) > 2 else "",
            )

        # Agar @ bilan boshlansa (@username)
        if first_arg.startswith("@"):
            clean_username = first_arg.lstrip("@")
            user_db = await db.get_user_by_username(message.chat.id, clean_username)
            if user_db:
                return TargetResult(
                    user_id=user_db["user_id"],
                    full_name=user_db["full_name"],
                    username=user_db["username"],
                    remaining_text=" ".join(parts[2:]) if len(parts) > 2 else "",
                )
            else:
                return TargetResult(
                    error=(
                        f"❌ `@{clean_username}` guruh bazasidan topilmadi!\n"
                        f"Foydalanuvchi guruhda hali xabar yozmagan bo'lishi mumkin. "
                        f"Iltimos, uning xabariga **Reply** qiling yoki uning raqamli **Telegram ID**sini kiriting."
                    )
                )

    # Agar hech qanday nishon topilmasa
    return TargetResult(
        error=(
            "⚠️ Foydalanuvchini ko'rsating:\n"
            "• Foydalanuvchining xabariga **Reply** (Javob) qiling\n"
            "• Yoki `@username` kiriting (masalan: `/ogohlantir @username`)\n"
            "• Yoki Telegram **ID** raqamini kiriting (masalan: `/ogohlantir 123456789`)"
        )
    )
