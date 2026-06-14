"""WxPusher notification client (微信推送)."""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

WXPUSHER_URL = "https://wxpusher.zjiecode.com/api/send/message"


class WxPusherClient:
    """Push notification via WxPusher (微信公众号/个人推送)."""

    def __init__(self, app_token: str, uid: str):
        self.app_token = app_token
        self.uid = uid

    def send(self, title: str, content: str, content_type: int = 3) -> bool:
        """Send a notification message.

        Args:
            title: Notification title (used as summary for markdown).
            content: Message body.
            content_type: 1=text, 2=HTML, 3=Markdown.

        Returns True if accepted (code == 1000).
        """
        payload = {
            "appToken": self.app_token,
            "content": content,
            "summary": title,
            "contentType": content_type,
            "uids": [self.uid],
        }
        try:
            resp = requests.post(WXPUSHER_URL, json=payload, timeout=15)
            data = resp.json()
            if data.get("code") == 1000:
                logger.info("WxPusher sent OK: %s", title)
                return True
            logger.error("WxPusher error: code=%s msg=%s", data.get("code"), data.get("msg"))
            return False
        except Exception as exc:
            logger.error("WxPusher request failed: %s", exc)
            return False

    def send_report(self, report: str) -> bool:
        """Send a daily quant report."""
        from datetime import date
        title = f"量化分析日报 - {date.today().isoformat()}"
        return self.send(title, report, content_type=3)
