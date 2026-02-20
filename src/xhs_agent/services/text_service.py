import json
import logging
import httpx
from ..config import get_setting
from ..api.schemas import XHSContent

logger = logging.getLogger("xhs_agent")

SYSTEM_PROMPT = """你是一位专业的小红书内容创作者，擅长创作爆款图文笔记。
你的任务是根据用户给出的主题，生成一篇完整的小红书笔记内容。

输出必须是严格的 JSON 格式，包含以下字段：
{
  "title": "吸引眼球的标题（含emoji，15字以内）",
  "body": "正文内容（含emoji，200-400字，分段落，有感染力）",
  "hashtags": ["话题标签1", "话题标签2", ...],
  "image_prompts": ["图片1的中文提示词", "图片2的中文提示词", ...],
  "image_style": "photo"
}

【第一步：为整篇笔记决定统一视觉风格 image_style】
一篇笔记只能有一种视觉风格，所有图片必须保持统一，不允许混用。
根据内容调性选择：
- "photo"：生活记录、探店、穿搭、美食、旅行、日常分享等真实场景 → 选 photo
- "poster"：活动推广、产品种草、励志内容、品牌宣传、知识干货等需要视觉冲击力的场景 → 选 poster

【第二步：根据统一风格生成所有图片的 image_prompts】
所有图片提示词必须与 image_style 保持一致的视觉风格，每条约100字，全部用中文编写，严禁出现任何英文单词、字母、拼音。

如果 image_style 为 "photo"（真实照片风格）：
每张图片提示词必须体现以下特征：
- 手机随手误拍感，拍摄角度略微倾斜尴尬，主体偏移，背景杂乱
- 自然光局部轻微过曝，或室内光线昏暗不均
- 轻微手持抖动模糊感，轻微噪点，无滤镜无后期
- 真实粗粝的生活质感，无任何刻意构图感
- 每张图片描述不同的具体场景，但整体风格统一

photo 提示词示例：
"手机随手误拍风格，极度普通的生活快照，木质书桌一角，桌面散落着几张写满字迹的复习笔记和一支黑色圆珠笔，椅背局部入镜，拍摄角度略微倾斜尴尬，窗边自然光从侧面照入导致局部轻微过曝，画面有轻微手持抖动模糊感，轻微噪点，无滤镜无后期，真实生活场景质感，无任何文字"

如果 image_style 为 "poster"（海报设计风格）：
每张图片提示词必须体现以下特征：
- 高端商业海报设计感，构图精准居中，视觉层次分明
- 色彩饱和度高、对比强烈，配色和谐统一
- 光影质感细腻，背景简洁干净
- 整体风格现代简约，适合小红书平台传播
- 每张图片描述不同的视觉主题，但整体设计语言统一

poster 提示词示例：
"高端商业海报设计风格，主体居中突出，背景采用渐变深色调，色彩饱和度高对比强烈，光影质感细腻，整体构图精准视觉层次分明，现代简约风格，适合小红书平台传播，无任何文字"

【文字规则】默认不出现任何文字。如场景中自然存在文字，必须全部是中文，严禁出现英文、字母、拼音。

注意：
- 标题要有吸引力，可以用数字、疑问句或感叹句
- 正文要真实、有温度，像真人分享
- 话题标签要精准，覆盖核心关键词
- image_prompts 数量与请求的图片数量相同
- 严禁在提示词中出现任何英文单词、字母或拼音
"""


async def generate_xhs_content(topic: str, style: str, image_count: int) -> XHSContent:
    user_prompt = f"主题：{topic}\n风格：{style}\n需要生成 {image_count} 张配图的提示词"

    base_url = await get_setting("siliconflow_base_url")
    api_key = await get_setting("siliconflow_api_key")
    model = await get_setting("text_model")

    logger.debug(
        f"[TextService] 请求参数: model={model!r}, topic={topic!r}, style={style!r}, image_count={image_count}"
    )
    logger.debug(f"[TextService] system_prompt:\n{SYSTEM_PROMPT}")
    logger.debug(f"[TextService] user_prompt:\n{user_prompt}")

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
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.8,
                "max_tokens": 2048,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()

    data = response.json()
    raw_content = data["choices"][0]["message"]["content"]
    logger.debug(f"[TextService] LLM 原始响应: {raw_content}")

    parsed = json.loads(raw_content)

    # image_style 为整篇笔记统一风格（单值），兼容旧格式 image_styles 列表
    raw_style = parsed.get("image_style") or (
        parsed.get("image_styles", ["photo"])[0]
        if parsed.get("image_styles")
        else "photo"
    )
    unified_style = raw_style if raw_style in ("photo", "poster") else "photo"

    return XHSContent(
        title=parsed["title"],
        body=parsed["body"],
        hashtags=parsed.get("hashtags", []),
        image_prompts=parsed.get("image_prompts", []),
        image_styles=[unified_style],  # 只存一个统一风格
    )
