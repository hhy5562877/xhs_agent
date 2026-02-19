import aiosqlite
import pathlib
from contextlib import asynccontextmanager

DB_PATH = pathlib.Path(__file__).parent.parent.parent / "data" / "xhs_agent.db"


@asynccontextmanager
async def get_db():
    """用法：async with get_db() as db:"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        yield db


async def init_db() -> None:
    async with get_db() as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            id           TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            cookie       TEXT NOT NULL,
            xhs_user_id  TEXT,
            nickname     TEXT,
            avatar_url   TEXT,
            fans         TEXT,
            created_at   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS operation_goals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id  TEXT NOT NULL,
            title       TEXT NOT NULL,
            description TEXT NOT NULL,
            style       TEXT NOT NULL DEFAULT '生活方式',
            post_freq   INTEGER NOT NULL DEFAULT 1,
            active      INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        );

        CREATE TABLE IF NOT EXISTS scheduled_posts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id       INTEGER NOT NULL,
            account_id    TEXT NOT NULL,
            topic         TEXT NOT NULL,
            style         TEXT NOT NULL,
            aspect_ratio  TEXT NOT NULL DEFAULT '3:4',
            image_count   INTEGER NOT NULL DEFAULT 1,
            scheduled_at  TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'pending',
            result_title  TEXT,
            result_body   TEXT,
            result_images TEXT,
            note_id       TEXT,
            error         TEXT,
            created_at    TEXT NOT NULL,
            FOREIGN KEY (goal_id) REFERENCES operation_goals(id),
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        );
        """)
        await db.commit()
