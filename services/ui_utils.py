from __future__ import annotations


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
