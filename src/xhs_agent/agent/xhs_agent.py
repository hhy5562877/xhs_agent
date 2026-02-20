import logging
from ..services.text_service import generate_xhs_content
from ..services.image_service import generate_images
from ..api.schemas import GenerateRequest, GenerateResponse
from .prompt_agent import build_image_prompts

logger = logging.getLogger("xhs_agent")


async def run(request: GenerateRequest) -> GenerateResponse:
    logger.info(
        f"开始生成内容，主题={request.topic!r}，风格={request.style!r}，图片数={request.image_count}"
    )

    # 1. 生成图文内容（含风格决策 image_styles）
    content = await generate_xhs_content(
        topic=request.topic,
        style=request.style,
        image_count=request.image_count,
    )
    logger.info(
        f"文本生成完成，标题={content.title!r}，风格决策={content.image_styles}"
    )
    logger.debug(
        f"文本内容详情: body长度={len(content.body)}字，hashtags={content.hashtags}，原始image_prompts={content.image_prompts}"
    )

    # 2. PromptAgent：根据笔记内容选模板 + 填充细节，生成高质量提示词
    prompts, styles = await build_image_prompts(
        topic=request.topic,
        style=request.style,
        content=content,
        image_count=request.image_count,
    )
    logger.debug(f"PromptAgent 输出: prompts={prompts}，styles={styles}")

    # 3. 并发生成图片
    images = await generate_images(
        prompts, aspect_ratio=request.aspect_ratio, styles=styles
    )
    logger.info(
        f"图片生成完成，共{len(images)}张，成功={sum(1 for img in images if img.url or img.b64_json)}张"
    )

    return GenerateResponse(content=content, images=images)
