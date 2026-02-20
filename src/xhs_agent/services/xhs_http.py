"""
用 curl_cffi 直接发 XHS API 请求，模拟 Chrome TLS 指纹，复用本地签名函数。
"""
import json
import logging
import random
import secrets
import time
from typing import Any
from curl_cffi.requests import Session

logger = logging.getLogger("xhs_agent")

XHS_HOST = "https://edith.xiaohongshu.com"


class XhsHttpClient:
    def __init__(self, cookie: str, sign_fn):
        self.cookie = cookie
        self.sign_fn = sign_fn
        self._session = Session(impersonate="chrome131")
        self._base_headers = {
            "Cookie": cookie,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Priority": "u=1, i",
            "Origin": "https://www.xiaohongshu.com",
            "Referer": "https://www.xiaohongshu.com/",
            "Sec-Ch-Ua": '"Not:A-Brand";v="99", "Google Chrome";v="131", "Chromium";v="131"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        }

    def _build_headers(self, uri: str, data: dict | None = None) -> dict:
        signs = self.sign_fn(uri, data)
        traceid = secrets.token_hex(8)
        return {**self._base_headers, **signs, "x-xray-traceid": traceid}

    def get(self, uri: str, params: dict | None = None) -> Any:
        query = ""
        if params:
            query = "?" + "&".join(f"{k}={v}" for k, v in params.items())
        full_uri = uri + query
        headers = self._build_headers(full_uri)
        resp = self._session.get(XHS_HOST + full_uri, headers=headers, timeout=30)
        return self._handle(resp)

    def post(self, uri: str, data: dict | None = None) -> Any:
        headers = self._build_headers(uri, data)
        headers["Content-Type"] = "application/json;charset=UTF-8"
        resp = self._session.post(XHS_HOST + uri, headers=headers, json=data or {}, timeout=30)
        return self._handle(resp)

    def _handle(self, resp) -> Any:
        if resp.status_code in (471, 461):
            verify_type = resp.headers.get("Verifytype", "?")
            verify_uuid = resp.headers.get("Verifyuuid", "?")
            raise RuntimeError(
                f"出现验证码，请求失败，Verifytype: {verify_type}，Verifyuuid: {verify_uuid}"
            )
        try:
            data = resp.json()
        except Exception:
            resp.raise_for_status()
            return {}
        logger.debug(f"XHS response: {json.dumps(data, ensure_ascii=False)[:300]}")
        if data.get("success"):
            return data.get("data", {})
        if data.get("code") == 0:
            return data.get("data", {})
        raise RuntimeError(f"XHS API 错误: {data}")

    # ── 具体接口 ──────────────────────────────────────────

    def get_self_info(self) -> dict:
        return self.get("/api/sns/web/v1/user/selfinfo") or {}

    def get_user_notes(self, user_id: str, cursor: str = "") -> dict:
        params = {
            "num": 30,
            "cursor": cursor,
            "user_id": user_id,
            "image_formats": "jpg,webp,avif",
            "xsec_token": "",
            "xsec_source": "",
        }
        return self.get("/api/sns/web/v1/user_posted", params) or {}

    def get_user_all_notes(self, user_id: str) -> list[dict]:
        """分页获取全部笔记，返回简单 dict 列表"""
        results = []
        cursor = ""
        while True:
            data = self.get_user_notes(user_id, cursor)
            notes = data.get("notes", [])
            results.extend(notes)
            if not data.get("has_more") or not notes:
                break
            cursor = data.get("cursor", "")
        logger.info(f"get_user_all_notes 共获取 {len(results)} 条笔记")
        return results

    # ── 搜索笔记 ──────────────────────────────────────────

    @staticmethod
    def _get_search_id() -> str:
        """生成搜索会话 ID：毫秒时间戳左移64位 + 随机数，Base36 编码"""
        e = int(time.time() * 1000) << 64
        t = int(random.uniform(0, 2147483646))
        n = e + t
        alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        base36 = ""
        while n:
            n, i = divmod(n, 36)
            base36 = alphabet[i] + base36
        return base36 or "0"

    def search_notes(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20,
        sort: str = "general",
        note_type: int = 0,
    ) -> dict:
        """关键词搜索笔记 (POST /api/sns/web/v1/search/notes)"""
        data = {
            "keyword": keyword,
            "page": page,
            "page_size": page_size,
            "search_id": self._get_search_id(),
            "sort": sort,
            "note_type": note_type,
        }
        return self.post("/api/sns/web/v1/search/notes", data) or {}

    # ── 笔记详情 ──────────────────────────────────────────

    def get_note_by_id(
        self,
        note_id: str,
        xsec_token: str = "",
        xsec_source: str = "pc_feed",
    ) -> dict:
        """获取笔记详情 (POST /api/sns/web/v1/feed)"""
        data = {
            "source_note_id": note_id,
            "image_formats": ["jpg", "webp", "avif"],
            "extra": {"need_body_topic": 1},
            "xsec_token": xsec_token,
            "xsec_source": xsec_source,
        }
        return self.post("/api/sns/web/v1/feed", data) or {}

    # ── 评论 ──────────────────────────────────────────────

    def get_note_comments(
        self,
        note_id: str,
        cursor: str = "",
        xsec_token: str = "",
    ) -> dict:
        """获取笔记评论列表 (GET /api/sns/web/v2/comment/page)"""
        params = {
            "note_id": note_id,
            "cursor": cursor,
            "top_comment_id": "",
            "image_formats": "jpg,webp,avif",
            "xsec_token": xsec_token,
        }
        return self.get("/api/sns/web/v2/comment/page", params) or {}

    def get_note_sub_comments(
        self,
        note_id: str,
        root_comment_id: str,
        num: int = 10,
        cursor: str = "",
        xsec_token: str = "",
    ) -> dict:
        """获取子评论（回复）(GET /api/sns/web/v2/comment/sub/page)"""
        params = {
            "note_id": note_id,
            "root_comment_id": root_comment_id,
            "num": num,
            "cursor": cursor,
            "xsec_token": xsec_token,
        }
        return self.get("/api/sns/web/v2/comment/sub/page", params) or {}

    # ── 短链接 ────────────────────────────────────────────

    def get_note_short_url(self, original_url: str) -> dict:
        """获取笔记短链接 (POST /api/sns/web/short_url)"""
        return self.post("/api/sns/web/short_url", {"original_url": original_url}) or {}

    # ── 首页推荐 ──────────────────────────────────────────

    def get_homefeed_notes(
        self,
        category: str = "homefeed_recommend",
        cursor_score: str = "",
        note_index: int = 0,
        num: int = 18,
    ) -> dict:
        """获取首页推荐笔记 (POST /api/sns/web/v1/homefeed)"""
        data = {
            "category": category,
            "cursor_score": cursor_score,
            "image_formats": ["jpg", "webp", "avif"],
            "need_filter_image": False,
            "need_num": num,
            "note_index": note_index,
            "num": num,
            "refresh_type": 3,
            "search_key": "",
            "unread_begin_note_id": "",
            "unread_end_note_id": "",
            "unread_note_count": 0,
        }
        return self.post("/api/sns/web/v1/homefeed", data) or {}
