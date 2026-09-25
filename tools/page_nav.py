# -*- coding: utf-8 -*-
"""Mở trang chủ nền tảng một cách chịu lỗi.

Vấn đề: `page.goto(url)` mặc định chờ sự kiện "load" (tải xong mọi video/ảnh).
Trang chủ Douyin/XHS/Bilibili rất nặng, hay vượt 30 giây, và chỉ một lần chậm là
cả phiên crawl dừng với `Page.goto: Timeout 30000ms exceeded`.

Crawler chỉ cần cookie + localStorage (có ngay khi HTML xong), nên chờ
"domcontentloaded", cho thêm một khoảng ngắn chờ "load" nhưng không bắt buộc,
và thử lại vài lần khi mạng chậm.
"""

from __future__ import annotations

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from tools import utils


async def goto_resilient(
    page: Page,
    url: str,
    *,
    attempts: int = 3,
    nav_timeout_ms: int = 45_000,
    settle_timeout_ms: int = 15_000,
) -> None:
    """Mở `url`, không để trang tải chậm làm hỏng cả phiên crawl.

    Args:
        page: trang Playwright.
        url: địa chỉ cần mở.
        attempts: số lần thử khi quá thời gian.
        nav_timeout_ms: thời gian tối đa chờ "domcontentloaded" mỗi lần.
        settle_timeout_ms: thời gian chờ thêm "load"; hết giờ thì bỏ qua.

    Raises:
        PlaywrightTimeoutError: khi cả `attempts` lần đều không tải được HTML.
    """
    last_error: PlaywrightTimeoutError | None = None
    for attempt in range(1, attempts + 1):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=nav_timeout_ms)
            break
        except PlaywrightTimeoutError as exc:
            last_error = exc
            utils.logger.warning(
                f"[goto_resilient] Mở {url} quá {nav_timeout_ms // 1000}s "
                f"(lần {attempt}/{attempts}), thử lại..."
            )
    else:
        assert last_error is not None
        raise last_error

    try:
        await page.wait_for_load_state("load", timeout=settle_timeout_ms)
    except PlaywrightTimeoutError:
        utils.logger.info(
            f"[goto_resilient] {url} chưa tải xong toàn bộ sau {settle_timeout_ms // 1000}s, "
            "tiếp tục vì cookie/localStorage đã sẵn sàng"
        )
