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
  "image_styles": ["photo", "poster", ...]
}

【第一步：为每张图片决定风格 image_styles】
根据内容调性为每张图片独立选择风格，与 image_prompts 一一对应：
- "photo"：生活记录、探店、穿搭、美食、旅行、日常分享等真实场景 → 选 photo
- "poster"：活动推广、产品种草、励志内容、品牌宣传、知识干货等需要视觉冲击力的场景 → 选 poster

【第二步：根据风格生成对应的 image_prompts】
每条提示词必须全部用中文编写，严禁出现任何英文单词、字母、拼音，约100字。

如果该图片风格为 "photo"（真实照片风格）：
提示词必须体现以下特征：
- 手机随手误拍感，拍摄角度略微倾斜尴尬，主体偏移，背景杂乱
- 自然光局部轻微过曝，或室内光线昏暗不均
- 轻微手持抖动模糊感，轻微噪点，无滤镜无后期
- 真实粗粝的生活质感，无任何刻意构图感

photo 提示词示例：
"手机随手误拍风格，极度普通的生活快照，木质书桌一角，桌面散落着几张写满字迹的复习笔记和一支黑色圆珠笔，椅背局部入镜，拍摄角度略微倾斜尴尬，窗边自然光从侧面照入导致局部轻微过曝，画面有轻微手持抖动模糊感，轻微噪点，无滤镜无后期，真实生活场景质感，无任何文字"

如果该图片风格为 "poster"（海报设计风格）：
提示词必须体现以下特征：
- 高端商业海报设计感，构图精准居中，视觉层次分明
- 色彩饱和度高、对比强烈，配色和谐统一
- 光影质感细腻，背景简洁干净
- 整体风格现代简约，适合小红书平台传播

poster 提示词示例：
"高端商业海报设计风格，主体居中突出，背景采用渐变深色调，色彩饱和度高对比强烈，光影质感细腻，整体构图精准视觉层次分明，现代简约风格，适合小红书平台传播，无任何文字"

【文字规则】默认不出现任何文字。如场景中自然存在文字，必须全部是中文，严禁出现英文、字母、拼音。

注意：
- 标题要有吸引力，可以用数字、疑问句或感叹句
- 正文要真实、有温度，像真人分享
- 话题标签要精准，覆盖核心关键词
- image_styles 和 image_prompts 必须一一对应，数量相同
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

    return XHSContent(
        title=parsed["title"],
        body=parsed["body"],
        hashtags=parsed.get("hashtags", []),
        image_prompts=parsed.get("image_prompts", []),
        image_styles=parsed.get("image_styles", []),
    )
