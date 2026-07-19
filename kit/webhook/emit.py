# -*- coding: utf-8 -*-
"""
Bắn event sang n8n (NOTIFY_WEBHOOK_URL).

Nguyên tắc: webhook chỉ là kênh phụ — lỗi mạng KHÔNG được làm hỏng job chính.
Mọi lỗi chỉ log cảnh báo; retry tối đa 2 lần với timeout ngắn.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TIMEOUT_S = 5.0
RETRIES = 2


def emit(event: str, payload: dict[str, Any],
         url: str | None = None, client: httpx.Client | None = None) -> bool:
    """
    POST {event, payload, ts} tới NOTIFY_WEBHOOK_URL.

    Trả True nếu gửi thành công; False nếu thiếu URL hoặc lỗi mạng (đã log,
    không raise). `client` inject được để test không gọi mạng.
    """
    url = url or os.getenv("NOTIFY_WEBHOOK_URL", "")
    if not url:
        logger.info("Bỏ qua webhook: chưa đặt NOTIFY_WEBHOOK_URL.")
        return False
    body = {"event": event, "payload": payload,
            "ts": datetime.now(UTC).isoformat()}
    own_client = client is None
    if own_client:
        client = httpx.Client(timeout=TIMEOUT_S)
    try:
        for attempt in range(1 + RETRIES):
            try:
                resp = client.post(url, json=body)
                resp.raise_for_status()
                logger.info("Webhook '%s' gửi OK (lần %s).", event, attempt + 1)
                return True
            except Exception as exc:  # noqa: BLE001 — nuốt lỗi mạng, chỉ log
                logger.warning("Webhook '%s' lần %s lỗi: %s", event, attempt + 1, exc)
        return False
    finally:
        if own_client:
            client.close()


def notify_trend_brief(text: str, url: str | None = None,
                       client: httpx.Client | None = None) -> bool:
    """Gửi bản tóm tắt Trend Brief (CS1) — n8n chuyển tiếp Zalo/Slack."""
    return emit("trend_brief", {"text": text}, url=url, client=client)


def notify_rising_koc(creators: list[dict[str, Any]], url: str | None = None,
                      client: httpx.Client | None = None) -> bool:
    """Gửi danh sách KOC đang lên (CS9)."""
    return emit("rising_koc", {"creators": creators, "count": len(creators)},
                url=url, client=client)


def notify_sov_updated(url: str | None = None,
                       client: httpx.Client | None = None) -> bool:
    """Báo SOV tuần đã cập nhật (CS11) — n8n tự query view v_sov_trend."""
    return emit("sov_updated", {}, url=url, client=client)
