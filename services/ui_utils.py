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
