import logging

import httpx

from ..config import get_setting

logger = logging.getLogger("xhs_agent")

CATEGORY_PROMPTS: dict[str, str] = {
    "style": (
        "你是一位专业的小红书视觉分析师。请从【风格参考】角度整体描述这组图片：\n"
        "1. 整体视觉调性（色调、光线、氛围）\n"
        "2. 构图方式和排版特点\n"
        "3. 滤镜/后期风格倾向\n"
        "4. 适合的小红书内容方向\n"
        "请用中文回答，控制在 300 字以内。"
    ),
    "person": (
        "你是一位专业的小红书视觉分析师。请从【人物形象】角度整体描述这组图片：\n"
        "1. 人物/角色的外貌特征（发型、妆容、体态）\n"
        "2. 穿着风格和配饰\n"
        "3. 表情和姿态传达的气质\n"
        "4. 如果是宠物/IP角色，描述其品种、毛色、特征\n"
        "请用中文回答，控制在 300 字以内。"
    ),
    "product": (
        "你是一位专业的小红书视觉分析师。请从【产品素材】角度整体描述这组图片：\n"
        "1. 产品名称/类型和外观特征\n"
        "2. 包装设计、颜色、材质\n"
        "3. 产品摆放方式和拍摄角度\n"
        "4. 产品传达的品质感和定位\n"
        "请用中文回答，控制在 300 字以内。"
    ),
    "scene": (
        "你是一位专业的小红书视觉分析师。请从【场景环境】角度整体描述这组图片：\n"
        "1. 场景类型（室内/室外、具体地点）\n"
        "2. 空间布局和装饰风格\n"
        "3. 光线条件和色彩氛围\n"
        "4. 场景传达的情绪和适合的拍摄主题\n"
        "请用中文回答，控制在 300 字以内。"
    ),
    "brand": (
        "你是一位专业的小红书视觉分析师。请从【品牌元素】角度整体描述这组图片：\n"
        "1. Logo 设计特征（字体、图形、颜色）\n"
        "2. 品牌主色调和辅助色\n"
        "3. 视觉规范特点（排版风格、设计语言）\n"
        "4. 品牌传达的调性和定位\n"
        "请用中文回答，控制在 300 字以内。"
    ),
}

_DEFAULT_PROMPT = CATEGORY_PROMPTS["style"]


async def analyze_image_group(
    image_urls: list[str],
    category: str = "style",
    user_prompt: str = "",
) -> str:
    base_url = await get_setting("siliconflow_base_url")
    api_key = await get_setting("siliconflow_api_key")
    model = await get_setting("vision_model")

    prompt = CATEGORY_PROMPTS.get(category, _DEFAULT_PROMPT)
    if len(image_urls) == 1:
        prompt = prompt.replace("这组图片", "这张图片")
    if user_prompt.strip():
        prompt += f"\n\n用户补充说明：{user_prompt.strip()}"

    content_parts: list[dict] = [{"type": "text", "text": prompt}]
    for url in image_urls:
        content_parts.append({"type": "image_url", "image_url": {"url": url}})

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content_parts}],
        "max_tokens": 1500,
        "temperature": 0.7,
    }

    logger.debug(
        f"[VisionService] model={model!r}, category={category!r}, images={len(image_urls)}"
    )

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    result = data["choices"][0]["message"]["content"]
    logger.info(
        f"[VisionService] 组识别完成 [{category}] {len(image_urls)}张: {result[:80]}..."
    )
    return result
