import asyncio
import logging
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..api.schemas import GenerateRequest, GenerateResponse
from ..agent.xhs_agent import run
from ..services.upload_service import download_image_to_tmp, upload_image_note
from ..services import account_service

logger = logging.getLogger("xhs_agent")
router = APIRouter(prefix="/api", tags=["xhs"])


# ── 生成 ──────────────────────────────────────────────
class UploadRequest(BaseModel):
    account_id: str | None = None   # 使用已保存账号
    cookie: str | None = None       # 或直接传 cookie
    title: str
    desc: str
    image_urls: list[str]
    hashtags: list[str] = []


class UploadResponse(BaseModel):
    note_id: str | None = None
    success: bool
    detail: str = ""


@router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    try:
        return await run(request)
    except Exception as e:
        logger.error(f"生成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 上传 ──────────────────────────────────────────────
@router.post("/upload", response_model=UploadResponse)
async def upload(request: UploadRequest):
    # 解析 cookie
    cookie = request.cookie
    if request.account_id:
        cookie = account_service.get_cookie(request.account_id)
        if not cookie:
            raise HTTPException(status_code=404, detail="账号不存在")
    if not cookie:
        raise HTTPException(status_code=400, detail="需要提供 cookie 或 account_id")

    tmp_paths: list[str] = []
    try:
        logger.info(f"下载 {len(request.image_urls)} 张图片...")
        tmp_paths = await asyncio.gather(*[download_image_to_tmp(u) for u in request.image_urls])
        result = await asyncio.to_thread(
            upload_image_note,
            cookie,
            request.title,
            request.desc,
            list(tmp_paths),
            request.hashtags,
        )
        note_id = result.get("note_id") if isinstance(result, dict) else None
        return UploadResponse(success=True, note_id=note_id)
    except Exception as e:
        logger.error(f"上传失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for p in tmp_paths:
            try:
                os.unlink(p)
            except Exception:
                pass


# ── 账号管理 ──────────────────────────────────────────
class AccountCreate(BaseModel):
    name: str
    cookie: str


class AccountUpdate(BaseModel):
    name: str | None = None
    cookie: str | None = None


@router.get("/accounts")
def get_accounts():
    return account_service.list_accounts()


@router.post("/accounts", status_code=201)
def create_account(body: AccountCreate):
    return account_service.add_account(body.name, body.cookie)


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: str):
    if not account_service.delete_account(account_id):
        raise HTTPException(status_code=404, detail="账号不存在")


@router.patch("/accounts/{account_id}")
def update_account(account_id: str, body: AccountUpdate):
    if not account_service.update_account(account_id, body.name, body.cookie):
        raise HTTPException(status_code=404, detail="账号不存在")
    return {"ok": True}
