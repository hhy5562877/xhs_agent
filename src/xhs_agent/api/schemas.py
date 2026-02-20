from pydantic import BaseModel, Field
from typing import Literal


class GenerateRequest(BaseModel):
    topic: str = Field(..., description="内容主题，例如：'秋日咖啡馆探店'")
    style: str = Field(
        default="生活方式", description="内容风格，例如：美食、旅行、穿搭"
    )
    aspect_ratio: Literal[
        "1:1", "4:5", "3:4", "9:16", "16:9", "4:3", "2:3", "3:2", "21:9"
    ] = Field(default="3:4", description="图片比例")
    image_count: int = Field(default=1, ge=1, le=4, description="生成图片数量")


class XHSContent(BaseModel):
    title: str
    body: str
    hashtags: list[str]
    image_prompts: list[str]
    image_styles: list[Literal["photo", "poster"]] = Field(
        default_factory=list,
        description="整篇笔记的统一视觉风格，列表中只有一个值：photo=真实照片，poster=海报设计",
    )


class GeneratedImage(BaseModel):
    url: str | None = None
    b64_json: str | None = None


class GenerateResponse(BaseModel):
    content: XHSContent
    images: list[GeneratedImage]
