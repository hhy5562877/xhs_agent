"""
Playwright 浏览器服务
- 启动可视化 Chromium，注入 cookie，拦截并记录所有 XHS API 请求
- 验证码出现时用户可在浏览器窗口手动处理
"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("xhs_agent")

# 请求日志保存目录
LOG_DIR = Path("log/browser_requests")
LOG_DIR.mkdir(parents=True, exist_ok=True)

_browser = None
_context = None
_page = None
_status = "stopped"   # stopped | starting | running
_request_log: list[dict] = []


def get_status() -> dict:
    return {"status": _status, "request_count": len(_request_log)}


def get_request_log() -> list[dict]:
    return _request_log


async def start_browser(cookie: str) -> None:
    global _browser, _context, _page, _status, _request_log
    if _status == "running":
        return
    _status = "starting"
    _request_log = []

    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    _browser = await pw.chromium.launch(headless=False, args=["--start-maximized"])
    _context = await _browser.new_context(
        viewport=None,
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ),
    )

    # 注入 cookie
    cookies = _parse_cookie_str(cookie)
    await _context.add_cookies(cookies)

    _page = await _context.new_page()

    # 拦截并记录所有 XHS API 请求
    async def on_request(request):
        if "xiaohongshu.com" in request.url or "xhscdn.com" in request.url:
            entry = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "method": request.method,
                "url": request.url,
                "headers": dict(request.headers),
                "post_data": request.post_data,
            }
            _request_log.append(entry)
            logger.info(f"[Browser] {request.method} {request.url[:100]}")

    async def on_response(response):
        if "xiaohongshu.com/api" in response.url:
            try:
                body = await response.json()
                # 更新最后一条匹配的请求记录
                for entry in reversed(_request_log):
                    if entry["url"] == response.url:
                        entry["response"] = body
                        entry["status"] = response.status
                        break
            except Exception:
                pass

    _page.on("request", on_request)
    _page.on("response", on_response)

    await _page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded")
    _status = "running"
    logger.info("Playwright 浏览器已启动，已注入 cookie 并打开小红书")

    # 定期保存请求日志到文件
    asyncio.create_task(_save_log_loop())


async def stop_browser() -> None:
    global _browser, _context, _page, _status
    if _browser:
        await _browser.close()
        _browser = _context = _page = None
    _status = "stopped"
    logger.info("Playwright 浏览器已关闭")


async def fetch_via_browser(url: str, method: str = "GET", data: dict | None = None) -> Any:
    """通过浏览器页面执行 fetch 请求，绕过验证码"""
    if _status != "running" or not _page:
        raise RuntimeError("浏览器未启动")
    js = f"""
    async () => {{
        const resp = await fetch({json.dumps(url)}, {{
            method: {json.dumps(method)},
            headers: {{"Content-Type": "application/json"}},
            {f'body: JSON.stringify({json.dumps(data)}),' if data else ''}
        }});
        return await resp.json();
    }}
    """
    return await _page.evaluate(js)


async def _save_log_loop():
    """每30秒将请求日志写入文件"""
    while _status == "running":
        await asyncio.sleep(30)
        if _request_log:
            log_file = LOG_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            log_file.write_text(json.dumps(_request_log, ensure_ascii=False, indent=2))
            logger.info(f"已保存 {len(_request_log)} 条浏览器请求日志到 {log_file}")


def _parse_cookie_str(cookie_str: str) -> list[dict]:
    """将 cookie 字符串解析为 Playwright 格式"""
    cookies = []
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        name, _, value = part.partition("=")
        cookies.append({
            "name": name.strip(),
            "value": value.strip(),
            "domain": ".xiaohongshu.com",
            "path": "/",
        })
    return cookies
