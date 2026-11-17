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
