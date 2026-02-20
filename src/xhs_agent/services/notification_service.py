import logging
import httpx
from typing import Optional
from ..config import get_setting

logger = logging.getLogger("xhs_agent")


class NotificationService:
    """WxPusher 通知服务封装"""

    BASE_URL = "https://wxpusher.zjiecode.com/api"

    def __init__(self):
        self.app_token = ""
        self.uids = []

    async def _load_config(self):
        self.app_token = await get_setting("wxpusher_app_token")
        uids_str = await get_setting("wxpusher_uids")
        self.uids = [uid.strip() for uid in uids_str.split(",") if uid.strip()]

    def is_enabled(self) -> bool:
        """检查通知服务是否已配置"""
        return bool(self.app_token and self.uids)

    async def send_message(
        self,
        content: str,
        summary: Optional[str] = None,
        content_type: int = 1,
        topic_ids: Optional[list[int]] = None,
        url: Optional[str] = None,
    ) -> bool:
        """
        发送消息通知

        Args:
            content: 消息内容，支持 HTML（content_type=2）或纯文本（content_type=1）
            summary: 消息摘要，显示在微信聊天列表，不传默认截取 content 前 10 个字符
            content_type: 内容类型，1=纯文本，2=HTML，3=Markdown
            topic_ids: 主题 ID 列表，用于群发
            url: 原文链接，点击消息跳转的 URL

        Returns:
            bool: 发送是否成功
        """
        await self._load_config()

        if not self.is_enabled():
            logger.warning("WxPusher 未配置，跳过通知发送")
            return False

        try:
            payload = {
                "appToken": self.app_token,
                "content": content,
                "contentType": content_type,
                "uids": self.uids,
            }

            if summary:
                payload["summary"] = summary
            if topic_ids:
                payload["topicIds"] = topic_ids
            if url:
                payload["url"] = url

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/send/message",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()

                if result.get("code") == 1000:
                    logger.info(f"WxPusher 通知发送成功: {summary or content[:20]}")
                    return True
                else:
                    logger.error(f"WxPusher 通知发送失败: {result.get('msg')}")
                    return False

        except Exception as e:
            logger.error(f"WxPusher 通知发送异常: {e}")
            return False

    async def send_success_notification(self, title: str, details: str) -> bool:
        """发送成功通知"""
        content = f"✅ {title}\n\n{details}"
        return await self.send_message(content, summary=f"✅ {title}")

    async def send_error_notification(self, title: str, error: str) -> bool:
        """发送错误通知"""
        content = f"❌ {title}\n\n错误信息：{error}"
        return await self.send_message(content, summary=f"❌ {title}")

    async def send_warning_notification(self, title: str, warning: str) -> bool:
        """发送警告通知"""
        content = f"⚠️ {title}\n\n警告信息：{warning}"
        return await self.send_message(content, summary=f"⚠️ {title}")


_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """获取通知服务单例"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
