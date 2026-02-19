import json
import httpx
from ..config import settings
from ..api.schemas import XHSContent

SYSTEM_PROMPT = """你是一位专业的小红书内容创作者，擅长创作爆款图文笔记。
你的任务是根据用户给出的主题，生成一篇完整的小红书笔记内容。

输出必须是严格的 JSON 格式，包含以下字段：
{
  "title": "吸引眼球的标题（含emoji，15字以内）",
  "body": "正文内容（含emoji，200-400字，分段落，有感染力）",
  "hashtags": ["话题标签1", "话题标签2", ...],
  "image_prompts": ["图片1的中文提示词", "图片2的中文提示词", ...]
}

【image_prompts 生成规则 - 非常重要】
每张图片提示词必须同时满足以下三点：

1. 真实感：描述真人用手机随手拍的生活照风格，自然光或暖光，轻微噪点，非完美构图，
   像素级真实，绝对不能有 AI 绘画感、插画感、过度磨皮感。

2. 网感：符合当下小红书/抖音流行的视觉风格，例如：
   - 咖啡/美食类：俯拍、奶油色系、木质桌面、手边有书或花
   - 穿搭类：街头抓拍感、胶片色调、背景虚化
   - 旅行类：黄金时刻光线、人物背影、地标元素
   - 护肤类：白色大理石台面、产品平铺、清晨窗边光

3. 中文文字入图：图片中必须包含中文文字元素，具体要求：
   - 用大号醒目字体在图片显眼位置写上与主题相关的中文短句（5-10字）
   - 可以是手写风格、霓虹灯字、贴纸风格、印刷体等
   - 文字内容要有网感，例如：「今天也是被治愈的一天」「这也太好喝了吧」「OMG 发现宝藏」
   - 文字颜色要与背景形成对比，清晰可读

提示词示例（咖啡主题）：
"真实手机拍摄风格，暖黄色调，木质桌面上一杯拿铁咖啡，奶泡上有拉花，旁边放着一本翻开的书，
自然窗边光，轻微噪点，图片右上角有白色手写体中文「今天也要好好生活」，贴纸风格装饰"

注意：
- 标题要有吸引力，可以用数字、疑问句或感叹句
- 正文要真实、有温度，像真人分享
- 话题标签要精准，覆盖核心关键词
"""


async def generate_xhs_content(topic: str, style: str, image_count: int) -> XHSContent:
    """调用 SiliconFlow API 生成小红书图文内容"""
    user_prompt = f"主题：{topic}\n风格：{style}\n需要生成 {image_count} 张配图的提示词"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.siliconflow_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.siliconflow_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.text_model,
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
    parsed = json.loads(raw_content)

    return XHSContent(
        title=parsed["title"],
        body=parsed["body"],
        hashtags=parsed.get("hashtags", []),
        image_prompts=parsed.get("image_prompts", []),
    )
