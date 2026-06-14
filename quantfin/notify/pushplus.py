"""PushPlus notification client (WeChat push)."""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

PUSHPLUS_URL = "http://www.pushplus.plus/send"


class PushPlusClient:
    """Push notification via PushPlus (微信公众号推送)."""

    def __init__(self, token: str):
        self.token = token

    def send(self, title: str, content: str, template: str = "markdown") -> bool:
        """Send a notification message.

        Args:
            title: Notification title.
            content: Message body (markdown supported).
            template: Template style ("html", "txt", "json", "markdown").

        Returns True if accepted.
        """
        payload = {
            "token": self.token,
            "title": title,
            "content": content,
            "template": template,
        }
        try:
            resp = requests.post(PUSHPLUS_URL, json=payload, timeout=15)
            data = resp.json()
            if data.get("code") == 200:
                logger.info("PushPlus sent OK: %s", title)
                return True
            logger.error("PushPlus error: code=%s msg=%s", data.get("code"), data.get("msg"))
            return False
        except Exception as exc:
            logger.error("PushPlus request failed: %s", exc)
            return False

    def send_report(self, report: str) -> bool:
        """Send a daily quant report."""
        from datetime import date
        title = f"量化分析日报 - {date.today().isoformat()}"
        return self.send(title, report, template="markdown")
