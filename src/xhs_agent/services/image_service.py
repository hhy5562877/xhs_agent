import httpx
from ..config import settings
from ..api.schemas import GeneratedImage


async def generate_image(prompt: str, aspect_ratio: str = "3:4") -> GeneratedImage:
    """调用 nano-banana API 生成图片"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.image_api_base_url}/images/generations",
            headers={
                "Authorization": f"Bearer {settings.image_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.image_model,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "response_format": "url",
            },
        )
        response.raise_for_status()

    data = response.json()
    image_data = data["data"][0]
    return GeneratedImage(
        url=image_data.get("url"),
        b64_json=image_data.get("b64_json"),
    )


async def generate_images(prompts: list[str], aspect_ratio: str = "3:4") -> list[GeneratedImage]:
    """并发生成多张图片"""
    import asyncio
    tasks = [generate_image(prompt, aspect_ratio) for prompt in prompts]
    return await asyncio.gather(*tasks)
