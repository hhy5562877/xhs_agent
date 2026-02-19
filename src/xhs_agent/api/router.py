import asyncio
import logging
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..api.schemas import GenerateRequest, GenerateResponse
from ..agent.xhs_agent import run
from ..services.upload_service import download_image_to_tmp, upload_image_note
from ..services import account_service
from ..services import goal_service
from ..services.manager_service import plan_operation, calc_scheduled_time
from ..services.scheduler_service import schedule_post

logger = logging.getLogger("xhs_agent")
router = APIRouter(prefix="/api", tags=["xhs"])


# ── 生成 ──────────────────────────────────────────────
class UploadRequest(BaseModel):
    account_id: str | None = None
    cookie: str | None = None
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


@router.post("/upload", response_model=UploadResponse)
async def upload(request: UploadRequest):
    cookie = request.cookie
    if request.account_id:
        cookie = await account_service.get_cookie(request.account_id)
        if not cookie:
            raise HTTPException(status_code=404, detail="账号不存在")
    if not cookie:
        raise HTTPException(status_code=400, detail="需要提供 cookie 或 account_id")

    tmp_paths: list[str] = []
    try:
        logger.info(f"下载 {len(request.image_urls)} 张图片...")
        tmp_paths = await asyncio.gather(*[download_image_to_tmp(u) for u in request.image_urls])
        result = await asyncio.to_thread(
            upload_image_note, cookie, request.title, request.desc, list(tmp_paths), request.hashtags,
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
    name: str = ""
    cookie: str


class AccountPreview(BaseModel):
    cookie: str


@router.post("/accounts/preview")
async def preview_account(body: AccountPreview):
    """传入 cookie，返回小红书账号信息（不保存）"""
    from ..services.upload_service import fetch_user_info
    try:
        info = await asyncio.to_thread(fetch_user_info, body.cookie)
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cookie 无效或请求失败: {e}")


class AccountUpdate(BaseModel):
    name: str | None = None
    cookie: str | None = None


@router.get("/accounts")
async def get_accounts():
    return await account_service.list_accounts()


@router.post("/accounts", status_code=201)
async def create_account(body: AccountCreate):
    return await account_service.add_account(body.name, body.cookie)


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(account_id: str):
    if not await account_service.delete_account(account_id):
        raise HTTPException(status_code=404, detail="账号不存在")


@router.patch("/accounts/{account_id}")
async def update_account(account_id: str, body: AccountUpdate):
    if not await account_service.update_account(account_id, body.name, body.cookie):
        raise HTTPException(status_code=404, detail="账号不存在")
    return {"ok": True}


# ── 运营目标 ──────────────────────────────────────────
class GoalCreate(BaseModel):
    title: str
    description: str
    style: str = "生活方式"
    post_freq: int = 1
    account_id: str


@router.get("/goals")
async def get_goals(account_id: str | None = None):
    return await goal_service.list_goals(account_id)


@router.post("/goals", status_code=201)
async def create_goal(body: GoalCreate):
    return await goal_service.create_goal(body.account_id, body.title, body.description, body.style, body.post_freq)


@router.delete("/goals/{goal_id}", status_code=204)
async def delete_goal(goal_id: int):
    if not await goal_service.delete_goal(goal_id):
        raise HTTPException(status_code=404, detail="目标不存在")


@router.patch("/goals/{goal_id}/toggle")
async def toggle_goal(goal_id: int, active: bool):
    if not await goal_service.toggle_goal(goal_id, active):
        raise HTTPException(status_code=404, detail="目标不存在")
    return {"ok": True}


# ── AI 规划 + 排期 ────────────────────────────────────
@router.post("/goals/{goal_id}/plan")
async def plan_goal(goal_id: int):
    """让总管 AI 分析目标（使用目标绑定的账号），生成并保存7天发布计划"""
    goal = await goal_service.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="目标不存在")

    account_id = goal["account_id"]
    cookie = await account_service.get_cookie(account_id)
    if not cookie:
        raise HTTPException(status_code=404, detail="账号不存在或 Cookie 已失效")

    try:
        plan = await plan_operation(
            goal["title"], goal["description"], goal["style"], goal["post_freq"], cookie
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 规划失败: {e}")

    created_posts = []
    for item in plan.get("weekly_plan", []):
        scheduled_at = calc_scheduled_time(item["day_offset"], item["hour"], item["minute"])
        post = await goal_service.create_scheduled_post(
            goal_id=goal_id,
            account_id=account_id,
            topic=item["topic"],
            style=item.get("style", goal["style"]),
            aspect_ratio=item.get("aspect_ratio", "3:4"),
            image_count=item.get("image_count", 1),
            scheduled_at=scheduled_at,
        )
        run_time = datetime.strptime(scheduled_at, "%Y-%m-%d %H:%M")
        schedule_post(post["id"], run_time)
        created_posts.append(post)

    return {"analysis": plan.get("analysis", ""), "posts": created_posts}


@router.get("/goals/{goal_id}/posts")
async def get_goal_posts(goal_id: int):
    return await goal_service.list_scheduled_posts(goal_id)


@router.get("/posts")
async def get_all_posts():
    return await goal_service.list_scheduled_posts()
