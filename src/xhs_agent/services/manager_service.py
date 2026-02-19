import json
import logging
import httpx
from datetime import datetime, timedelta
from ..config import settings

logger = logging.getLogger("xhs_agent")

MANAGER_SYSTEM_PROMPT = """你是一位专业的小红书运营总监，精通小红书平台算法和内容运营规律。

你的任务是根据用户给出的运营目标，制定一套科学的内容发布计划。

小红书运营核心规律：
1. 发布频率：新账号每天1-2篇，成熟账号每天1-3篇，避免连续发布间隔小于4小时
2. 最佳发布时间：
   - 早高峰：7:00-9:00（通勤时间）
   - 午休：12:00-13:30
   - 晚高峰：18:00-22:00（黄金时段，尤其20:00-21:00）
3. 内容节奏：干货/教程类 + 生活记录类 + 种草类 交替发布
4. 话题热度：结合当前热点，但核心内容要垂直
5. 图片数量：3-6张最佳，封面图最重要

输出必须是严格的 JSON 格式：
{
  "analysis": "运营策略分析（200字以内）",
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


async def plan_operation(goal_title: str, goal_desc: str, style: str, post_freq: int) -> dict:
    """调用总管 AI 分析运营目标，生成发布计划"""
    user_prompt = (
        f"运营目标：{goal_title}\n"
        f"详细描述：{goal_desc}\n"
        f"主要风格：{style}\n"
        f"每日发布频率：{post_freq} 篇\n"
        f"当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}（星期{['一','二','三','四','五','六','日'][datetime.now().weekday()]}）\n"
        "请制定未来7天的内容发布计划。"
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
    """计算实际发布时间"""
    base = datetime.now().replace(second=0, microsecond=0)
    target = base + timedelta(days=day_offset)
    target = target.replace(hour=hour, minute=minute)
    # 如果时间已过，顺延到明天同一时间
    if target <= datetime.now():
        target += timedelta(days=1)
    return target.strftime("%Y-%m-%d %H:%M")
