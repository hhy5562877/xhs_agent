import logging
import pathlib
import tempfile
import httpx
from playwright.sync_api import sync_playwright
from xhs import XhsClient

logger = logging.getLogger("xhs_agent")

STEALTH_JS = pathlib.Path(__file__).parent.parent.parent.parent / "utils" / "stealth.min.js"


def _sign_with_playwright(uri: str, data=None, a1: str = "", web_session: str = "") -> dict:
    """使用 Playwright 在小红书页面执行签名"""
    for _ in range(3):
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                ctx = browser.new_context()
                ctx.add_init_script(path=str(STEALTH_JS))
                page = ctx.new_page()
                page.goto("https://www.xiaohongshu.com")
                ctx.add_cookies([{"name": "a1", "value": a1, "domain": ".xiaohongshu.com", "path": "/"}])
                page.reload()
                page.wait_for_timeout(2000)
                result = page.evaluate("([url, data]) => window._webmsxyw(url, data)", [uri, data])
                browser.close()
                return {"x-s": result["X-s"], "x-t": str(result["X-t"])}
        except Exception as e:
            logger.warning(f"签名重试: {e}")
    raise RuntimeError("Playwright 签名失败，已重试 3 次")


def _make_client(cookie: str) -> XhsClient:
    return XhsClient(cookie=cookie, sign=_sign_with_playwright, timeout=60)


async def download_image_to_tmp(url: str) -> str:
    """将图片 URL 下载到临时文件，返回本地路径"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        suffix = ".jpg"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(resp.content)
        tmp.close()
        return tmp.name


def upload_image_note(cookie: str, title: str, desc: str, image_paths: list[str], topics: list[str] | None = None) -> dict:
    """同步上传图文笔记到小红书（xhs 库为同步）"""
    client = _make_client(cookie)

    # 获取话题 id
    topic_objs = []
    for tag in (topics or []):
        try:
            results = client.get_suggest_topic(tag)
            if results:
                topic_objs.append(results[0])
        except Exception as e:
            logger.warning(f"获取话题 '{tag}' 失败: {e}")

    logger.info(f"开始上传图文笔记: {title}，图片数: {len(image_paths)}")
    result = client.create_image_note(
        title=title,
        desc=desc,
        files=image_paths,
        topics=topic_objs,
    )
    logger.info(f"上传成功: {result}")
    return result
