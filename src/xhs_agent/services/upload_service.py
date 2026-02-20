import hashlib
import json
import logging
import pathlib
import tempfile
import httpx
import execjs
from xhs import XhsClient

logger = logging.getLogger("xhs_agent")

_JS_DIR = (
    pathlib.Path(__file__).parent.parent.parent.parent / "xhs_tools" / "js" / "xhs"
)

# 编译签名 JS（模块级别只编译一次）
with open(_JS_DIR / "xhs_xs_new.js", encoding="utf-8") as f:
    _xs_ctx = execjs.compile(f.read())

with open(_JS_DIR / "xhs_xmns.js", encoding="utf-8") as f:
    _xms_ctx = execjs.compile(f.read())


def _md5(data: dict | None) -> str:
    data_str = (
        json.dumps(data, separators=(",", ":"), ensure_ascii=False) if data else ""
    )
    return hashlib.md5(data_str.encode()).hexdigest()


def _make_sign_fn(full_cookie: str):
    """
    返回一个适配 XhsClient 签名回调的函数。
    完整 cookie 字符串直接传给 JS sign()，与 xhs_encrpty_test.py 保持一致。
    """

    def _sign(uri: str, data: dict | None, a1: str = "", web_session: str = "") -> dict:
        xs_sign = _xs_ctx.call("sign", uri, data, full_cookie)
        xmns = _xms_ctx.call("window.getMnsToken", uri, data, _md5(data))
        return {
            "x-s": xs_sign["x-s"],
            "x-t": str(xs_sign["x-t"]),
            "x-s-common": xs_sign["x-s-common"],
            "x-b3-traceid": xs_sign["x-b3-traceid"],
            "x-mns": xmns,
        }

    return _sign


def _make_client(cookie: str) -> XhsClient:
    """创建 XhsClient，注入完整 cookie 和必要请求头，用 curl_cffi 替换内部 session"""
    from curl_cffi.requests import Session as CurlSession

    client = XhsClient(
        cookie=cookie,
        sign=_make_sign_fn(cookie),
        timeout=60,
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
    )
    # 用 curl_cffi session 替换 requests session，模拟 Chrome TLS 指纹
    curl_session = CurlSession(impersonate="chrome131")
    curl_session.headers.update(dict(client.session.headers))
    curl_session.headers.update(
        {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "origin": "https://www.xiaohongshu.com",
            "referer": "https://www.xiaohongshu.com/",
        }
    )
    # 迁移 cookies，确保对所有小红书子域名都有效
    for c in client.session.cookies:
        domain = c.domain if c.domain else ".xiaohongshu.com"
        if not domain.startswith("."):
            domain = "." + domain.lstrip(".")
        curl_session.cookies.set(c.name, c.value, domain=domain, path=c.path or "/")
    # 替换内部 session（name mangling: __session -> _XiaoHongShuClient__session）
    client._XiaoHongShuClient__session = curl_session
    return client


async def download_image_to_tmp(url: str) -> str:
    """将图片 URL 下载到临时文件，返回本地路径"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        tmp.write(resp.content)
        tmp.close()
        return tmp.name


def upload_image_note(
    cookie: str,
    title: str,
    desc: str,
    image_paths: list[str],
    topics: list[str] | None = None,
) -> dict:
    """同步上传图文笔记到小红书"""
    client = _make_client(cookie)

    topic_objs = []
    for tag in topics or []:
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


def _make_http_client(cookie: str):
    """创建 httpx 版 XHS 客户端（用于数据读取）"""
    from .xhs_http import XhsHttpClient

    return XhsHttpClient(cookie, _make_sign_fn(cookie))


def fetch_user_info(cookie: str) -> dict:
    """获取账号基本信息：昵称、头像、粉丝数、user_id"""
    client = _make_http_client(cookie)
    data = client.get_self_info()
    # selfinfo 返回结构: {"basic_info": {...}, "interactions": [...]}
    # basic_info 中只有 red_id，没有 user_id，需要用 v2 接口获取
    basic = data.get("basic_info") or data
    interact_list = data.get("interactions") or []
    fans = ""
    for item in interact_list:
        if item.get("type") == "fans":
            fans = item.get("count", "")
            break
    user_id = basic.get("user_id") or ""
    if not user_id:
        try:
            info_v2 = client.get_self_info_v2()
            user_id = info_v2.get("user_id") or ""
        except Exception:
            pass
    return {
        "xhs_user_id": user_id or basic.get("red_id") or "",
        "nickname": basic.get("nickname") or "",
        "avatar_url": basic.get("imageb") or basic.get("images") or "",
        "fans": fans,
    }


def get_notes_statistics(cookie: str, time: int = 30) -> list:
    """
    获取账号近期笔记统计数据（近 time 天）

    注意：此功能使用创作者中心 API，需要特殊的签名和域名配置。
    如果遇到"登录已过期"错误，说明 Cookie 对创作者中心域名无效，
    这是正常现象，不影响其他功能。
    """
    try:
        client = _make_client(cookie)
        return client.get_notes_statistics(time=time)
    except Exception as e:
        error_msg = str(e)
        if "登录已过期" in error_msg or "code': -1" in error_msg:
            logger.info(f"创作者中心 API 访问受限（Cookie 域名问题），跳过统计数据获取")
        else:
            logger.warning(f"get_notes_statistics 失败: {error_msg[:200]}")
        return []


def get_user_recent_notes(cookie: str, user_id: str = "", limit: int = 20) -> list:
    """获取账号最近发布的笔记列表（含互动数据），使用 httpx 直接请求"""
    client = _make_http_client(cookie)
    if not user_id:
        try:
            info = client.get_self_info_v2()
            logger.info(f"get_self_info_v2 返回数据: {info}")
            user_id = (
                info.get("user_id") or info.get("basic_info", {}).get("user_id") or ""
            )
            if not user_id:
                info_v1 = client.get_self_info()
                logger.info(f"get_self_info_v1 返回数据: {info_v1}")
                basic = info_v1.get("basic_info") or info_v1
                user_id = basic.get("user_id") or ""
        except Exception as e:
            logger.warning(f"获取用户信息失败: {e}")
            return []
    if not user_id:
        logger.warning(
            "get_user_recent_notes: 无法获取 user_id，可能是 Cookie 无效或 API 返回数据格式变化"
        )
        return []
    try:
        notes = client.get_user_all_notes(user_id)
    except Exception as e:
        err_str = str(e)
        if "验证码" in err_str or "Verify" in err_str:
            logger.warning(f"获取笔记时触发验证码，跳过历史数据: {err_str[:100]}")
        else:
            logger.warning(f"get_user_all_notes 失败: {err_str[:200]}")
        return []

    result = []
    for n in notes[:limit]:
        interact = n.get("interact_info") or {}
        result.append(
            {
                "note_id": n.get("note_id", ""),
                "title": n.get("display_title") or n.get("title") or "",
                "type": n.get("type", ""),
                "liked_count": interact.get("liked_count") or 0,
                "collected_count": interact.get("collected_count") or 0,
                "comment_count": interact.get("comment_count") or 0,
                "share_count": interact.get("share_count") or 0,
            }
        )
    return result
