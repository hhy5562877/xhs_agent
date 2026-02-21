import json
import logging
import asyncio
import httpx
from datetime import datetime, timedelta
from ..config import get_setting

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

如果提供了参考图片素材，你需要根据每条内容的主题，从素材库中选择最合适的参考图片组。
每组图片是一个整体（如一套模板、一组产品图），选中后整组都会用于该条内容的生图参考。
选择时请注意：
- 风格参考组：选择与该条内容视觉调性匹配的
- 人物形象组：需要保持人物一致性的内容必选
- 产品素材组：涉及产品推广的内容必选
- 场景环境组：选择与内容场景匹配的
- 品牌元素组：需要品牌露出的内容必选
- 每条内容可选 0-3 个参考组，不必每条都选

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
      "reason": "选择该主题和时间的原因",
      "ref_images": [
        {"group_id": 1, "usage": "说明这组参考图在本条内容中的用途"}
      ]
    }
  ]
}

weekly_plan 包含未来7天的发布计划，每天1-2条，时间要符合最佳发布规律。
ref_images 为可选字段，如果没有合适的参考图片可以留空数组 []。
"""


async def fetch_account_stats(cookie: str, user_id: str = "") -> dict:
    """异步获取账号近期笔记统计数据"""
    try:
        stats, notes = await asyncio.gather(
            asyncio.to_thread(_get_stats, cookie),
            asyncio.to_thread(_get_recent_notes, cookie, user_id),
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


def _get_recent_notes(cookie: str, user_id: str = "") -> list:
    from ..services.upload_service import get_user_recent_notes

    return get_user_recent_notes(cookie, user_id=user_id)


def _summarize_stats(account_data: dict) -> str:
    """将账号数据压缩为 AI 可读的摘要"""
    lines = []
    notes = account_data.get("recent_notes", [])
    if notes:
        lines.append(f"近期发布笔记数：{len(notes)}")
        total_likes = sum(int(n.get("liked_count") or 0) for n in notes)
        total_collect = sum(int(n.get("collected_count") or 0) for n in notes)
        total_comment = sum(int(n.get("comment_count") or 0) for n in notes)
        lines.append(
            f"累计点赞：{total_likes}  收藏：{total_collect}  评论：{total_comment}"
        )
        sorted_notes = sorted(
            notes,
            key=lambda n: int(n.get("liked_count") or 0)
            + int(n.get("collected_count") or 0),
            reverse=True,
        )
        lines.append("表现最好的笔记（按点赞+收藏）：")
        for n in sorted_notes[:5]:
            lines.append(
                f"  - 《{n.get('title') or '无标题'}》[{n.get('type', '')}]"
                f" 点赞:{n.get('liked_count', 0)} 收藏:{n.get('collected_count', 0)}"
                f" 评论:{n.get('comment_count', 0)} 分享:{n.get('share_count', 0)}"
            )
        lines.append("所有笔记列表：")
        for n in notes:
            lines.append(
                f"  - 《{n.get('title') or '无标题'}》"
                f" 点赞:{n.get('liked_count', 0)} 收藏:{n.get('collected_count', 0)} 评论:{n.get('comment_count', 0)}"
            )
    else:
        lines.append(
            "注意：本次因小红书验证码拦截，无法获取历史笔记数据，请根据运营目标和平台规律制定计划。"
        )

    stats = account_data.get("stats", [])
    if isinstance(stats, list) and stats:
        lines.append(f"近30天笔记统计条数：{len(stats)}")
    return "\n".join(lines)


async def plan_operation(
    goal_title: str,
    goal_desc: str,
    style: str,
    post_freq: int,
    cookie: str,
    user_id: str = "",
    account_id: str = "",
) -> dict:
    """调用总管 AI 分析运营目标 + 账号历史数据，生成发布计划"""
    account_data = await fetch_account_stats(cookie, user_id=user_id)
    stats_summary = _summarize_stats(account_data)

    image_section = ""
    if account_id:
        from .account_image_service import get_categorized_groups, IMAGE_CATEGORIES

        categorized = await get_categorized_groups(account_id)
        if categorized:
            lines = [
                "\n\n账号参考图片素材库（按分类整理，每组可含多张图片，视觉 AI 标注）："
            ]
            for cat, groups in categorized.items():
                cat_info = IMAGE_CATEGORIES.get(cat, {"name": cat, "desc": ""})
                lines.append(f"\n【{cat_info['name']}】({cat_info['desc']})")
                for g in groups:
                    lines.append(
                        f"  - [组ID:{g['id']}] ({g['image_count']}张图): {g['annotation'][:200]}"
                    )
            lines.append(
                "\n请根据每条内容的主题，从以上素材库中选择合适的参考图片组，"
                "在 ref_images 字段中填写组 ID 和用途说明。一组图片会整体用于该条内容的生图参考。"
            )
            image_section = "\n".join(lines)

    user_prompt = (
        f"运营目标：{goal_title}\n"
        f"详细描述：{goal_desc}\n"
        f"主要风格：{style}\n"
        f"每日发布频率：{post_freq} 篇\n"
        f"当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}（星期{['一', '二', '三', '四', '五', '六', '日'][datetime.now().weekday()]}）\n\n"
        f"账号近期数据：\n{stats_summary}"
        f"{image_section}\n\n"
        "请结合以上数据，制定未来7天的内容发布计划。"
    )

    base_url = await get_setting("siliconflow_base_url")
    api_key = await get_setting("siliconflow_api_key")
    model = await get_setting("text_model")

    logger.debug(f"[ManagerAI] 请求参数: model={model!r}, goal={goal_title!r}")
    logger.debug(f"[ManagerAI] system_prompt:\n{MANAGER_SYSTEM_PROMPT}")
    logger.debug(f"[ManagerAI] user_prompt:\n{user_prompt}")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": MANAGER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 3000,
            },
        )
        response.raise_for_status()

    data = response.json()
    raw = data["choices"][0]["message"]["content"]
    logger.info(f"[Manager AI 输出]\n{raw}")
    # 提取 JSON 块（模型可能在 ```json ... ``` 中返回）
    import re

    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    json_str = match.group(1) if match else raw.strip()
    return json.loads(json_str)


def calc_scheduled_time(day_offset: int, hour: int, minute: int) -> str:
    base = datetime.now().replace(second=0, microsecond=0)
    target = (base + timedelta(days=day_offset)).replace(hour=hour, minute=minute)
    if target <= datetime.now():
        target += timedelta(days=1)
    return target.strftime("%Y-%m-%d %H:%M")
