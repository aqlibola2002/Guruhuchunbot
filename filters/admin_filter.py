from __future__ import annotations

from aiogram.filters import Filter
from aiogram.types import Message
from aiogram import Bot

from config import ADMIN_IDS


ANONYMOUS_ADMIN_ID = 1087968824  # @GroupAnonymousBot
CHANNEL_BOT_ID = 136817688       # @Channel_Bot
SERVICE_BOT_ID = 777000          # Telegram Service Notifications


async def is_admin(bot: Bot, chat_id: int, user_id: int | None = None, message: Message | None = None) -> bool:
    """
    Foydalanuvchi bot admini yoki guruh admini (shu jumladan anonim admin) ekanligini tekshiradi.
    Adminlarning hech qanday xabari hech qachon o'chirilmaydi!
    """
    # 1. Botning asosiy egasi / Super admini (masalan ID: 8781024332)
    if user_id and user_id in ADMIN_IDS:
        return True

    # 2. Xabar obyekti orqali anonim adminlarni 100% aniqlash
    if message is not None:
        # Telegramda guruh admini anonim yozganda sender_chat guruhning o'zi bo'ladi
        if message.sender_chat and message.sender_chat.id == message.chat.id:
            return True

        if message.from_user:
            # Super admin
            if message.from_user.id in ADMIN_IDS:
                return True

            # Telegram anonim admin botlari
            if message.from_user.id in (ANONYMOUS_ADMIN_ID, CHANNEL_BOT_ID, SERVICE_BOT_ID):
                return True

            if (message.from_user.username or "") in ("GroupAnonymousBot", "Channel_Bot"):
                return True

        # Guruhga ulangan rasmiy kanal bo'lsa
        if message.sender_chat:
            try:
                chat = await bot.get_chat(chat_id)
                if getattr(chat, "linked_chat_id", None) == message.sender_chat.id:
                    return True
            except Exception:
                pass

        if user_id is None and message.from_user:
            user_id = message.from_user.id

    # 3. ID bo'yicha maxsus botlar tekshiruvi
    if user_id in (ANONYMOUS_ADMIN_ID, CHANNEL_BOT_ID, SERVICE_BOT_ID):
        return True

    if not user_id:
        # Agar user_id bo'lmay, xabarda guruh nomidan sender_chat bo'lsa (anonim admin)
        if message and message.sender_chat and message.sender_chat.id == message.chat.id:
            return True
        return False

    # 4. Telegram API orqali guruh adminlari ro'yxatidan tekshirish
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
        if message.sender_chat and message.sender_chat.id == message.chat.id:
            return True
        if message.from_user:
            if message.from_user.id in (ANONYMOUS_ADMIN_ID, CHANNEL_BOT_ID, SERVICE_BOT_ID):
                return True
            if (message.from_user.username or "") in ("GroupAnonymousBot", "Channel_Bot"):
                return True
            if message.from_user.id in ADMIN_IDS:
                return True
        user_id = message.from_user.id if message.from_user else None
        return await is_admin(bot, message.chat.id, user_id, message=message)
