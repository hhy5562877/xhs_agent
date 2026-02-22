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


def _get_fail_stage(e: Exception) -> str:
    err = str(e).lower()
    tb = getattr(e, "__traceback__", None)
    frames = []
    while tb:
        frames.append(tb.tb_frame.f_code.co_filename + ":" + tb.tb_frame.f_code.co_name)
        tb = tb.tb_next
    frames_str = " ".join(frames)
    if "text_service" in frames_str or "generate_xhs_content" in frames_str:
        return "文本生成"
    if "prompt_agent" in frames_str or "build_image_prompts" in frames_str:
        return "提示词生成"
    if "image_service" in frames_str or "generate_image" in frames_str:
        return "图片生成"
    if "download_image" in frames_str or "ReadTimeout" in type(e).__name__:
        return "图片下载"
    if "upload_image_note" in frames_str or "upload_service" in frames_str:
        return "笔记上传"
    if "cookie" in err:
        return "账号Cookie"
    return "未知阶段"


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
        # 同步更新该目标下所有排期的账号（不限状态）
        await db.execute(
            "UPDATE scheduled_posts SET account_id=? WHERE goal_id=?",
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


async def delete_all_posts(goal_id: int) -> int:
    async with get_db() as db:
        cur = await db.execute(
            "DELETE FROM scheduled_posts WHERE goal_id = ?",
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
    ref_image_ids: str = "[]",
) -> dict:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    async with get_db() as db:
        cur = await db.execute(
            """INSERT INTO scheduled_posts
               (goal_id, account_id, topic, style, aspect_ratio, image_count, scheduled_at, ref_image_ids, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,'pending',?)""",
            (
                goal_id,
                account_id,
                topic,
                style,
                aspect_ratio,
                image_count,
                scheduled_at,
                ref_image_ids,
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
    from ..services.notification_service import get_notification_service
    from ..agent.prompt_agent import build_image_prompts

    notification = get_notification_service()

    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM scheduled_posts WHERE id = ?", (post_id,)
        ) as cur:
            post = await cur.fetchone()
        if not post or post["status"] != "pending":
            logger.debug(
                f"定时任务 #{post_id} 跳过: post={dict(post) if post else None}"
            )
            return
        await db.execute(
            "UPDATE scheduled_posts SET status = 'running' WHERE id = ?", (post_id,)
        )
        await db.commit()

    logger.info(
        f"定时任务 #{post_id} 开始执行: topic={post['topic']!r}, style={post['style']!r}, image_count={post['image_count']}"
    )

    tmp_paths: list[str] = []
    try:
        # 1. 加载参考图片组
        ref_images: list[dict] = []
        ref_image_urls: list[str] = []
        raw_ref_ids = post["ref_image_ids"] if "ref_image_ids" in post.keys() else "[]"
        try:
            ref_ids = json.loads(raw_ref_ids) if raw_ref_ids else []
        except (json.JSONDecodeError, TypeError):
            ref_ids = []
        if ref_ids:
            from ..services.account_image_service import get_groups_by_ids

            ref_groups = await get_groups_by_ids(ref_ids)
            for g in ref_groups:
                ref_images.append(
                    {
                        "category": g.get("category", "style"),
                        "original_name": f"图片组({len(g.get('images', []))}张)",
                        "annotation": g.get("annotation", ""),
                    }
                )
                for img in g.get("images", []):
                    url = img.get("file_path", "")
                    if url:
                        ref_image_urls.append(url)
            logger.info(
                f"定时任务 #{post_id} 加载 {len(ref_groups)} 组参考图片, {len(ref_image_urls)} 张参考图URL"
            )

        # 2. 生成文本内容（传入参考图标注影响风格判断）
        ref_annotations = ref_images if ref_images else None
        content = await generate_xhs_content(
            post["topic"],
            post["style"],
            post["image_count"],
            ref_annotations=ref_annotations,
        )
        logger.info(
            f"定时任务 #{post_id} 文本生成完成: title={content.title!r}, image_styles={content.image_styles}"
        )
        logger.debug(
            f"定时任务 #{post_id} 文本详情: body长度={len(content.body)}字, hashtags={content.hashtags}, image_prompts={content.image_prompts}"
        )

        prompts, styles = await build_image_prompts(
            topic=post["topic"],
            style=post["style"],
            content=content,
            image_count=post["image_count"],
            ref_images=ref_images if ref_images else None,
        )
        logger.info(f"定时任务 #{post_id} 提示词生成完成: styles={styles}")
        logger.debug(f"定时任务 #{post_id} 完整提示词: {prompts}")

        # 3. 生成图片
        images = await generate_images(
            prompts,
            aspect_ratio=post["aspect_ratio"],
            styles=styles,
            ref_image_urls=ref_image_urls if ref_image_urls else None,
        )
        failed = [
            i + 1 for i, img in enumerate(images) if not img.url and not img.b64_json
        ]
        if failed:
            raise ValueError(f"第 {failed} 张图片生成失败，取消上传")
        image_urls = [img.url or "" for img in images if img.url]
        images_json = json.dumps(
            [{"url": img.url, "b64_json": img.b64_json} for img in images]
        )
        logger.debug(f"定时任务 #{post_id} 图片生成完成: urls={image_urls}")

        from ..services.account_service import get_cookie

        account_id = post["account_id"]
        cookie = await get_cookie(account_id)
        logger.info(
            f"定时任务 #{post_id} 使用账号 account_id={account_id!r}, cookie={'有' if cookie else '无'}"
        )
        if not cookie:
            raise ValueError(f"账号 Cookie 不存在 (account_id={account_id!r})")

        # 4. 下载图片到临时文件
        tmp_paths = await asyncio.gather(
            *[download_image_to_tmp(u) for u in image_urls if u]
        )
        logger.debug(f"定时任务 #{post_id} 图片下载完成: tmp_paths={tmp_paths}")

        # 5. 上传笔记
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
        logger.debug(f"定时任务 #{post_id} 上传结果: {result}")

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
            f"任务 ID: {post_id}\n话题: {post['topic']}\n账号: {post['account_id']}\n失败阶段: {_get_fail_stage(e)}\n错误类型: {type(e).__name__}\n错误详情: {str(e)[:500]}",
        )
    finally:
        for p in tmp_paths:
            try:
                os.unlink(p)
            except Exception:
                pass
