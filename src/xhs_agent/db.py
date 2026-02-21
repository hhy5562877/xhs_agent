import aiosqlite
import re
import logging
import pathlib
from contextlib import asynccontextmanager

DB_PATH = pathlib.Path(__file__).parent.parent.parent / "data" / "xhs_agent.db"

logger = logging.getLogger("xhs_agent")


@asynccontextmanager
async def get_db():
    """用法：async with get_db() as db:"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        yield db


_SCHEMA_SQL = """
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
    ref_image_ids TEXT NOT NULL DEFAULT '[]',
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

CREATE TABLE IF NOT EXISTS system_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS image_groups (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id    TEXT NOT NULL,
    category      TEXT NOT NULL DEFAULT 'style',
    user_prompt   TEXT NOT NULL DEFAULT '',
    annotation    TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'pending',
    created_at    TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS account_images (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id      INTEGER NOT NULL DEFAULT 0,
    account_id    TEXT NOT NULL,
    file_path     TEXT NOT NULL,
    original_name TEXT NOT NULL,
    category      TEXT NOT NULL DEFAULT 'style',
    user_prompt   TEXT NOT NULL DEFAULT '',
    annotation    TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'pending',
    created_at    TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (group_id) REFERENCES image_groups(id)
);
"""

_COL_RE = re.compile(
    r"^\s+(\w+)\s+(TEXT|INTEGER|REAL|BLOB|NUMERIC)(.*)$", re.IGNORECASE
)


def _parse_expected_columns(schema_sql: str) -> dict[str, list[tuple[str, str]]]:
    """从 CREATE TABLE 语句中解析每张表期望的列定义。
    返回 {table_name: [(col_name, full_col_def), ...]}
    """
    tables: dict[str, list[tuple[str, str]]] = {}
    current_table: str | None = None
    for line in schema_sql.splitlines():
        m = re.match(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", line, re.IGNORECASE)
        if m:
            current_table = m.group(1)
            tables[current_table] = []
            continue
        if current_table and line.strip().startswith(")"):
            current_table = None
            continue
        if current_table:
            cm = _COL_RE.match(line)
            if cm:
                col_name = cm.group(1)
                col_type = cm.group(2).upper()
                rest = cm.group(3).rstrip(",").strip()
                col_def = f"{col_type} {rest}".strip() if rest else col_type
                tables[current_table].append((col_name, col_def))
    return tables


async def _auto_migrate(db: aiosqlite.Connection) -> None:
    """对比 schema 定义与实际表结构，自动补充缺失的列。"""
    expected = _parse_expected_columns(_SCHEMA_SQL)
    for table_name, columns in expected.items():
        async with db.execute(f"PRAGMA table_info({table_name})") as cur:
            rows = await cur.fetchall()
        existing_cols = {row[1] for row in rows}
        for col_name, col_def in columns:
            if col_name not in existing_cols:
                alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"
                try:
                    await db.execute(alter_sql)
                    logger.info(f"[DB迁移] {table_name} 补充字段: {col_name} {col_def}")
                except Exception as e:
                    logger.warning(f"[DB迁移] {table_name}.{col_name} 失败: {e}")


async def init_db() -> None:
    async with get_db() as db:
        await db.executescript(_SCHEMA_SQL)
        await _auto_migrate(db)
        await db.commit()


async def get_config(key: str, default: str = "") -> str:
    async with get_db() as db:
        async with db.execute(
            "SELECT value FROM system_config WHERE key = ?", (key,)
        ) as cur:
            row = await cur.fetchone()
    return row["value"] if row else default


async def set_config(key: str, value: str) -> None:
    async with get_db() as db:
        await db.execute(
            "INSERT INTO system_config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await db.commit()
