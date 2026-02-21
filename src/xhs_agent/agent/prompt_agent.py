"""
图片提示词 Agent

标准 Agent 设计：
  LLM 根据主题/风格/图片数量，从预设模板库中选择最合适的模板，
  然后填充主题细节，返回最终的图片提示词列表。

调用链：
  xhs_agent.run()
    → prompt_agent.build_image_prompts()   ← 本模块
      → LLM 选模板 + 填充细节
    → image_service.generate_images()
"""

import json
import logging
import httpx
from ..config import get_setting
from ..api.schemas import XHSContent

logger = logging.getLogger("xhs_agent")

# ─────────────────────────────────────────────
# 预设提示词模板库
# 每个模板包含：style（图片风格）、name（模板名）、description（适用场景）、template（提示词骨架）
# ─────────────────────────────────────────────
PROMPT_TEMPLATES: dict[str, dict] = {
    # ── photo 类：真实照片风格 ──────────────────
    "photo_lifestyle": {
        "style": "photo",
        "name": "生活日常",
        "description": "适合日常生活记录、桌面物品、咖啡书本、居家场景，强调真实随手感",
        "template": (
            "手机随手误拍风格，极度真实的生活快照，{scene_detail}，"
            "桌面或室内场景，物品自然散落，拍摄角度略微倾斜尴尬，主体偏移，"
            "窗边自然光从侧面照入导致局部轻微过曝，"
            "轻微手持抖动模糊感，轻微噪点，无滤镜无后期，"
            "真实粗粝的生活质感，无任何刻意构图感，无任何文字"
        ),
    },
    "photo_food": {
        "style": "photo",
        "name": "美食探店",
        "description": "适合餐厅探店、菜品特写、咖啡甜品、街边小吃，强调食物真实感和环境氛围",
        "template": (
            "手机随手误拍风格，真实探店快照，{scene_detail}，"
            "餐桌或吧台场景，餐具自然摆放，背景有餐厅环境虚化，"
            "暖色调室内灯光，局部轻微过曝，"
            "轻微手持抖动，画面略微倾斜，无滤镜无后期，"
            "真实的食物质感和色泽，无任何文字"
        ),
    },
    "photo_outdoor": {
        "style": "photo",
        "name": "户外街拍",
        "description": "适合旅行打卡、街头场景、户外活动、城市探索，强调真实户外氛围",
        "template": (
            "手机随手误拍风格，真实户外快照，{scene_detail}，"
            "户外自然光线，背景有街道或自然环境，人物或主体略微偏移，"
            "阳光直射导致局部高光溢出，轻微运动模糊，"
            "画面略微倾斜，轻微噪点，无滤镜无后期，"
            "真实的户外氛围和光线质感，无任何文字"
        ),
    },
    "photo_study": {
        "style": "photo",
        "name": "学习备考",
        "description": "适合学习打卡、备考记录、书桌笔记、教材资料，强调学习氛围的真实感",
        "template": (
            "手机随手误拍风格，真实学习场景快照，{scene_detail}，"
            "书桌场景，笔记本、教材、文具自然散落，"
            "台灯或窗边自然光，局部轻微过曝，"
            "拍摄角度略微倾斜，轻微手持抖动，轻微噪点，无滤镜无后期，"
            "真实备考氛围，无任何文字"
        ),
    },
    # ── poster 类：海报设计风格 ─────────────────
    "poster_product": {
        "style": "poster",
        "name": "产品种草",
        "description": "适合产品推荐、好物分享、美妆护肤、数码配件",
        "template": (
            "海报设计风格，{scene_detail}，产品主体突出，无水印，可包含中文标题文字"
        ),
    },
    "poster_knowledge": {
        "style": "poster",
        "name": "知识干货",
        "description": "适合知识分享、技能教程、干货总结、信息图表",
        "template": (
            "海报设计风格，{scene_detail}，信息图表排版，无水印，可包含中文标题文字"
        ),
    },
    "poster_motivation": {
        "style": "poster",
        "name": "励志激励",
        "description": "适合励志内容、正能量分享、目标打卡、成长记录",
        "template": (
            "海报设计风格，{scene_detail}，视觉冲击力强，无水印，可包含中文标题文字"
        ),
    },
    "poster_event": {
        "style": "poster",
        "name": "活动推广",
        "description": "适合节日活动、品牌推广、限时优惠、打卡挑战",
        "template": (
            "海报设计风格，{scene_detail}，氛围感强，无水印，可包含中文标题文字"
        ),
    },
}

# ─────────────────────────────────────────────
# Agent System Prompt
# ─────────────────────────────────────────────
_AGENT_SYSTEM_PROMPT = """你是一位专业的图片提示词工程师，专门为小红书图文笔记生成高质量的图片提示词。

你的任务：
1. 根据笔记主题、风格和每张图片的用途，从可用模板中选择最合适的模板
2. 将模板中的 {scene_detail} 替换为与主题高度相关的具体场景描述（30-50字）
3. 返回最终的提示词列表

可用模板列表（JSON格式）：
{templates_json}

输出必须是严格的 JSON 格式：
{
  "selections": [
    {
      "template_key": "模板key",
      "scene_detail": "具体场景描述，30-50字，全部中文，无英文无拼音",
      "final_prompt": "完整的最终提示词（模板填充后的结果）"
    },
    ...
  ]
}

规则：
- scene_detail 必须全部用中文，严禁出现任何英文单词、字母、拼音
- 每张图片选择不同的模板（避免重复）
- 根据图片在笔记中的位置和用途选择最合适的模板
- final_prompt 是将 scene_detail 填入模板后的完整提示词
"""


async def build_image_prompts(
    topic: str,
    style: str,
    content: XHSContent,
    image_count: int,
    ref_images: list[dict] | None = None,
) -> tuple[list[str], list[str]]:
    # 取整篇笔记的统一风格（image_styles 列表中只有一个值）
    unified_style = content.image_styles[0] if content.image_styles else "photo"
    if unified_style not in ("photo", "poster"):
        unified_style = "photo"

    # 只加载与统一风格匹配的模板
    filtered_templates = {
        k: {
            "name": v["name"],
            "description": v["description"],
            "style": v["style"],
            "template": v["template"],
        }
        for k, v in PROMPT_TEMPLATES.items()
        if v["style"] == unified_style
    }

    templates_json = json.dumps(filtered_templates, ensure_ascii=False, indent=2)
    system_prompt = _AGENT_SYSTEM_PROMPT.replace("{templates_json}", templates_json)

    user_prompt = (
        f"笔记主题：{topic}\n"
        f"内容风格：{style}\n"
        f"笔记标题：{content.title}\n"
        f"笔记正文摘要：{content.body[:100]}...\n"
        f"话题标签：{', '.join(content.hashtags[:5])}\n"
        f"需要生成图片数量：{image_count}\n"
        f"整篇笔记统一视觉风格：{unified_style}\n"
    )

    if ref_images:
        ref_lines = ["\n参考图片素材（请将这些参考图的视觉特征融入生成的提示词中）："]
        for img in ref_images:
            cat_label = img.get("category", "style")
            ref_lines.append(
                f"  - [{cat_label}] 《{img.get('original_name', '')}》: {img.get('annotation', '')}"
            )
        user_prompt += "\n".join(ref_lines) + "\n"

    user_prompt += "\n请为每张图片从上述同类模板中选择不同的子模板并填充场景细节，确保所有图片风格统一。"

    logger.debug(
        f"[PromptAgent] 开始选模板，主题={topic!r}，图片数={image_count}，统一风格={unified_style!r}"
    )
    logger.debug(
        f"[PromptAgent] 可用模板数={len(filtered_templates)}，模板keys={list(filtered_templates.keys())}"
    )

    base_url = await get_setting("siliconflow_base_url")
    api_key = await get_setting("siliconflow_api_key")
    model = await get_setting("text_model")

    logger.debug(f"[PromptAgent] system_prompt:\n{system_prompt}")
    logger.debug(f"[PromptAgent] user_prompt:\n{user_prompt}")

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
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 2048,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()

    data = response.json()
    raw_content = data["choices"][0]["message"]["content"]
    logger.debug(f"[PromptAgent] LLM 原始响应: {raw_content}")

    parsed = json.loads(raw_content)
    selections = parsed.get("selections", [])

    prompts: list[str] = []
    styles: list[str] = []

    for i, sel in enumerate(selections[:image_count]):
        template_key = sel.get("template_key", "")
        final_prompt = sel.get("final_prompt", "")

        logger.debug(
            f"[PromptAgent] 图片{i + 1}: 模板={template_key!r}，风格={unified_style!r}，提示词={final_prompt[:60]}..."
        )

        prompts.append(final_prompt)
        styles.append(unified_style)

    if len(prompts) < image_count:
        fallback_prompts = content.image_prompts
        for i in range(len(prompts), image_count):
            fallback = (
                fallback_prompts[i]
                if i < len(fallback_prompts)
                else f"{topic}相关场景，真实生活质感"
            )
            logger.warning(f"[PromptAgent] 图片{i + 1} 未获得模板结果，使用兜底提示词")
            prompts.append(fallback)
            styles.append(unified_style)

    logger.info(
        f"[PromptAgent] 完成，共生成 {len(prompts)} 条提示词，统一风格={unified_style!r}"
    )
    return prompts, styles
