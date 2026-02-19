import logging
import httpx
from ..config import settings
from ..api.schemas import GeneratedImage

logger = logging.getLogger("xhs_agent")

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


async def generate_images(
    prompts: list[str], aspect_ratio: str = "3:4"
) -> list[GeneratedImage]:
    """调用即梦4 API，一次请求生成多张图片"""
    if not prompts:
        return []

    count = len(prompts)
    size = _RATIO_TO_SIZE.get(aspect_ratio)
    if not size:
        logger.warning(f"不支持的宽高比 {aspect_ratio!r}，使用默认 3:4")
        size = _RATIO_TO_SIZE["3:4"]

    if count > 1:
        scenes = "\n".join(f"第{i + 1}张：{p}" for i, p in enumerate(prompts))
        combined_prompt = f"请生成{count}张图片，每张场景如下：\n{scenes}"
    else:
        combined_prompt = prompts[0]

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            f"{settings.image_api_base_url}/images/generations",
            headers={
                "Authorization": f"Bearer {settings.image_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.image_model,
                "prompt": combined_prompt,
                "n": count,
                "response_format": "url",
                "size": size,
                "watermark": False,
            },
        )
        if not response.is_success:
            logger.error(f"图片生成失败 {response.status_code}: {response.text[:500]}")
        response.raise_for_status()

    data = response.json()
    results = []
    for item in data.get("data", []):
        results.append(
            GeneratedImage(
                url=item.get("url"),
                b64_json=item.get("b64_json"),
            )
        )

    if len(results) < count:
        logger.warning(f"图片生成数量不足: 请求{count}张，实际返回{len(results)}张")

    return results


async def generate_image(prompt: str, aspect_ratio: str = "3:4") -> GeneratedImage:
    """单张图片生成（兼容旧调用）"""
    images = await generate_images([prompt], aspect_ratio)
    return images[0] if images else GeneratedImage()
