import json
import logging
import asyncio
import httpx
from datetime import datetime, timedelta
from ..config import settings

logger = logging.getLogger("xhs_agent")

MANAGER_SYSTEM_PROMPT = """你是一位专业的小红书运营总监，精通小红书平台算法和内容运营规律。

你的任务是根据用户给出的运营目标和账号近期数据，制定一套科学的内容发布计划。

小红书运营核心规律：
1. 发布频率：新账号每天1-2篇，成熟账号每天1-3篇，避免连续发布间隔小于4小时
2. 最佳发布时间：
   - 早高峰：7:00-9:00（通勤时间）
   - 午休：12:00-13:30
   - 晚高峰：18:00-22:00（黄金时段，尤其20:00-21:00）
3. 内容节奏：干货/教程类 + 生活记录类 + 种草类 交替发布
4. 话题热度：结合当前热点，但核心内容要垂直
5. 图片数量：3-6张最佳，封面图最重要
6. 数据分析：根据历史笔记的点赞/收藏/评论数据，判断哪类内容更受欢迎，优先复制爆款方向

输出必须是严格的 JSON 格式：
{
  "analysis": "运营策略分析（300字以内，结合账号历史数据给出具体建议）",
  "weekly_plan": [
    {
      "day_offset": 0,
      "hour": 20,
      "minute": 0,
      "topic": "具体内容主题",
      "style": "内容风格",
      "aspect_ratio": "3:4",
      "image_count": 3,
      "reason": "选择该主题和时间的原因"
    }
  ]
}

weekly_plan 包含未来7天的发布计划，每天1-2条，时间要符合最佳发布规律。
"""


async def fetch_account_stats(cookie: str) -> dict:
    """异步获取账号近期笔记统计数据"""
    try:
        stats, notes = await asyncio.gather(
            asyncio.to_thread(_get_stats, cookie),
            asyncio.to_thread(_get_recent_notes, cookie),
            return_exceptions=True,
        )
        return {
            "stats": stats if not isinstance(stats, Exception) else [],
            "recent_notes": notes if not isinstance(notes, Exception) else [],
        }
    except Exception as e:
        logger.warning(f"获取账号数据失败: {e}")
        return {"stats": [], "recent_notes": []}


def _get_stats(cookie: str) -> list:
    from ..services.upload_service import get_notes_statistics
    return get_notes_statistics(cookie, time=30)


def _get_recent_notes(cookie: str) -> list:
    from ..services.upload_service import get_user_recent_notes
    return get_user_recent_notes(cookie)


def _summarize_stats(account_data: dict) -> str:
    """将账号数据压缩为 AI 可读的摘要"""
    lines = []
    notes = account_data.get("recent_notes", [])
    if notes:
        lines.append(f"近期发布笔记数：{len(notes)}")
        # 取前5篇，展示互动数据
        for n in notes[:5]:
            info = n.get("interact_info", {})
            lines.append(
                f"- 《{n.get('display_title', '无标题')}》"
                f" 点赞:{info.get('liked_count','?')} 收藏:{info.get('collected_count','?')} 评论:{info.get('comment_count','?')}"
            )
    stats = account_data.get("stats", [])
    if isinstance(stats, list) and stats:
        lines.append(f"近30天笔记统计条数：{len(stats)}")
    return "\n".join(lines) if lines else "暂无历史数据"


async def plan_operation(
    goal_title: str,
    goal_desc: str,
    style: str,
    post_freq: int,
    cookie: str,
) -> dict:
    """调用总管 AI 分析运营目标 + 账号历史数据，生成发布计划"""
    # 并发获取账号数据
    account_data = await fetch_account_stats(cookie)
    stats_summary = _summarize_stats(account_data)

    user_prompt = (
        f"运营目标：{goal_title}\n"
        f"详细描述：{goal_desc}\n"
        f"主要风格：{style}\n"
        f"每日发布频率：{post_freq} 篇\n"
        f"当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}（星期{['一','二','三','四','五','六','日'][datetime.now().weekday()]}）\n\n"
        f"账号近期数据：\n{stats_summary}\n\n"
        "请结合以上数据，制定未来7天的内容发布计划。"
    )

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.image_api_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.image_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-5.2",
                "messages": [
                    {"role": "system", "content": MANAGER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 3000,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()

    data = response.json()
    raw = data["choices"][0]["message"]["content"]
    return json.loads(raw)


def calc_scheduled_time(day_offset: int, hour: int, minute: int) -> str:
    base = datetime.now().replace(second=0, microsecond=0)
    target = (base + timedelta(days=day_offset)).replace(hour=hour, minute=minute)
    if target <= datetime.now():
        target += timedelta(days=1)
    return target.strftime("%Y-%m-%d %H:%M")
