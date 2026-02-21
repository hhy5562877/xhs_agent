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
  "image_style": "poster"
}

【第一步：为整篇笔记决定统一视觉风格 image_style】
一篇笔记只能有一种视觉风格，所有图片必须保持统一，不允许混用。

默认优先选择 "poster"（海报设计风格），因为小红书平台上精心设计的图文内容传播效果更好。
仅当主题明确属于以下真实场景类型时，才选择 "photo"：
- 真实探店体验（餐厅、咖啡馆、商场实地探访）
- 穿搭展示（真人穿搭、OOTD）
- 旅行实拍（景点打卡、旅途记录）
- 美食实拍（自己做的菜、餐厅菜品实拍）
- 日常生活记录（居家、通勤、宠物日常）

其他所有类型（知识干货、教程分享、产品种草、励志内容、商业科普、技能分享、品牌宣传、活动推广、清单盘点等）一律选择 "poster"。

如果用户提供了参考图片素材的标注信息，请重点参考：
- 标注中出现"插画""手绘""卡通""设计""海报""扁平""色彩饱和"等关键词 → 必须选 poster
- 标注中出现"实拍""真实照片""手机拍摄"等关键词 → 选 photo
- 参考图片的视觉风格是最重要的判断依据之一

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
提示词要求简洁，重点描述主题内容和画面构成，不要堆砌风格描述词。
- 无水印
- 鼓励在图片中包含与主题相关的中文文字，文字必须清晰准确无错别字
- 如果有参考图片素材，尽可能贴近参考图的视觉形式、排版和配色风格
- 每张图片描述不同的视觉主题，但整体风格统一

poster 提示词示例：
"海报设计风格，{主题相关的画面描述}，无水印，可包含中文标题文字"

【文字规则】
- photo 风格：默认不出现任何文字。如场景中自然存在文字，必须全部是中文，严禁出现英文、字母、拼音。
- poster 风格：鼓励包含与主题相关的中文文字（标题、关键词等），文字必须清晰准确无错别字，严禁出现英文、字母、拼音。

注意：
- 标题要有吸引力，可以用数字、疑问句或感叹句
- 正文要真实、有温度，像真人分享
- 话题标签要精准，覆盖核心关键词
- image_prompts 数量与请求的图片数量相同
- 严禁在提示词中出现任何英文单词、字母或拼音
"""


async def generate_xhs_content(
    topic: str,
    style: str,
    image_count: int,
    ref_annotations: list[dict] | None = None,
) -> XHSContent:
    user_prompt = f"主题：{topic}\n风格：{style}\n需要生成 {image_count} 张配图的提示词"

    if ref_annotations:
        user_prompt += "\n\n参考图片素材标注（请据此判断视觉风格）："
        for ann in ref_annotations:
            cat = ann.get("category", "style")
            text = ann.get("annotation", "")
            if text:
                user_prompt += f"\n  - [{cat}] {text}"

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
