import json
import logging
import asyncio
import os
from datetime import datetime
from ..db import get_db
from ..services.text_service import generate_xhs_content
from ..services.image_service import generate_images
from ..services.upload_service import download_image_to_tmp, upload_image_note

logger = logging.getLogger("xhs_agent")


async def list_goals(account_id: str | None = None) -> list[dict]:
    async with get_db() as db:
        if account_id:
            async with db.execute(
                "SELECT * FROM operation_goals WHERE account_id = ? ORDER BY created_at DESC",
                (account_id,),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM operation_goals ORDER BY created_at DESC"
            ) as cur:
                rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_goal(goal_id: int) -> dict | None:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM operation_goals WHERE id = ?", (goal_id,)
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def create_goal(
    account_id: str, title: str, description: str, style: str, post_freq: int
) -> dict:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO operation_goals (account_id, title, description, style, post_freq, active, created_at) VALUES (?,?,?,?,?,1,?)",
            (account_id, title, description, style, post_freq, created_at),
        )
        await db.commit()
        goal_id = cur.lastrowid
    return {
        "id": goal_id,
        "account_id": account_id,
        "title": title,
        "description": description,
        "style": style,
        "post_freq": post_freq,
        "active": 1,
        "created_at": created_at,
    }


async def toggle_goal(goal_id: int, active: bool) -> bool:
    async with get_db() as db:
        cur = await db.execute(
            "UPDATE operation_goals SET active = ? WHERE id = ?", (int(active), goal_id)
        )
        await db.commit()
    return cur.rowcount > 0


async def update_goal(
    goal_id: int,
    title: str,
    description: str,
    style: str,
    post_freq: int,
    account_id: str,
) -> bool:
    async with get_db() as db:
        cur = await db.execute(
            "UPDATE operation_goals SET title=?, description=?, style=?, post_freq=?, account_id=? WHERE id=?",
            (title, description, style, post_freq, account_id, goal_id),
        )
        # 检查第一个更新是否成功
        if cur.rowcount == 0:
            await db.commit()
            return False
        # 同步更新该目标下所有 pending 排期的账号
        await db.execute(
            "UPDATE scheduled_posts SET account_id=? WHERE goal_id=? AND status='pending'",
            (account_id, goal_id),
        )
        await db.commit()
    return True


async def delete_goal(goal_id: int) -> bool:
    async with get_db() as db:
        cur = await db.execute("DELETE FROM operation_goals WHERE id = ?", (goal_id,))
        await db.commit()
    return cur.rowcount > 0


async def delete_pending_posts(goal_id: int) -> int:
    """删除目标下所有 pending 状态的排期（重新规划前调用）"""
    async with get_db() as db:
        cur = await db.execute(
            "DELETE FROM scheduled_posts WHERE goal_id = ? AND status = 'pending'",
            (goal_id,),
        )
        await db.commit()
    return cur.rowcount


async def create_scheduled_post(
    goal_id: int,
    account_id: str,
    topic: str,
    style: str,
    aspect_ratio: str,
    image_count: int,
    scheduled_at: str,
) -> dict:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    async with get_db() as db:
        cur = await db.execute(
            """INSERT INTO scheduled_posts
               (goal_id, account_id, topic, style, aspect_ratio, image_count, scheduled_at, status, created_at)
               VALUES (?,?,?,?,?,?,?,'pending',?)""",
            (
                goal_id,
                account_id,
                topic,
                style,
                aspect_ratio,
                image_count,
                scheduled_at,
                created_at,
            ),
        )
        await db.commit()
        post_id = cur.lastrowid
    return {
        "id": post_id,
        "topic": topic,
        "scheduled_at": scheduled_at,
        "status": "pending",
    }


async def list_scheduled_posts(goal_id: int | None = None) -> list[dict]:
    async with get_db() as db:
        if goal_id:
            async with db.execute(
                "SELECT * FROM scheduled_posts WHERE goal_id = ? ORDER BY scheduled_at ASC",
                (goal_id,),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM scheduled_posts ORDER BY scheduled_at ASC"
            ) as cur:
                rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def execute_scheduled_post(post_id: int) -> None:
    """执行一条定时发布任务"""
    from ..services.notification_service import get_notification_service

    notification = get_notification_service()

    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM scheduled_posts WHERE id = ?", (post_id,)
        ) as cur:
            post = await cur.fetchone()
        if not post or post["status"] != "pending":
            return
        await db.execute(
            "UPDATE scheduled_posts SET status = 'running' WHERE id = ?", (post_id,)
        )
        await db.commit()

    tmp_paths: list[str] = []
    try:
        content = await generate_xhs_content(
            post["topic"], post["style"], post["image_count"]
        )
        prompts = content.image_prompts[: post["image_count"]]
        styles = (
            content.image_styles[: post["image_count"]]
            if content.image_styles
            else None
        )
        images = await generate_images(
            prompts, aspect_ratio=post["aspect_ratio"], styles=styles
        )
        image_urls = [img.url or "" for img in images if img.url]
        images_json = json.dumps(
            [{"url": img.url, "b64_json": img.b64_json} for img in images]
        )

        from ..services.account_service import get_cookie

        account_id = post["account_id"]
        cookie = await get_cookie(account_id)
        logger.info(
            f"定时任务 #{post_id} 使用账号 account_id={account_id!r}, cookie={'有' if cookie else '无'}"
        )
        if not cookie:
            raise ValueError(f"账号 Cookie 不存在 (account_id={account_id!r})")

        tmp_paths = await asyncio.gather(
            *[download_image_to_tmp(u) for u in image_urls if u]
        )
        desc = content.body + "\n\n" + " ".join(f"#{t}" for t in content.hashtags)
        result = await asyncio.to_thread(
            upload_image_note,
            cookie,
            content.title,
            desc,
            list(tmp_paths),
            content.hashtags,
        )
        note_id = result.get("note_id") if isinstance(result, dict) else None

        async with get_db() as db:
            await db.execute(
                """UPDATE scheduled_posts SET status='done', result_title=?, result_body=?,
                   result_images=?, note_id=? WHERE id=?""",
                (content.title, content.body, images_json, note_id, post_id),
            )
            await db.commit()
        logger.info(f"定时任务 #{post_id} 发布成功: {content.title}")

        await notification.send_success_notification(
            "笔记发布成功",
            f"任务 ID: {post_id}\n标题: {content.title}\n话题: {post['topic']}\n账号: {account_id}",
        )

    except Exception as e:
        import traceback

        logger.error(f"定时任务 #{post_id} 失败: {e}\n{traceback.format_exc()}")
        async with get_db() as db:
            await db.execute(
                "UPDATE scheduled_posts SET status='failed', error=? WHERE id=?",
                (str(e), post_id),
            )
            await db.commit()

        await notification.send_error_notification(
            "笔记发布失败",
            f"任务 ID: {post_id}\n话题: {post['topic']}\n错误: {str(e)[:200]}",
        )
    finally:
        for p in tmp_paths:
            try:
                os.unlink(p)
            except Exception:
                pass
