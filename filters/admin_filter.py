from __future__ import annotations

from aiogram.filters import Filter
from aiogram.types import Message
from aiogram import Bot

from config import ADMIN_IDS


async def is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Foydalanuvchi bot admini yoki guruh admini ekanligini tekshiradi."""
    if user_id in ADMIN_IDS:
        return True

    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ("creator", "administrator")
    except Exception:
        return False


async def can_bot_delete(bot: Bot, chat_id: int) -> bool:
    """Bot guruhda admin ekanligi va xabarlarni o'chira olish huquqi borligini tekshiradi."""
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id=chat_id, user_id=me.id)
        if member.status in ("creator", "administrator"):
            return getattr(member, "can_delete_messages", True)
        return False
    except Exception:
        return False


class IsAdmin(Filter):
    async def __call__(self, message: Message, bot: Bot) -> bool:
        if not message.from_user:
            return False
        return await is_admin(bot, message.chat.id, message.from_user.id)
