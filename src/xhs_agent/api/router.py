import asyncio
import json
import logging
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel
import httpx
from ..api.schemas import GenerateRequest, GenerateResponse
from ..agent.xhs_agent import run
from ..services.upload_service import download_image_to_tmp, upload_image_note
from ..services import account_service
from ..services import goal_service
from ..services import account_image_service
from ..services.manager_service import plan_operation, calc_scheduled_time
from ..services.scheduler_service import schedule_post, scheduler

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
        tmp_paths = await asyncio.gather(
            *[download_image_to_tmp(u) for u in request.image_urls]
        )
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


@router.get("/accounts/{account_id}/check")
async def check_account_cookie(account_id: str):
    cookie = await account_service.get_cookie(account_id)
    if not cookie:
        raise HTTPException(status_code=404, detail="账号不存在")
    from ..services.upload_service import fetch_user_info

    try:
        info = await asyncio.to_thread(fetch_user_info, cookie)
        return {
            "valid": True,
            "nickname": info.get("nickname", ""),
            "fans": info.get("fans", ""),
        }
    except Exception as e:
        return {"valid": False, "reason": str(e)[:100]}


# ── 账号参考图片（组） ──────────────────────────────────


@router.post("/accounts/{account_id}/image-groups")
async def upload_image_group(
    account_id: str,
    files: list[UploadFile] = File(...),
    category: str = Form("style"),
    user_prompt: str = Form(""),
):
    cookie = await account_service.get_cookie(account_id)
    if not cookie:
        raise HTTPException(status_code=404, detail="账号不存在")

    if len(files) > 9:
        raise HTTPException(status_code=400, detail="每组最多 9 张图片")

    file_list: list[tuple[bytes, str]] = []
    for f in files:
        if not f.content_type or not f.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"仅支持图片文件: {f.filename}")
        data = await f.read()
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=400, detail=f"图片大小不能超过 10MB: {f.filename}"
            )
        file_list.append((data, f.filename or "image.jpg"))

    record = await account_image_service.save_group(
        account_id,
        file_list,
        category=category,
        user_prompt=user_prompt,
    )
    return record


@router.get("/accounts/{account_id}/image-groups")
async def get_image_groups(account_id: str, category: str | None = None):
    return await account_image_service.list_groups(account_id, category=category)


@router.delete("/image-groups/{group_id}", status_code=204)
async def delete_image_group(group_id: int):
    if not await account_image_service.delete_group(group_id):
        raise HTTPException(status_code=404, detail="图片组不存在")


@router.post("/image-groups/{group_id}/retry")
async def retry_group_vision(group_id: int):
    if not await account_image_service.retry_group_vision(group_id):
        raise HTTPException(status_code=404, detail="图片组不存在")
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
    return await goal_service.create_goal(
        body.account_id, body.title, body.description, body.style, body.post_freq
    )


@router.delete("/goals/{goal_id}", status_code=204)
async def delete_goal(goal_id: int):
    # 取消调度器中该目标下所有 pending job
    posts = await goal_service.list_scheduled_posts(goal_id)
    for p in posts:
        if p["status"] == "pending":
            job_id = f"post_{p['id']}"
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
    # 删除所有排期记录（不限状态）
    await goal_service.delete_all_posts(goal_id)
    # 删除目标本身
    if not await goal_service.delete_goal(goal_id):
        raise HTTPException(status_code=404, detail="目标不存在")


@router.patch("/goals/{goal_id}/toggle")
async def toggle_goal(goal_id: int, active: bool):
    if not await goal_service.toggle_goal(goal_id, active):
        raise HTTPException(status_code=404, detail="目标不存在")
    return {"ok": True}


class GoalUpdate(BaseModel):
    title: str
    description: str
    style: str
    post_freq: int
    account_id: str


@router.patch("/goals/{goal_id}")
async def update_goal(goal_id: int, body: GoalUpdate):
    if not await goal_service.update_goal(
        goal_id,
        body.title,
        body.description,
        body.style,
        body.post_freq,
        body.account_id,
    ):
        raise HTTPException(status_code=404, detail="目标不存在")
    return {"ok": True}


# ── AI 规划 + 排期 ────────────────────────────────────
import asyncio as _asyncio

_plan_locks: dict[int, _asyncio.Lock] = {}


def _get_plan_lock(goal_id: int) -> _asyncio.Lock:
    if goal_id not in _plan_locks:
        _plan_locks[goal_id] = _asyncio.Lock()
    return _plan_locks[goal_id]


@router.post("/goals/{goal_id}/plan")
async def plan_goal(goal_id: int):
    """让总管 AI 分析目标（使用目标绑定的账号），生成并保存7天发布计划"""
    lock = _get_plan_lock(goal_id)
    if lock.locked():
        raise HTTPException(status_code=429, detail="规划进行中，请勿重复提交")
    async with lock:
        goal = await goal_service.get_goal(goal_id)
        if not goal:
            raise HTTPException(status_code=404, detail="目标不存在")

        account_id = goal["account_id"]
        cookie = await account_service.get_cookie(account_id)
        if not cookie:
            raise HTTPException(status_code=404, detail="账号不存在或 Cookie 已失效")

        accounts = await account_service.list_accounts()
        xhs_user_id = next(
            (a["xhs_user_id"] for a in accounts if a["id"] == account_id), ""
        )

        try:
            plan = await plan_operation(
                goal["title"],
                goal["description"],
                goal["style"],
                goal["post_freq"],
                cookie,
                user_id=xhs_user_id,
                account_id=account_id,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI 规划失败: {e}")

        # 清除旧的 pending 排期（取消调度器中对应 job）
        old_posts = await goal_service.list_scheduled_posts(goal_id)
        for p in old_posts:
            if p["status"] == "pending":
                job_id = f"post_{p['id']}"
                if scheduler.get_job(job_id):
                    scheduler.remove_job(job_id)
        deleted = await goal_service.delete_pending_posts(goal_id)
        if deleted:
            logger.info(f"已清除目标 #{goal_id} 的 {deleted} 条旧 pending 排期")

        created_posts = []
        for item in plan.get("weekly_plan", []):
            scheduled_at = calc_scheduled_time(
                item["day_offset"], item["hour"], item["minute"]
            )
            ref_images_raw = item.get("ref_images", [])
            ref_image_ids = json.dumps(
                [
                    r["group_id"]
                    for r in ref_images_raw
                    if isinstance(r, dict) and "group_id" in r
                ]
            )
            post = await goal_service.create_scheduled_post(
                goal_id=goal_id,
                account_id=account_id,
                topic=item["topic"],
                style=item.get("style", goal["style"]),
                aspect_ratio=item.get("aspect_ratio", "3:4"),
                image_count=item.get("image_count", 1),
                scheduled_at=scheduled_at,
                ref_image_ids=ref_image_ids,
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


@router.post("/posts/{post_id}/run")
async def run_post_now(post_id: int):
    """立即执行一条排期任务（不管 scheduled_at）"""
    from ..db import get_db as _get_db
    from ..services.goal_service import execute_scheduled_post

    async with _get_db() as db:
        async with db.execute(
            "SELECT id, status FROM scheduled_posts WHERE id = ?", (post_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="排期不存在")
    if row["status"] not in ("pending", "failed"):
        raise HTTPException(
            status_code=400, detail=f"当前状态 {row['status']} 不可立即执行"
        )
    async with _get_db() as db:
        await db.execute(
            "UPDATE scheduled_posts SET status='pending', error=NULL WHERE id=?",
            (post_id,),
        )
        await db.commit()
    asyncio.create_task(execute_scheduled_post(post_id))
    return {"ok": True, "post_id": post_id}


@router.get("/proxy/image")
async def proxy_image(url: str):
    """代理 XHS CDN 图片，绕过防盗链"""
    if not url.startswith("https://sns-avatar"):
        raise HTTPException(status_code=400, detail="不支持的图片地址")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url, headers={"Referer": "https://www.xiaohongshu.com"}, timeout=10
        )
    return Response(
        content=resp.content, media_type=resp.headers.get("content-type", "image/webp")
    )


# ── 浏览器服务 ────────────────────────────────────────
class BrowserStartRequest(BaseModel):
    account_id: str


@router.post("/browser/start")
async def browser_start(body: BrowserStartRequest):
    """启动可视化 Playwright 浏览器，注入账号 cookie"""
    from ..services import browser_service

    cookie = await account_service.get_cookie(body.account_id)
    if not cookie:
        raise HTTPException(status_code=404, detail="账号不存在")
    asyncio.create_task(browser_service.start_browser(cookie))
    return {"ok": True, "message": "浏览器启动中，请稍候..."}


@router.post("/browser/stop")
async def browser_stop():
    from ..services import browser_service

    await browser_service.stop_browser()
    return {"ok": True}


@router.get("/browser/status")
async def browser_status():
    from ..services import browser_service

    return browser_service.get_status()


@router.get("/browser/requests")
async def browser_requests():
    from ..services import browser_service

    return browser_service.get_request_log()


# ── 系统配置 ──────────────────────────────────────────
from ..db import get_config, set_config as _set_config

_CONFIG_KEYS = [
    "siliconflow_api_key",
    "siliconflow_base_url",
    "text_model",
    "vision_model",
    "image_api_key",
    "image_api_base_url",
    "image_model",
    "wxpusher_app_token",
    "wxpusher_uids",
    "cos_secret_id",
    "cos_secret_key",
    "cos_region",
    "cos_bucket",
    "cos_path_prefix",
]

_CONFIG_DEFAULTS = {
    "siliconflow_api_key": "",
    "siliconflow_base_url": "https://api.siliconflow.cn/v1",
    "text_model": "Qwen/Qwen3-VL-32B-Instruct",
    "vision_model": "zai-org/GLM-4.6V",
    "image_api_key": "",
    "image_api_base_url": "",
    "image_model": "doubao-seedream-4-5-251128",
    "wxpusher_app_token": "",
    "wxpusher_uids": "",
    "cos_secret_id": "",
    "cos_secret_key": "",
    "cos_region": "ap-guangzhou",
    "cos_bucket": "",
    "cos_path_prefix": "ref_images",
}


@router.get("/config")
async def get_system_config():
    result = {}
    for key in _CONFIG_KEYS:
        result[key] = await get_config(key, _CONFIG_DEFAULTS.get(key, ""))
    return result


class ConfigUpdate(BaseModel):
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    text_model: str = "Qwen/Qwen3-VL-32B-Instruct"
    vision_model: str = "zai-org/GLM-4.6V"
    image_api_key: str = ""
    image_api_base_url: str = ""
    image_model: str = "doubao-seedream-4-5-251128"
    wxpusher_app_token: str = ""
    wxpusher_uids: str = ""
    cos_secret_id: str = ""
    cos_secret_key: str = ""
    cos_region: str = "ap-guangzhou"
    cos_bucket: str = ""
    cos_path_prefix: str = "ref_images"


@router.put("/config")
async def update_system_config(body: ConfigUpdate):
    for key in _CONFIG_KEYS:
        await _set_config(key, getattr(body, key, ""))
    return {"ok": True}
