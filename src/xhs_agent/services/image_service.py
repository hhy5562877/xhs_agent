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
_POSTER_STYLE_PREFIX = "海报设计风格，无水印，"


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


async def _call_image_api(
    prompt: str,
    size: str,
    aspect_ratio: str,
    ref_image_urls: list[str] | None = None,
) -> GeneratedImage:
    base_url = await get_setting("image_api_base_url")
    api_key = await get_setting("image_api_key")
    model = await get_setting("image_model")

    logger.debug(
        f"[ImageAPI] 请求参数: model={model!r}, size={size!r}, aspect_ratio={aspect_ratio!r}, prompt长度={len(prompt)}字, 参考图={len(ref_image_urls or [])}张"
    )
    logger.debug(f"[ImageAPI] 完整提示词: {prompt}")

    is_nano_banana = model.startswith("nano-banana")
    if is_nano_banana:
        payload: dict = {
            "model": model,
            "prompt": prompt,
            "response_format": "url",
            "aspect_ratio": aspect_ratio,
        }
    else:
        payload = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "response_format": "url",
            "size": size,
            "watermark": False,
        }

    # 两种模型都支持 image 参数传入参考图数组
    if ref_image_urls:
        payload["image"] = ref_image_urls
        logger.debug(f"[ImageAPI] 传入参考图: {[u[:60] for u in ref_image_urls]}")

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            f"{base_url}/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
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
        logger.warning(f"[ImageAPI] 响应 data 为空: {data}")
        return GeneratedImage()
    item = items[0]
    url = item.get("url")
    logger.debug(f"[ImageAPI] 生成成功，url={url}")
    return GeneratedImage(url=url, b64_json=item.get("b64_json"))


async def generate_images(
    prompts: list[str],
    aspect_ratio: str = "3:4",
    styles: list[ImageStyle] | None = None,
    ref_image_urls: list[str] | None = None,
) -> list[GeneratedImage]:
    """生成多张图片。poster 风格串行生成（第1张结果作为后续参考图保持风格一致），photo 风格并发生成。"""
    if not prompts:
        return []

    size = _RATIO_TO_SIZE.get(aspect_ratio)
    if not size:
        logger.warning(f"不支持的宽高比 {aspect_ratio!r}，使用默认 3:4")
        size = _RATIO_TO_SIZE["3:4"]

    if not styles:
        styles = ["photo"] * len(prompts)
    elif len(styles) < len(prompts):
        styles = list(styles) + ["photo"] * (len(prompts) - len(styles))

    built_prompts = [
        _build_poster_prompt(p) if s == "poster" else _build_photo_prompt(p)
        for p, s in zip(prompts, styles)
    ]

    unified_style = styles[0] if styles else "photo"
    is_poster = unified_style == "poster"

    if is_poster:
        images: list[GeneratedImage] = []
        style_ref_urls = list(ref_image_urls) if ref_image_urls else []
        for i, prompt in enumerate(built_prompts):
            logger.info(f"[ImageAPI] poster 串行生成第 {i + 1}/{len(built_prompts)} 张")
            result = await _call_image_api(
                prompt,
                size,
                aspect_ratio,
                ref_image_urls=style_ref_urls if style_ref_urls else None,
            )
            images.append(result)
            if i == 0 and result.url:
                style_ref_urls.append(result.url)
                logger.debug(f"[ImageAPI] 第1张结果加入风格参考: {result.url}")
        return images
    else:
        tasks = [
            _call_image_api(p, size, aspect_ratio, ref_image_urls)
            for p in built_prompts
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        images = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"第{i + 1}张图片生成失败: {result}")
                images.append(GeneratedImage())
            else:
                images.append(result)
        return images


async def generate_image(
    prompt: str,
    aspect_ratio: str = "3:4",
    style: ImageStyle = "photo",
    ref_image_urls: list[str] | None = None,
) -> GeneratedImage:
    """单张图片生成（兼容旧调用）"""
    images = await generate_images([prompt], aspect_ratio, [style], ref_image_urls)
    return images[0] if images else GeneratedImage()
