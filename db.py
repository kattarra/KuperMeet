"""SQLite storage layer for KuperMeet.

Uses aiosqlite so database operations do not block the aiogram event loop.
The database file is created automatically on first startup.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import aiosqlite

DB_PATH = Path(__file__).with_name("kupermeet.db")

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL UNIQUE,
    username TEXT,
    name TEXT NOT NULL CHECK(length(name) <= 30),
    age INTEGER NOT NULL CHECK(age BETWEEN 14 AND 99),
    age_segment TEXT NOT NULL CHECK(age_segment IN ('teen', 'adult')),
    age_verified INTEGER NOT NULL DEFAULT 0 CHECK(age_verified IN (0, 1)),
    city TEXT NOT NULL DEFAULT 'Омск',
    photo_id TEXT NOT NULL,
    bio TEXT NOT NULL DEFAULT '' CHECK(length(bio) <= 100),
    is_premium INTEGER NOT NULL DEFAULT 0 CHECK(is_premium IN (0, 1)),
    premium_at TEXT,
    approved INTEGER NOT NULL DEFAULT 0 CHECK(approved IN (0, 1)),
    banned INTEGER NOT NULL DEFAULT 0 CHECK(banned IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS views (
    user_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('like', 'dislike', 'report')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, target_id)
);

CREATE TABLE IF NOT EXISTS matches (
    user1 INTEGER NOT NULL,
    user2 INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user1, user2),
    CHECK(user1 < user2)
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    reason TEXT NOT NULL CHECK(length(reason) <= 200),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'dismissed', 'actioned')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id INTEGER NOT NULL,
    to_id INTEGER NOT NULL,
    text TEXT NOT NULL CHECK(length(text) <= 300),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'accepted', 'rejected')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_limits (
    user_id INTEGER PRIMARY KEY,
    subscribed INTEGER NOT NULL DEFAULT 0 CHECK(subscribed IN (0, 1)),
    subscribed_at TEXT
);

CREATE TABLE IF NOT EXISTS daily_likes (
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0 CHECK(count >= 0),
    PRIMARY KEY (user_id, date)
);

CREATE INDEX IF NOT EXISTS idx_users_pool
    ON users(city, age_segment, approved, banned, is_premium);
CREATE INDEX IF NOT EXISTS idx_views_target_action
    ON views(user_id, target_id, action);
CREATE INDEX IF NOT EXISTS idx_messages_inbox
    ON messages(to_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_outbox
    ON messages(from_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_status
    ON reports(status, created_at DESC);
"""


def _age_segment(age: int) -> str:
    if not 14 <= age <= 99:
        raise ValueError("Возраст должен быть от 14 до 99 лет")
    return "teen" if age < 18 else "adult"


async def init_db() -> None:
    """Create the database and all tables/indexes if they do not exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def execute(query: str, params: tuple[Any, ...] = ()) -> int:
    """Execute a write query and return the last inserted row id."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        await db.commit()
        return cursor.lastrowid or 0


async def fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
        return dict(row) if row else None


async def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def create_user(
    *,
    tg_id: int,
    username: str,
    name: str,
    age: int,
    city: str,
    photo_id: str,
    bio: str = "",
) -> None:
    """Create an unapproved profile; moderators must approve it before discovery."""
    if not username:
        raise ValueError("Для регистрации необходим Telegram username")
    if len(name) > 30 or len(bio) > 100:
        raise ValueError("Имя или описание превышает допустимую длину")

    await execute(
        """
        INSERT INTO users
            (tg_id, username, name, age, age_segment, city, photo_id, bio)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (tg_id, username.lstrip("@"), name.strip(), age, _age_segment(age),
         city.strip() or "Омск", photo_id, bio.strip()),
    )
    await execute(
        "INSERT OR IGNORE INTO user_limits (user_id) VALUES (?)",
        (tg_id,),
    )


async def get_user(tg_id: int) -> dict[str, Any] | None:
    return await fetch_one("SELECT * FROM users WHERE tg_id = ?", (tg_id,))


async def set_user_approved(tg_id: int, approved: bool) -> None:
    await execute(
        "UPDATE users SET approved = ?, updated_at = CURRENT_TIMESTAMP WHERE tg_id = ?",
        (int(approved), tg_id),
    )


async def ban_user(tg_id: int) -> None:
    await execute(
        "UPDATE users SET banned = 1, approved = 0, updated_at = CURRENT_TIMESTAMP WHERE tg_id = ?",
        (tg_id,),
    )


async def record_view(user_id: int, target_id: int, action: str) -> None:
    if action not in {"like", "dislike", "report"}:
        raise ValueError("Недопустимое действие с анкетой")
    await execute(
        """
        INSERT INTO views (user_id, target_id, action)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, target_id)
        DO UPDATE SET action = excluded.action, created_at = CURRENT_TIMESTAMP
        """,
        (user_id, target_id, action),
    )


async def create_match(user_a: int, user_b: int) -> None:
    if user_a == user_b:
        return
    user1, user2 = sorted((user_a, user_b))
    await execute(
        "INSERT OR IGNORE INTO matches (user1, user2) VALUES (?, ?)",
        (user1, user2),
    )


async def get_daily_like_count(user_id: int, day: date) -> int:
    row = await fetch_one(
        "SELECT count FROM daily_likes WHERE user_id = ? AND date = ?",
        (user_id, day.isoformat()),
    )
    return int(row["count"]) if row else 0


async def increment_daily_likes(user_id: int, day: date) -> int:
    await execute(
        """
        INSERT INTO daily_likes (user_id, date, count)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, date)
        DO UPDATE SET count = count + 1
        """,
        (user_id, day.isoformat()),
    )
    return await get_daily_like_count(user_id, day)


async def delete_user(tg_id: int) -> None:
    """Delete a rejected profile and its per-user limits."""
    await execute("DELETE FROM user_limits WHERE user_id = ?", (tg_id,))
    await execute("DELETE FROM users WHERE tg_id = ?", (tg_id,))


async def get_next_profile(viewer_id: int) -> dict[str, Any] | None:
    """Find the next approved, unseen profile compatible with the viewer."""
    viewer = await get_user(viewer_id)
    if not viewer or not viewer["approved"] or viewer["banned"]:
        return None
    candidates = await fetch_all(
        """
        SELECT u.* FROM users u
        WHERE u.tg_id != ?
          AND u.city = ?
          AND u.approved = 1
          AND u.banned = 0
          AND u.age_segment = ?
          AND NOT EXISTS (
              SELECT 1 FROM views v
              WHERE v.user_id = ? AND v.target_id = u.tg_id
          )
        ORDER BY u.is_premium DESC, u.created_at DESC
        """,
        (viewer_id, viewer["city"], viewer["age_segment"], viewer_id),
    )
    from age_filter import are_ages_compatible
    for candidate in candidates:
        if are_ages_compatible(
            int(viewer["age"]),
            int(candidate["age"]),
            teen_segment_enabled=False,
            both_ages_verified=False,
        ):
            return candidate
    return None


async def has_liked(user_id: int, target_id: int) -> bool:
    row = await fetch_one(
        "SELECT 1 AS found FROM views WHERE user_id = ? AND target_id = ? AND action = 'like'",
        (user_id, target_id),
    )
    return bool(row)


async def get_user_like_limit(user_id: int) -> int:
    row = await fetch_one(
        "SELECT subscribed FROM user_limits WHERE user_id = ?",
        (user_id,),
    )
    return 100 if row and row["subscribed"] else 10


async def get_match_profile_ids(user_id: int) -> list[int]:
    rows = await fetch_all(
        """
        SELECT CASE WHEN user1 = ? THEN user2 ELSE user1 END AS other_id
        FROM matches WHERE user1 = ? OR user2 = ?
        ORDER BY created_at DESC
        """,
        (user_id, user_id, user_id),
    )
    return [int(row["other_id"]) for row in rows]


async def create_message_request(from_id: int, to_id: int, text: str) -> int:
    """Create one pending intro request, preventing duplicate pending requests."""
    body = text.strip()
    if not body or len(body) > 300:
        raise ValueError("Сообщение должно содержать от 1 до 300 символов")
    if from_id == to_id:
        raise ValueError("Нельзя отправить сообщение самому себе")
    sender = await get_user(from_id)
    recipient = await get_user(to_id)
    if not sender or not recipient:
        raise ValueError("Профиль не найден")
    if not sender["approved"] or sender["banned"] or not recipient["approved"] or recipient["banned"]:
        raise ValueError("Один из профилей недоступен")
    from age_filter import are_ages_compatible
    if not are_ages_compatible(
        int(sender["age"]),
        int(recipient["age"]),
        teen_segment_enabled=False,
        both_ages_verified=False,
    ):
        raise ValueError("Возрастная совместимость не позволяет отправить запрос")
    existing = await fetch_one(
        """
        SELECT id FROM messages
        WHERE from_id = ? AND to_id = ? AND status = 'pending'
        ORDER BY id DESC LIMIT 1
        """,
        (from_id, to_id),
    )
    if existing:
        raise ValueError("У тебя уже есть ожидающий запрос этому пользователю")
    return await execute(
        "INSERT INTO messages (from_id, to_id, text) VALUES (?, ?, ?)",
        (from_id, to_id, body),
    )


async def get_pending_message_requests(user_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        """
        SELECT m.*, u.name AS sender_name, u.age AS sender_age,
               u.city AS sender_city, u.username AS sender_username,
               u.photo_id AS sender_photo
        FROM messages m
        JOIN users u ON u.tg_id = m.from_id
        WHERE m.to_id = ? AND m.status = 'pending'
          AND u.approved = 1 AND u.banned = 0
        ORDER BY m.created_at DESC
        """,
        (user_id,),
    )


async def get_message_request(message_id: int) -> dict[str, Any] | None:
    return await fetch_one("SELECT * FROM messages WHERE id = ?", (message_id,))


async def update_message_request(message_id: int, recipient_id: int, status: str) -> bool:
    if status not in {"accepted", "rejected"}:
        raise ValueError("Недопустимый статус запроса")
    current = await fetch_one(
        "SELECT id FROM messages WHERE id = ? AND to_id = ? AND status = 'pending'",
        (message_id, recipient_id),
    )
    if not current:
        return False
    await execute(
        """
        UPDATE messages SET status = ?
        WHERE id = ? AND to_id = ? AND status = 'pending'
        """,
        (status, message_id, recipient_id),
    )
    return True


async def create_report(reporter_id: int, target_id: int, reason: str) -> int:
    body = reason.strip()
    if not body or len(body) > 200:
        raise ValueError("Причина жалобы должна содержать от 1 до 200 символов")
    if reporter_id == target_id:
        raise ValueError("Нельзя пожаловаться на собственную анкету")
    reporter = await get_user(reporter_id)
    target = await get_user(target_id)
    if not reporter or not target:
        raise ValueError("Анкета не найдена")
    if not reporter["approved"] or reporter["banned"]:
        raise ValueError("Отправлять жалобы можно только с активной анкеты")
    if not target["approved"] or target["banned"]:
        raise ValueError("Эта анкета больше недоступна")
    pending = await fetch_one(
        """
        SELECT id FROM reports
        WHERE reporter_id = ? AND target_id = ? AND status = 'pending'
        LIMIT 1
        """,
        (reporter_id, target_id),
    )
    if pending:
        raise ValueError("Ты уже отправил(а) жалобу на эту анкету")
    return await execute(
        "INSERT INTO reports (reporter_id, target_id, reason) VALUES (?, ?, ?)",
        (reporter_id, target_id, body),
    )


async def get_report(report_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        """
        SELECT r.*, reporter.name AS reporter_name,
               target.name AS target_name, target.age AS target_age,
               target.username AS target_username, target.photo_id AS target_photo
        FROM reports r
        JOIN users reporter ON reporter.tg_id = r.reporter_id
        JOIN users target ON target.tg_id = r.target_id
        WHERE r.id = ?
        """,
        (report_id,),
    )


async def resolve_report(report_id: int, status: str) -> bool:
    if status not in {"dismissed", "actioned"}:
        raise ValueError("Недопустимый статус жалобы")
    current = await fetch_one(
        "SELECT id FROM reports WHERE id = ? AND status = 'pending'",
        (report_id,),
    )
    if not current:
        return False
    await execute(
        "UPDATE reports SET status = ? WHERE id = ? AND status = 'pending'",
        (status, report_id),
    )
    return True
