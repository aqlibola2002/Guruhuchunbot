from __future__ import annotations

import datetime
from typing import Any
import aiosqlite
from config import DB_PATH


class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS groups (
                    chat_id INTEGER PRIMARY KEY,
                    title TEXT DEFAULT '',
                    rules TEXT DEFAULT '',
                    antilink_enabled INTEGER DEFAULT 1,
                    antispam_enabled INTEGER DEFAULT 1,
                    antiforward_enabled INTEGER DEFAULT 1,
                    channels_enabled INTEGER DEFAULT 1,
                    welcome_enabled INTEGER DEFAULT 1,
                    ai_enabled INTEGER DEFAULT 1,
                    scheduled_enabled INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER,
                    chat_id INTEGER,
                    full_name TEXT DEFAULT '',
                    username TEXT DEFAULT '',
                    message_count INTEGER DEFAULT 0,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, chat_id)
                );

                CREATE TABLE IF NOT EXISTS warns (
                    user_id INTEGER,
                    chat_id INTEGER,
                    warn_count INTEGER DEFAULT 0,
                    last_reason TEXT DEFAULT '',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, chat_id)
                );

                CREATE TABLE IF NOT EXISTS faqs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    keyword TEXT,
                    answer TEXT,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT,
                    chat_id INTEGER,
                    messages_count INTEGER DEFAULT 0,
                    warns_given INTEGER DEFAULT 0,
                    mutes_given INTEGER DEFAULT 0,
                    bans_given INTEGER DEFAULT 0,
                    PRIMARY KEY (date, chat_id)
                );

                CREATE TABLE IF NOT EXISTS user_invites (
                    chat_id INTEGER,
                    inviter_id INTEGER,
                    invited_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (chat_id, invited_id)
                );

                CREATE TABLE IF NOT EXISTS mandatory_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_chat_id INTEGER,
                    channel_id TEXT,
                    title TEXT DEFAULT '',
                    invite_link TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(group_chat_id, channel_id)
                );

                CREATE TABLE IF NOT EXISTS join_requests (
                    user_id INTEGER,
                    channel_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, channel_id)
                );
                """
            )
            # Mavjud bazalar uchun yangi ustunlarni tekshirib qo'shish
            try:
                await conn.execute("ALTER TABLE groups ADD COLUMN min_invites INTEGER DEFAULT 0")
            except Exception:
                pass
            try:
                await conn.execute("ALTER TABLE groups ADD COLUMN invites_enabled INTEGER DEFAULT 1")
            except Exception:
                pass
            try:
                await conn.execute("ALTER TABLE groups ADD COLUMN antiforward_enabled INTEGER DEFAULT 1")
            except Exception:
                pass
            try:
                await conn.execute("ALTER TABLE groups ADD COLUMN channels_enabled INTEGER DEFAULT 1")
            except Exception:
                pass
            await conn.commit()

    # ── Guruh sozlamalari ─────────────────────────────────────────────
    async def get_or_create_group(self, chat_id: int, title: str = "") -> dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM groups WHERE chat_id = ?", (chat_id,)
            )
            row = await cursor.fetchone()
            if not row:
                await conn.execute(
                    """
                    INSERT INTO groups (chat_id, title)
                    VALUES (?, ?)
                    """,
                    (chat_id, title),
                )
                await conn.commit()
                cursor = await conn.execute(
                    "SELECT * FROM groups WHERE chat_id = ?", (chat_id,)
                )
                row = await cursor.fetchone()
            elif title and row["title"] != title:
                await conn.execute(
                    "UPDATE groups SET title = ? WHERE chat_id = ?",
                    (title, chat_id),
                )
                await conn.commit()
            return dict(row)

    async def update_group_setting(self, chat_id: int, setting_name: str, value: int) -> None:
        allowed = {
            "antilink_enabled",
            "antispam_enabled",
            "welcome_enabled",
            "scheduled_enabled",
            "invites_enabled",
            "antiforward_enabled",
            "channels_enabled",
        }
        if setting_name not in allowed:
            return
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                f"UPDATE groups SET {setting_name} = ? WHERE chat_id = ?",
                (value, chat_id),
            )
            await conn.commit()

    async def set_min_invites(self, chat_id: int, count: int) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            if count > 0:
                await conn.execute(
                    "UPDATE groups SET min_invites = ?, invites_enabled = 1 WHERE chat_id = ?",
                    (count, chat_id),
                )
            else:
                await conn.execute(
                    "UPDATE groups SET min_invites = 0 WHERE chat_id = ?",
                    (chat_id,),
                )
            await conn.commit()

    async def set_group_rules(self, chat_id: int, rules: str) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "UPDATE groups SET rules = ? WHERE chat_id = ?",
                (rules, chat_id),
            )
            await conn.commit()

    async def get_group_rules(self, chat_id: int) -> str:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT rules FROM groups WHERE chat_id = ?", (chat_id,)
            )
            row = await cursor.fetchone()
            if row and row["rules"]:
                return row["rules"]
            return ""

    async def get_all_active_groups(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM groups")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ── Foydalanuvchilar va Faollik ────────────────────────────────────
    async def record_user_message(
        self, chat_id: int, user_id: int, full_name: str, username: str | None
    ) -> None:
        today = datetime.date.today().isoformat()
        async with aiosqlite.connect(self.db_path) as conn:
            # Foydalanuvchi xabarlarini oshirish
            await conn.execute(
                """
                INSERT INTO users (user_id, chat_id, full_name, username, message_count, last_seen)
                VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, chat_id) DO UPDATE SET
                    full_name = excluded.full_name,
                    username = excluded.username,
                    message_count = users.message_count + 1,
                    last_seen = CURRENT_TIMESTAMP
                """,
                (user_id, chat_id, full_name, username or ""),
            )

            # Bugungi kunlik statistika
            await conn.execute(
                """
                INSERT INTO daily_stats (date, chat_id, messages_count)
                VALUES (?, ?, 1)
                ON CONFLICT(date, chat_id) DO UPDATE SET
                    messages_count = daily_stats.messages_count + 1
                """,
                (today, chat_id),
            )
            await conn.commit()

    async def get_top_users(self, chat_id: int, limit: int = 10) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT user_id, full_name, username, message_count
                FROM users
                WHERE chat_id = ?
                ORDER BY message_count DESC
                LIMIT ?
                """,
                (chat_id, limit),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_user_by_username(self, chat_id: int, username: str) -> dict[str, Any] | None:
        clean_user = username.strip().lstrip("@").lower()
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM users WHERE chat_id = ? AND LOWER(username) = ? LIMIT 1",
                (chat_id, clean_user),
            )
            row = await cursor.fetchone()
            if not row:
                cursor = await conn.execute(
                    "SELECT * FROM users WHERE LOWER(username) = ? ORDER BY last_seen DESC LIMIT 1",
                    (clean_user,),
                )
                row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_user_by_id(self, chat_id: int, user_id: int) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM users WHERE chat_id = ? AND user_id = ? LIMIT 1",
                (chat_id, user_id),
            )
            row = await cursor.fetchone()
            if not row:
                cursor = await conn.execute(
                    "SELECT * FROM users WHERE user_id = ? ORDER BY last_seen DESC LIMIT 1",
                    (user_id,),
                )
                row = await cursor.fetchone()
            return dict(row) if row else None


    # ── Takliflar / A'zolar qo'shish (Invites) ────────────────────────
    async def record_invite(
        self, chat_id: int, inviter_id: int, invited_id: int, inviter_name: str = "", inviter_username: str = ""
    ) -> tuple[bool, int]:
        """
        Guruhga a'zo qo'shilganini qayd etadi.
        Qaytaradi: (yangi_taklifmi: bool, jami_takliflar_soni: int)
        """
        async with aiosqlite.connect(self.db_path) as conn:
            is_new = False
            try:
                await conn.execute(
                    """
                    INSERT INTO user_invites (chat_id, inviter_id, invited_id)
                    VALUES (?, ?, ?)
                    """,
                    (chat_id, inviter_id, invited_id),
                )
                is_new = True
            except Exception:
                is_new = False

            if inviter_name:
                await conn.execute(
                    """
                    INSERT INTO users (user_id, chat_id, full_name, username)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id, chat_id) DO UPDATE SET
                        full_name = excluded.full_name,
                        username = excluded.username
                    """,
                    (inviter_id, chat_id, inviter_name, inviter_username or ""),
                )

            cursor = await conn.execute(
                "SELECT COUNT(*) FROM user_invites WHERE chat_id = ? AND inviter_id = ?",
                (chat_id, inviter_id),
            )
            row = await cursor.fetchone()
            total_count = row[0] if row else 0

            await conn.commit()
            return is_new, total_count

    async def get_user_invites(self, chat_id: int, user_id: int) -> int:
        """Foydalanuvchi guruhga nechta a'zo qo'shganini aniqlaydi."""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM user_invites WHERE chat_id = ? AND inviter_id = ?",
                (chat_id, user_id),
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_top_inviters(self, chat_id: int, limit: int = 10) -> list[dict[str, Any]]:
        """Guruhga eng ko'p a'zo qo'shgan TOP a'zolar ro'yxati."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT ui.inviter_id as user_id, 
                       COALESCE(u.full_name, 'Foydalanuvchi') as full_name, 
                       COALESCE(u.username, '') as username, 
                       COUNT(ui.invited_id) as invite_count
                FROM user_invites ui
                LEFT JOIN users u ON ui.inviter_id = u.user_id AND ui.chat_id = u.chat_id
                WHERE ui.chat_id = ?
                GROUP BY ui.inviter_id
                ORDER BY invite_count DESC
                LIMIT ?
                """,
                (chat_id, limit),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ── Majburiy kanallar (Mandatory Channels) ─────────────────────────
    async def add_mandatory_channel(
        self, group_chat_id: int, channel_id: str, title: str = "", invite_link: str = ""
    ) -> bool:
        clean_ch = str(channel_id).strip()
        async with aiosqlite.connect(self.db_path) as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO mandatory_channels (group_chat_id, channel_id, title, invite_link)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(group_chat_id, channel_id) DO UPDATE SET
                        title = excluded.title,
                        invite_link = excluded.invite_link
                    """,
                    (group_chat_id, clean_ch, title, invite_link),
                )
                await conn.commit()
                return True
            except Exception:
                return False

    async def get_mandatory_channels(self, group_chat_id: int) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM mandatory_channels WHERE group_chat_id = ? ORDER BY id ASC",
                (group_chat_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def remove_mandatory_channel(self, group_chat_id: int, channel_id: str) -> bool:
        clean_ch = str(channel_id).strip().lower()
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                """
                DELETE FROM mandatory_channels 
                WHERE group_chat_id = ? AND (LOWER(channel_id) = ? OR LOWER(channel_id) = ? OR channel_id = ?)
                """,
                (group_chat_id, clean_ch, f"@{clean_ch.lstrip('@')}".lower(), clean_ch.lstrip("@")),
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def clear_mandatory_channels(self, group_chat_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "DELETE FROM mandatory_channels WHERE group_chat_id = ?",
                (group_chat_id,),
            )
            await conn.commit()

    # ── Arizalar (Join Requests) ──────────────────────────────────────
    async def record_join_request(self, user_id: int, channel_id: str) -> None:
        clean_id = str(channel_id).strip().lower()
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO join_requests (user_id, channel_id)
                VALUES (?, ?)
                ON CONFLICT(user_id, channel_id) DO NOTHING
                """,
                (user_id, clean_id),
            )
            await conn.commit()

    async def has_join_request(self, user_id: int, channel_id: str) -> bool:
        clean_id = str(channel_id).strip().lower()
        variants = [clean_id, clean_id.lstrip("@"), f"@{clean_id.lstrip('@')}"]
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                f"SELECT 1 FROM join_requests WHERE user_id = ? AND channel_id IN ({','.join(['?']*len(variants))}) LIMIT 1",
                (user_id, *variants),
            )
            row = await cursor.fetchone()
            return bool(row)


    # ── Ogohlantirishlar (Warns) ───────────────────────────────────────
    async def add_warn(self, chat_id: int, user_id: int, reason: str = "") -> int:
        today = datetime.date.today().isoformat()
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT warn_count FROM warns WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )
            row = await cursor.fetchone()
            current = (row[0] + 1) if row else 1
            await conn.execute(
                """
                INSERT INTO warns (chat_id, user_id, warn_count, last_reason, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, chat_id) DO UPDATE SET
                    warn_count = ?,
                    last_reason = ?,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (chat_id, user_id, current, reason, current, reason),
            )
            # Kunlik statistika
            await conn.execute(
                """
                INSERT INTO daily_stats (date, chat_id, warns_given)
                VALUES (?, ?, 1)
                ON CONFLICT(date, chat_id) DO UPDATE SET
                    warns_given = daily_stats.warns_given + 1
                """,
                (today, chat_id),
            )
            await conn.commit()
            return current

    async def remove_warn(self, chat_id: int, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT warn_count FROM warns WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )
            row = await cursor.fetchone()
            if not row or row[0] <= 0:
                return 0
            new_count = max(0, row[0] - 1)
            await conn.execute(
                "UPDATE warns SET warn_count = ? WHERE chat_id = ? AND user_id = ?",
                (new_count, chat_id, user_id),
            )
            await conn.commit()
            return new_count

    async def reset_warns(self, chat_id: int, user_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "DELETE FROM warns WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )
            await conn.commit()

    async def get_warns(self, chat_id: int, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT warn_count FROM warns WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    # ── Jazolarni hisobga olish (Stats) ───────────────────────────────
    async def record_punishment(self, chat_id: int, action: str) -> None:
        today = datetime.date.today().isoformat()
        col = "mutes_given" if action == "mute" else "bans_given"
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                f"""
                INSERT INTO daily_stats (date, chat_id, {col})
                VALUES (?, ?, 1)
                ON CONFLICT(date, chat_id) DO UPDATE SET
                    {col} = daily_stats.{col} + 1
                """,
                (today, chat_id),
            )
            await conn.commit()

    async def get_group_stats(self, chat_id: int) -> dict[str, Any]:
        today = datetime.date.today().isoformat()
        async with aiosqlite.connect(self.db_path) as conn:
            # Jami foydalanuvchilar
            cursor = await conn.execute(
                "SELECT COUNT(*), SUM(message_count) FROM users WHERE chat_id = ?",
                (chat_id,),
            )
            user_count, total_msgs = await cursor.fetchone()

            # Bugungi statistika
            cursor = await conn.execute(
                "SELECT messages_count, warns_given, mutes_given, bans_given FROM daily_stats WHERE chat_id = ? AND date = ?",
                (chat_id, today),
            )
            row = await cursor.fetchone()

            today_msgs = row[0] if row else 0
            today_warns = row[1] if row else 0
            today_mutes = row[2] if row else 0
            today_bans = row[3] if row else 0

            return {
                "total_users": user_count or 0,
                "total_messages": total_msgs or 0,
                "today_messages": today_msgs,
                "today_warns": today_warns,
                "today_mutes": today_mutes,
                "today_bans": today_bans,
            }

    async def get_global_stats(self) -> dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM groups")
            row = await cursor.fetchone()
            total_groups = row[0] if row else 0

            cursor = await conn.execute("SELECT COUNT(DISTINCT user_id) FROM users")
            row = await cursor.fetchone()
            total_users = row[0] if row else 0

            cursor = await conn.execute("SELECT SUM(message_count) FROM users")
            row = await cursor.fetchone()
            total_messages = row[0] if row and row[0] else 0

            cursor = await conn.execute("SELECT COUNT(*) FROM user_invites")
            row = await cursor.fetchone()
            total_invites = row[0] if row else 0

            today = datetime.date.today().isoformat()
            cursor = await conn.execute(
                """
                SELECT SUM(messages_count), SUM(warns_given), SUM(mutes_given), SUM(bans_given)
                FROM daily_stats
                WHERE date = ?
                """,
                (today,),
            )
            row = await cursor.fetchone()
            today_msgs = row[0] if row and row[0] else 0
            today_warns = row[1] if row and row[1] else 0
            today_mutes = row[2] if row and row[2] else 0
            today_bans = row[3] if row and row[3] else 0

            return {
                "total_groups": total_groups,
                "total_users": total_users,
                "total_messages": total_messages,
                "total_invites": total_invites,
                "today_messages": today_msgs,
                "today_warns": today_warns,
                "today_mutes": today_mutes,
                "today_bans": today_bans,
            }

    # ── FAQ (Tez-tez beriladigan savollar) ───────────────────────────
    async def add_faq(self, chat_id: int, keyword: str, answer: str, created_by: int) -> None:
        clean_kw = keyword.strip().lower()
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                DELETE FROM faqs WHERE chat_id = ? AND keyword = ?
                """,
                (chat_id, clean_kw),
            )
            await conn.execute(
                """
                INSERT INTO faqs (chat_id, keyword, answer, created_by)
                VALUES (?, ?, ?, ?)
                """,
                (chat_id, clean_kw, answer.strip(), created_by),
            )
            await conn.commit()

    async def remove_faq(self, chat_id: int, keyword: str) -> bool:
        clean_kw = keyword.strip().lower()
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "DELETE FROM faqs WHERE chat_id = ? AND keyword = ?",
                (chat_id, clean_kw),
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def get_all_faqs(self, chat_id: int) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT keyword, answer FROM faqs WHERE chat_id = ? ORDER BY id ASC",
                (chat_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def match_faq(self, chat_id: int, text: str) -> str | None:
        clean_text = text.lower()
        faqs = await self.get_all_faqs(chat_id)
        for faq in faqs:
            kw = faq["keyword"]
            if kw in clean_text:
                return faq["answer"]
        return None


db = Database()


async def init_db() -> None:
    await db.init()
