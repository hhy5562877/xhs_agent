# -*- coding: utf-8 -*-
import json
import hashlib
import os
import sys
from abc import ABC, abstractmethod
from typing import Dict, Optional

import execjs
from playwright.async_api import Page
from tenacity import RetryError, retry, stop_after_attempt, wait_fixed

# 在 Windows 上设置环境变量，确保 Node.js 使用 UTF-8 编码
if sys.platform == 'win32':
    # 设置 Python IO 编码为 UTF-8
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    # 尝试设置控制台代码页为 UTF-8 (chcp 65001)
    try:
        os.system('chcp 65001 >nul 2>&1')
    except:
        pass

import config
from constant import XHS_JAVASCRIPT_SIGN, XHS_PLAYWRIGHT_SIGN
from context_vars import xhs_manager_ctx_var
from params.xiaohongshu_sign import XhsSignRequest, XhsSignResponse
from pkg import utils
from pkg.playwright.xhs_manager import XhsPlaywrightManager

from .help import sign as xhs_local_js_sign


class AbstractXhsSign(ABC):
    @abstractmethod
    async def sign(self, req_data: XhsSignRequest, force_init: bool = False) -> XhsSignResponse:
        raise NotImplementedError


class XhsPlaywrightSign(AbstractXhsSign):
    def __init__(self):
        pass

    @staticmethod
    def _get_a1_params(cookies_str: str) -> str:
        """
        获取a1参数
        :param cookies_str:
        :return:
        """
        return utils.convert_str_cookie_to_dict(cookies_str).get("a1", "")

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(0.5))
    async def sign(self, req: XhsSignRequest, force_init: bool = False) -> XhsSignResponse:
        """
        xhs请求签名, 如果发生异常默认重试3次，每次间隔500ms
        :param req:
        :param force_init: 是否强制初始化浏览器上下文
        :return:
        """
        xhs_browser_manager: XhsPlaywrightManager = xhs_manager_ctx_var.get()
        if force_init:
            await xhs_browser_manager.reload_page()
        page_obj: Page = xhs_browser_manager.context_page

        encrypt_params = await page_obj.evaluate("([url, data]) => window._webmsxyw(url,data)", [req.uri, req.data])
        local_storage = await page_obj.evaluate("() => window.localStorage")
        sign_result: Dict = xhs_local_js_sign(
            a1=self._get_a1_params(req.cookies),
            b1="I38rHdgsjopgIvesdVwgIC+oIELmBZ5e3VwXLgFTIxS3bqwErFeexd0ekncAzMFYnqthIhJeSnMDKutRI3KsYorWHPtGrbV0P9WfIi/eWc6eYqtyQApPI37ekmR1QL+5Ii6sdnoeSfqYHqwl2qt5B0DoIvMzOZQqZVw7IxOeTqwr4qtiIkrOIi/skccxICLdI3Oe0utl2ADZsLveDSKsSPw5IEvsiutJOqw8BVwfPpdeTDWOIx4VIiu6ZPwbPut5IvlaLbgs3qtxIxes1VwHIkumIkIyejgsY/WTge7sjutKrZgedWI9gfKeYWZGI36eWPwyIEJefut0ocVAPBLLI3Aeiqt3cZ7sVom4IESyIhEqQd4AICY24F4gIiifpVwAICZVJo3sWWJs1qwiIvdef97e0ekKIi/e1piS8qwUIE7s1fds6WAeiVwqed5sdut3IxILbd6sdqtDbgKs0PwgIv8aI3z5rqwGBVtwzfTsKD7sdBdskut+Iioed/As1SiiIkKs0F6s3nVuIkge1Pt0IkVkwPwwNVtMI3/e1qtdIkKs1VwVIEesdutA+qwKsuw7IvrRIxDgJfIj2IJexVtVIhiKIi6eDVw/bz4zLadsYjmfIkWo4VtPmVw5IvAe3qtk+LJeTl5sTSEyIEJekdgs3PtsnPwqI35sSPt0Ih/sV04TIk0ejjNsfqw7Iv3sVut04B8qIkWyIvKsxFOekzNsdAKsYPtKIiMFI3MurVtKIvzjIh6s6lFut//sWqtaI3IYbuwl",
            x_s=encrypt_params.get("X-s", ""),
            x_t=str(encrypt_params.get("X-t", ""))
        )
        return XhsSignResponse(
            x_s=str(sign_result.get("x-s")),
            x_t=sign_result.get("x-t"),
            x_s_common=sign_result.get("x-s-common"),
            x_b3_traceid=sign_result.get("x-b3-traceid")
        )


class XhsJavascriptSign(AbstractXhsSign):
    def __init__(self):
        # 显式读取 UTF-8 编码的 JS 文件，避免 Windows 上的编码问题
        with open('pkg/js/xhs/xhs_xs_new.js', 'r', encoding='utf-8') as f:
            xs_js_code = f.read()
        with open('pkg/js/xhs/xhs_xmns.js', 'r', encoding='utf-8') as f:
            xmns_js_code = f.read()

        self.xhs_xs_sign_obj = execjs.compile(xs_js_code)
        self.xhs_xmns_sign_obj = execjs.compile(xmns_js_code)

    @staticmethod
    def _make_md5_paramsd(api: str, data: Optional[Dict]):
        data_json_str = ""
        if data and isinstance(data, dict):
            data_json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        "".join([api, data_json_str])
        return hashlib.md5(data_json_str.encode()).hexdigest()

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(0.5))
    async def sign(self, req: XhsSignRequest, force_init: bool = False) -> XhsSignResponse:
        """
        xhs请求签名, js补环境版本
        :param req:
        :param force_init:
        :return:
        """
        sign_reslut = self.xhs_xs_sign_obj.call('sign', req.uri, req.data, req.cookies)
        return XhsSignResponse(
            x_s=sign_reslut.get("x-s"),
            x_t=str(sign_reslut.get("x-t")),
            x_s_common=sign_reslut.get("x-s-common"),
            x_b3_traceid=sign_reslut.get("x-b3-traceid"),
        )



class XhsSignFactory:
    @staticmethod
    def get_sign(sign_type: str) -> AbstractXhsSign:
        if sign_type == XHS_PLAYWRIGHT_SIGN:
            return XhsPlaywrightSign()
        elif sign_type == XHS_JAVASCRIPT_SIGN:
            return XhsJavascriptSign()
        else:
            raise NotImplementedError


class XhsSignLogic:
    def __init__(self, sign_type: str):
        """
        初始化
        :param sign_type:
        """
        self.sign_server = XhsSignFactory.get_sign(sign_type)

    async def sign(self, req_data: XhsSignRequest) -> XhsSignResponse:
        """
        签名
        :param req_data:
        :return:
        """
        try:
            return await self.sign_server.sign(req_data)
        except RetryError:
            return await self.sign_server.sign(req_data, force_init=True)
