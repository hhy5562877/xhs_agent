import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from .goal_service import execute_scheduled_post, list_scheduled_posts

logger = logging.getLogger("xhs_agent")
scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")


def start_scheduler() -> None:
    scheduler.start()
    logger.info("定时调度器已启动")


async def reload_pending_jobs() -> None:
    """从数据库加载所有 pending 任务到调度器（服务重启恢复用）"""
    posts = await list_scheduled_posts()
    now = datetime.now()
    count = 0
    for post in posts:
        if post["status"] != "pending":
            continue
        try:
            run_time = datetime.strptime(post["scheduled_at"], "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        if run_time <= now:
            # 已过期，直接标记失败
            from ..db import get_db
            async with get_db() as db:
                await db.execute(
                    "UPDATE scheduled_posts SET status='failed', error='服务重启时任务已过期' WHERE id=?",
                    (post["id"],),
                )
                await db.commit()
            continue
        _add_job(post["id"], run_time)
        count += 1
    logger.info(f"恢复 {count} 个待执行定时任务")


def schedule_post(post_id: int, run_time: datetime) -> None:
    _add_job(post_id, run_time)
    logger.info(f"已调度任务 #{post_id} 于 {run_time.strftime('%Y-%m-%d %H:%M')}")


def _add_job(post_id: int, run_time: datetime) -> None:
    job_id = f"post_{post_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(
        _run_post,
        trigger=DateTrigger(run_date=run_time),
        args=[post_id],
        id=job_id,
        misfire_grace_time=300,
    )


async def _run_post(post_id: int) -> None:
    logger.info(f"开始执行定时任务 #{post_id}")
    await execute_scheduled_post(post_id)
