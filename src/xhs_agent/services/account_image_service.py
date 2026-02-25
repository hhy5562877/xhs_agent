import asyncio
import logging
import pathlib
import uuid
from datetime import datetime

from ..db import get_db
from ..config import get_setting

logger = logging.getLogger("xhs_agent")

IMAGE_CATEGORIES = {
    "style": {"name": "风格参考", "desc": "整体视觉调性参考，决定生图的感觉"},
    "person": {"name": "人物形象", "desc": "真人/IP/宠物，保持跨帖一致性"},
    "product": {"name": "产品素材", "desc": "要推广的产品/物品"},
    "scene": {"name": "场景环境", "desc": "拍摄场景/背景环境"},
    "brand": {"name": "品牌元素", "desc": "Logo、色卡、视觉规范"},
}

_MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

MAX_GROUP_SIZE = 9


async def save_group(
    account_id: str,
    files: list[tuple[bytes, str]],
    category: str = "style",
    user_prompt: str = "",
) -> dict:
    from .cos_service import upload_bytes

    if category not in IMAGE_CATEGORIES:
        category = "style"
    if len(files) > MAX_GROUP_SIZE:
        files = files[:MAX_GROUP_SIZE]

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    async with get_db() as db:
        cur = await db.execute(
            """INSERT INTO image_groups
               (account_id, category, user_prompt, annotation, status, created_at)
               VALUES (?, ?, ?, '', 'pending', ?)""",
            (account_id, category, user_prompt, created_at),
        )
        await db.commit()
        group_id = cur.lastrowid

    path_prefix = await get_setting("cos_path_prefix")
    path_prefix = path_prefix.strip("/")

    image_records = []
    for file_bytes, original_name in files:
        ext = pathlib.Path(original_name).suffix.lower() or ".jpg"
        filename = f"{uuid.uuid4().hex}{ext}"
        cos_key = f"{path_prefix}/{account_id}/{category}/{filename}"
        content_type = _MIME_MAP.get(ext, "image/jpeg")

        cos_url = await upload_bytes(cos_key, file_bytes, content_type)

        async with get_db() as db:
            cur = await db.execute(
                """INSERT INTO account_images
                   (group_id, account_id, file_path, original_name, category, user_prompt, annotation, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, '', 'pending', ?)""",
                (
                    group_id,
                    account_id,
                    cos_url,
                    original_name,
                    category,
                    user_prompt,
                    created_at,
                ),
            )
            await db.commit()
            image_records.append(
                {
                    "id": cur.lastrowid,
                    "file_path": cos_url,
                    "original_name": original_name,
                }
            )

    group_record = {
        "id": group_id,
        "account_id": account_id,
        "category": category,
        "user_prompt": user_prompt,
        "annotation": "",
        "status": "pending",
        "created_at": created_at,
        "images": image_records,
    }

    asyncio.create_task(_run_group_vision(group_id, category, user_prompt))

    return group_record


async def _run_group_vision(group_id: int, category: str, user_prompt: str) -> None:
    from .vision_service import analyze_image_group

    async with get_db() as db:
        async with db.execute(
            "SELECT id, file_path FROM account_images WHERE group_id = ? ORDER BY id",
            (group_id,),
        ) as cur:
            images = await cur.fetchall()

    image_urls = [img["file_path"] for img in images]
    if not image_urls:
        return

    try:
        annotation = await analyze_image_group(
            image_urls, category=category, user_prompt=user_prompt
        )
        async with get_db() as db:
            await db.execute(
                "UPDATE image_groups SET annotation = ?, status = 'done' WHERE id = ?",
                (annotation, group_id),
            )
            await db.execute(
                "UPDATE account_images SET status = 'done' WHERE group_id = ?",
                (group_id,),
            )
            await db.commit()
        logger.info(
            f"图片组 #{group_id} 识别完成 ({len(image_urls)}张): {annotation[:80]}..."
        )
    except Exception as e:
        logger.error(f"图片组 #{group_id} 识别失败: {e}")
        async with get_db() as db:
            await db.execute(
                "UPDATE image_groups SET status = 'failed', annotation = ? WHERE id = ?",
                (f"识别失败: {str(e)[:200]}", group_id),
            )
            await db.execute(
                "UPDATE account_images SET status = 'failed' WHERE group_id = ?",
                (group_id,),
            )
            await db.commit()


async def list_groups(account_id: str, category: str | None = None) -> list[dict]:
    async with get_db() as db:
        if category:
            async with db.execute(
                "SELECT * FROM image_groups WHERE account_id = ? AND category = ? ORDER BY created_at DESC",
                (account_id, category),
            ) as cur:
                groups = [dict(r) for r in await cur.fetchall()]
        else:
            async with db.execute(
                "SELECT * FROM image_groups WHERE account_id = ? ORDER BY created_at DESC",
                (account_id,),
            ) as cur:
                groups = [dict(r) for r in await cur.fetchall()]

    for g in groups:
        async with get_db() as db:
            async with db.execute(
                "SELECT id, file_path, original_name, annotation, status FROM account_images WHERE group_id = ? ORDER BY id",
                (g["id"],),
            ) as cur:
                g["images"] = [dict(r) for r in await cur.fetchall()]
    return groups


async def get_group(group_id: int) -> dict | None:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM image_groups WHERE id = ?", (group_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    g = dict(row)
    async with get_db() as db:
        async with db.execute(
            "SELECT id, file_path, original_name, annotation, status FROM account_images WHERE group_id = ? ORDER BY id",
            (group_id,),
        ) as cur:
            g["images"] = [dict(r) for r in await cur.fetchall()]
    return g


async def delete_group(group_id: int) -> bool:
    group = await get_group(group_id)
    if not group:
        return False

    for img in group.get("images", []):
        cos_url: str = img["file_path"]
        if cos_url.startswith("https://") and ".cos." in cos_url:
            try:
                from .cos_service import delete_object

                parts = cos_url.split(".myqcloud.com/", 1)
                if len(parts) == 2:
                    await delete_object(parts[1])
            except Exception as e:
                logger.warning(f"删除 COS 文件失败: {e}")

    async with get_db() as db:
        await db.execute("DELETE FROM account_images WHERE group_id = ?", (group_id,))
        cur = await db.execute("DELETE FROM image_groups WHERE id = ?", (group_id,))
        await db.commit()
    return cur.rowcount > 0


async def retry_group_vision(group_id: int) -> bool:
    group = await get_group(group_id)
    if not group:
        return False

    async with get_db() as db:
        await db.execute(
            "UPDATE account_images SET status = 'pending', annotation = '' WHERE group_id = ?",
            (group_id,),
        )
        await db.execute(
            "UPDATE image_groups SET status = 'pending', annotation = '' WHERE id = ?",
            (group_id,),
        )
        await db.commit()

    asyncio.create_task(
        _run_group_vision(group_id, group["category"], group.get("user_prompt", ""))
    )
    return True


async def get_categorized_groups(account_id: str) -> dict[str, list[dict]]:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM image_groups WHERE account_id = ? AND status = 'done' "
            "ORDER BY category, created_at DESC",
            (account_id,),
        ) as cur:
            groups = [dict(r) for r in await cur.fetchall()]

    for g in groups:
        async with get_db() as db:
            async with db.execute(
                "SELECT id, file_path, original_name, annotation FROM account_images "
                "WHERE group_id = ? AND status = 'done' ORDER BY id",
                (g["id"],),
            ) as cur:
                g["images"] = [dict(r) for r in await cur.fetchall()]

    result: dict[str, list[dict]] = {}
    for g in groups:
        cat = g["category"] or "style"
        if cat not in result:
            result[cat] = []
        result[cat].append(
            {
                "id": g["id"],
                "annotation": g["annotation"],
                "image_count": len(g["images"]),
                "images": [
                    {
                        "id": img["id"],
                        "name": img["original_name"],
                        "url": img["file_path"],
                    }
                    for img in g["images"]
                ],
            }
        )
    return result


async def get_groups_by_ids(group_ids: list[int], account_id: str = "") -> list[dict]:
    if not group_ids:
        return []
    placeholders = ",".join("?" for _ in group_ids)
    async with get_db() as db:
        if account_id:
            async with db.execute(
                f"SELECT * FROM image_groups WHERE id IN ({placeholders}) AND account_id = ? AND status = 'done'",
                group_ids + [account_id],
            ) as cur:
                groups = [dict(r) for r in await cur.fetchall()]
        else:
            async with db.execute(
                f"SELECT * FROM image_groups WHERE id IN ({placeholders}) AND status = 'done'",
                group_ids,
            ) as cur:
                groups = [dict(r) for r in await cur.fetchall()]

    for g in groups:
        async with get_db() as db:
            async with db.execute(
                "SELECT id, file_path, original_name, annotation, category FROM account_images "
                "WHERE group_id = ? AND status = 'done' ORDER BY id",
                (g["id"],),
            ) as cur:
                g["images"] = [dict(r) for r in await cur.fetchall()]
    return groups
