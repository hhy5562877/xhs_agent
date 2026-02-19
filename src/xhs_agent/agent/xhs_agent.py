from ..services.text_service import generate_xhs_content
from ..services.image_service import generate_images
from ..api.schemas import GenerateRequest, GenerateResponse


async def run(request: GenerateRequest) -> GenerateResponse:
    """编排文本生成 + 图片生成的完整流程"""
    # 1. 生成图文内容（含图片提示词）
    content = await generate_xhs_content(
        topic=request.topic,
        style=request.style,
        image_count=request.image_count,
    )

    # 2. 取实际需要的提示词数量
    prompts = content.image_prompts[: request.image_count]

    # 3. 并发生成图片
    images = await generate_images(prompts, aspect_ratio=request.aspect_ratio)

    return GenerateResponse(content=content, images=images)
