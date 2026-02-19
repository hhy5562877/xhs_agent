import uuid
import asyncio
from datetime import datetime
from ..db import get_db


async def list_accounts() -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            "SELECT id, name, cookie, xhs_user_id, nickname, avatar_url, fans, created_at FROM accounts ORDER BY created_at DESC"
        ) as cur:
            rows = await cur.fetchall()
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "cookie_preview": r["cookie"][:20] + "..." if len(r["cookie"]) > 20 else r["cookie"],
            "xhs_user_id": r["xhs_user_id"] or "",
            "nickname": r["nickname"] or "",
            "avatar_url": r["avatar_url"] or "",
            "fans": r["fans"] or "",
            "created_at": r["created_at"],
        }
        for r in rows
    ]


async def get_cookie(account_id: str) -> str | None:
    async with get_db() as db:
        async with db.execute("SELECT cookie FROM accounts WHERE id = ?", (account_id,)) as cur:
            row = await cur.fetchone()
    return row["cookie"] if row else None


async def add_account(name: str, cookie: str) -> dict:
    from .upload_service import fetch_user_info
    account_id = str(uuid.uuid4())
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 拉取用户信息（失败不阻断保存）
    user_info: dict = {}
    try:
        user_info = await asyncio.to_thread(fetch_user_info, cookie)
        # 如果没有传入名称，用昵称作为默认名
        if not name and user_info.get("nickname"):
            name = user_info["nickname"]
    except Exception:
        pass

    async with get_db() as db:
        await db.execute(
            """INSERT INTO accounts (id, name, cookie, xhs_user_id, nickname, avatar_url, fans, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                account_id, name, cookie,
                user_info.get("xhs_user_id", ""),
                user_info.get("nickname", ""),
                user_info.get("avatar_url", ""),
                user_info.get("fans", ""),
                created_at,
            ),
        )
        await db.commit()
    return {
        "id": account_id, "name": name, "created_at": created_at,
        **user_info,
    }


async def delete_account(account_id: str) -> bool:
    async with get_db() as db:
        cur = await db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        await db.commit()
    return cur.rowcount > 0


async def update_account(account_id: str, name: str | None = None, cookie: str | None = None) -> bool:
    fields, values = [], []
    if name is not None:
        fields.append("name = ?"); values.append(name)
    if cookie is not None:
        fields.append("cookie = ?"); values.append(cookie)
    if not fields:
        return False
    values.append(account_id)
    async with get_db() as db:
        cur = await db.execute(f"UPDATE accounts SET {', '.join(fields)} WHERE id = ?", values)
        await db.commit()
    return cur.rowcount > 0
