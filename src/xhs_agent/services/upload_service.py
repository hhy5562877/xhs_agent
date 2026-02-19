import hashlib
import json
import logging
import pathlib
import tempfile
import httpx
import execjs

from xhs import XhsClient

logger = logging.getLogger("xhs_agent")

_JS_DIR = pathlib.Path(__file__).parent.parent.parent.parent / "js" / "xhs"

# 编译签名 JS（模块级别只编译一次）
with open(_JS_DIR / "xhs_xs.js", encoding="utf-8") as f:
    _xs_ctx = execjs.compile(f.read())

with open(_JS_DIR / "xhs_xmns.js", encoding="utf-8") as f:
    _xms_ctx = execjs.compile(f.read())


def _md5(data: dict | None) -> str:
    data_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False) if data else ""
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
    """创建 XhsClient，注入完整 cookie 和必要请求头"""
    client = XhsClient(
        cookie=cookie,
        sign=_make_sign_fn(cookie),
        timeout=60,
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ),
    )
    # 补充 xhs_encrpty_test.py 中的必要请求头
    client.session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "origin": "https://www.xiaohongshu.com",
        "referer": "https://www.xiaohongshu.com/",
    })
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


def fetch_user_info(cookie: str) -> dict:
    """获取账号基本信息：昵称、头像、粉丝数、user_id"""
    client = _make_client(cookie)
    try:
        info = client.get_self_info2()
    except Exception:
        info = client.get_self_info()

    # get_self_info2 返回结构
    basic = info.get("basic_info") or info
    interact = info.get("interact_info") or {}
    return {
        "xhs_user_id": info.get("user_id") or basic.get("user_id") or "",
        "nickname": basic.get("nickname") or info.get("nickname") or "",
        "avatar_url": basic.get("imageb_url") or basic.get("image_url") or info.get("image") or "",
        "fans": str(interact.get("fans_count") or interact.get("follower_count") or ""),
    }



    """获取账号近期笔记统计数据（近 time 天）"""
    client = _make_client(cookie)
    return client.get_notes_statistics(time=time)


def get_user_recent_notes(cookie: str) -> list:
    """获取账号最近发布的笔记列表（含互动数据）"""
    client = _make_client(cookie)
    self_info = client.get_self_info()
    user_id = self_info.get("user_id") or self_info.get("userId", "")
    notes = client.get_user_notes(user_id)
    return notes.get("notes", [])
