from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from aiogram.types import Message


def escape_md(text: str | None) -> str:
    """Telegram Markdown xatoliklarini oldini olish uchun xavfli belgilarni zararsizlantiradi."""
    if not text:
        return ""
    return (
        str(text)
        .replace("[", "(")
        .replace("]", ")")
        .replace("*", "")
        .replace("_", " ")
        .replace("`", "'")
    )


def safe_mention(full_name: str | None, user_id: int | None = None) -> str:
    """Foydalanuvchi ismidan xavfsiz Telegram Markdown linkini yasaydi."""
    clean_name = escape_md(full_name) or "Foydalanuvchi"
    if user_id:
        return f"[{clean_name}](tg://user?id={user_id})"
    return clean_name


async def safe_reply(message: Message, text: str, reply_markup=None, **kwargs) -> Message | None:
    """Xabarni xavfsiz yuborish: agar Markdown parsingda xatolik yuz bersa, toza matn ko'rinishida yuboradi."""
    try:
        return await message.reply(text, reply_markup=reply_markup, parse_mode="Markdown", **kwargs)
    except Exception:
        clean = text.replace("*", "").replace("_", "").replace("`", "")
        try:
            return await message.reply(clean, reply_markup=reply_markup, **kwargs)
        except Exception:
            return None


def make_progress_bar(percent: int | float, length: int = 10) -> str:
    """
    1 dan 100 gacha foizga mos zamonaviy va chiroyli progress bar chizadi.
    Masalan: 40% -> ▰▰▰▰▱▱▱▱▱▱
             100% -> ▰▰▰▰▰▰▰▰▰▰
    """
    try:
        pct = max(0, min(100, int(round(percent))))
    except Exception:
        pct = 0

    if pct <= 0:
        filled = 0
    elif pct >= 100:
        filled = length
    else:
        raw = int(round((pct / 100.0) * length))
        filled = max(1, min(length - 1, raw))

    return "▰" * filled + "▱" * (length - filled)


def get_level_title(level: int) -> str:
    """Foydalanuvchi darajasiga mos premium unvonni aniqlash."""
    if level < 5:
        return "🥉 Yangi a'zo"
    elif level < 10:
        return "🥈 Faol suhbatdosh"
    elif level < 20:
        return "🥇 Guruh yulduzi"
    elif level < 35:
        return "💎 Guruh faxri"
    elif level < 50:
        return "👑 Guruh yetakchisi"
    else:
        return "⚡️ AFSONAVIY A'ZO"


# Foydalanuvchilarga yuborilgan taklif talabi ogohlantirish xabarlari:
# (chat_id, user_id) -> set[message_id]
USER_INVITE_WARN_MSGS: dict[tuple[int, int], set[int]] = {}


def set_user_invite_warn_msg(chat_id: int, user_id: int, message_id: int) -> None:
    """Foydalanuvchiga yuborilgan ogohlantirish xabari ID sini saqlash."""
    USER_INVITE_WARN_MSGS.setdefault((chat_id, user_id), set()).add(message_id)


def pop_user_invite_warn_msgs(chat_id: int, user_id: int) -> list[int]:
    """Foydalanuvchining barcha avvalgi ogohlantirish xabarlari ID larini olish va o'chirish."""
    return list(USER_INVITE_WARN_MSGS.pop((chat_id, user_id), set()))


def pop_user_invite_warn_msg(chat_id: int, user_id: int) -> int | None:
    """Foydalanuvchining oxirgi ogohlantirish xabari ID sini olish va o'chirish."""
    msgs = pop_user_invite_warn_msgs(chat_id, user_id)
    return msgs[-1] if msgs else None


def normalize_channel_id(ch_raw: str | int) -> tuple[int | str, str]:
    """
    Kanal identifikatorini Telegram API va ma'lumotlar bazasi uchun to'g'ri standartga keltiradi.
    Qaytaradi: (target_id_for_telegram, clean_string_for_db)
    
    Telegram kanallari va superguruhlari sonli bo'lsa DOIM -100 bilan boshlanadi:
    - '2121239046' -> -1002121239046, '-1002121239046'
    - '-2121239046' -> -1002121239046, '-1002121239046'
    - '-1002121239046' -> -1002121239046, '-1002121239046'
    - '@kanal' -> '@kanal', '@kanal'
    - 'kanal' -> '@kanal', '@kanal'
    - 'https://t.me/kanal' -> '@kanal', '@kanal'
    - 'https://t.me/c/2121239046' -> -1002121239046, '-1002121239046'
    """
    raw = str(ch_raw).strip()
    if not raw:
        return "", ""

    # Havolalardan tozalash
    if "t.me/c/" in raw:
        clean_num = raw.split("t.me/c/")[1].split("/")[0].split("?")[0].strip().replace("-100", "").lstrip("-")
        if clean_num.isdigit():
            num_id = int(f"-100{clean_num}")
            return num_id, str(num_id)
    elif "t.me/" in raw and not ("+" in raw or "joinchat" in raw):
        after = raw.split("t.me/")[1].split("/")[0].split("?")[0].strip()
        raw = after

    clean_num = raw.replace("-100", "").lstrip("-")
    if clean_num.isdigit():
        num_id = int(f"-100{clean_num}")
        return num_id, str(num_id)

    if "+" in raw or "joinchat" in raw:
        return raw, raw

    u_name = raw if raw.startswith("@") else f"@{raw}"
    return u_name, u_name.lower()

