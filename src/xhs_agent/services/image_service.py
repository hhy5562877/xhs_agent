import asyncio
import logging
import httpx
from typing import Literal
from ..config import get_setting
from ..api.schemas import GeneratedImage

logger = logging.getLogger("xhs_agent")

ImageStyle = Literal["photo", "poster"]

# aspect_ratio → size 映射（即梦4 doubao-seedream-4-5-251128 支持的尺寸，使用 2K 规格）
# 参考: https://www.volcengine.com/docs/82379/1541523
_RATIO_TO_SIZE: dict[str, str] = {
    "1:1": "2048x2048",
    "4:3": "2304x1728",
    "3:4": "1728x2304",
    "16:9": "2560x1440",
    "9:16": "1440x2560",
    "3:2": "2496x1664",
    "2:3": "1664x2496",
    "21:9": "3024x1296",
}

# 照片风格前缀：手机误拍感快照，保留现有高质量提示词风格
_PHOTO_STYLE_PREFIX = (
    "手机随手误拍风格，极度真实的生活快照，"
    "拍摄角度略微倾斜尴尬，主体偏移，背景杂乱，"
    "自然光局部轻微过曝，轻微手持抖动模糊感，"
    "轻微噪点，无滤镜无后期，真实粗粝的生活质感，"
)

# 海报风格前缀：高端商业海报，基于 Seedream 最佳实践
_POSTER_STYLE_PREFIX = (
    "高端商业海报设计风格，"
    "构图精准居中，视觉层次分明，主体突出，"
    "色彩饱和度高、对比强烈，配色和谐统一，"
    "光影质感细腻，背景简洁干净，"
    "整体风格现代简约，适合小红书平台传播，"
)


def _build_photo_prompt(prompt: str) -> str:
    # 若提示词已包含风格关键词，不重复添加前缀
    if any(kw in prompt for kw in ["手机随手误拍", "误拍风格", "生活快照", "手持抖动"]):
        return prompt
    return _PHOTO_STYLE_PREFIX + prompt


def _build_poster_prompt(prompt: str) -> str:
    # 若提示词已包含风格关键词，不重复添加前缀
    if any(kw in prompt for kw in ["海报设计风格", "商业海报", "构图精准"]):
        return prompt
    return _POSTER_STYLE_PREFIX + prompt


async def _call_image_api(prompt: str, size: str) -> GeneratedImage:
    """调用即梦4 API 生成单张图片"""
    base_url = await get_setting("image_api_base_url")
    api_key = await get_setting("image_api_key")
    model = await get_setting("image_model")

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            f"{base_url}/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "prompt": prompt,
                "n": 1,
                "response_format": "url",
                "size": size,
                "watermark": False,
            },
        )
        if not response.is_success:
            logger.error(f"图片生成失败 {response.status_code}: {response.text[:500]}")
        response.raise_for_status()

    raw = response.text
    if not raw.strip():
        logger.error(f"图片生成 API 返回空响应，prompt 前30字: {prompt[:30]}")
        return GeneratedImage()

    data = response.json()
    items = data.get("data", [])
    if not items:
        return GeneratedImage()
    item = items[0]
    return GeneratedImage(url=item.get("url"), b64_json=item.get("b64_json"))


async def generate_images(
    prompts: list[str],
    aspect_ratio: str = "3:4",
    styles: list[ImageStyle] | None = None,
) -> list[GeneratedImage]:
    """并发生成多张图片，每张独立调用 API，支持按风格路由提示词"""
    if not prompts:
        return []

    size = _RATIO_TO_SIZE.get(aspect_ratio)
    if not size:
        logger.warning(f"不支持的宽高比 {aspect_ratio!r}，使用默认 3:4")
        size = _RATIO_TO_SIZE["3:4"]

    # styles 长度不足时，默认补 photo
    if not styles:
        styles = ["photo"] * len(prompts)
    elif len(styles) < len(prompts):
        styles = list(styles) + ["photo"] * (len(prompts) - len(styles))

    built_prompts = [
        _build_poster_prompt(p) if s == "poster" else _build_photo_prompt(p)
        for p, s in zip(prompts, styles)
    ]

    tasks = [_call_image_api(p, size) for p in built_prompts]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    images: list[GeneratedImage] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"第{i + 1}张图片生成失败: {result}")
            images.append(GeneratedImage())
        else:
            images.append(result)

    return images


async def generate_image(
    prompt: str, aspect_ratio: str = "3:4", style: ImageStyle = "photo"
) -> GeneratedImage:
    """单张图片生成（兼容旧调用）"""
    images = await generate_images([prompt], aspect_ratio, [style])
    return images[0] if images else GeneratedImage()
