# -*- coding: utf-8 -*-
"""goto_resilient: trang chậm không được làm hỏng phiên crawl (không mở trình duyệt thật)."""

from __future__ import annotations

from typing import List

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from tools.page_nav import goto_resilient


class _FakePage:
    def __init__(self, goto_failures: int = 0, load_times_out: bool = False) -> None:
        self.goto_failures = goto_failures
        self.load_times_out = load_times_out
        self.goto_calls: List[dict] = []

    async def goto(self, url: str, wait_until: str, timeout: int) -> None:
        self.goto_calls.append({"url": url, "wait_until": wait_until, "timeout": timeout})
        if len(self.goto_calls) <= self.goto_failures:
            raise PlaywrightTimeoutError("Timeout exceeded")

    async def wait_for_load_state(self, state: str, timeout: int) -> None:
        if self.load_times_out:
            raise PlaywrightTimeoutError("load not reached")


@pytest.mark.asyncio
async def test_waits_for_domcontentloaded_not_full_load():
    page = _FakePage()
    await goto_resilient(page, "https://www.douyin.com")
    assert page.goto_calls[0]["wait_until"] == "domcontentloaded"


@pytest.mark.asyncio
async def test_slow_full_load_is_not_an_error():
    """Lỗi cũ: chờ 'load' quá 30s -> crawler thoát code 1. Nay chỉ ghi log rồi đi tiếp."""
    page = _FakePage(load_times_out=True)
    await goto_resilient(page, "https://www.douyin.com")
    assert len(page.goto_calls) == 1


@pytest.mark.asyncio
async def test_retries_then_succeeds():
    page = _FakePage(goto_failures=2)
    await goto_resilient(page, "https://www.douyin.com", attempts=3)
    assert len(page.goto_calls) == 3


@pytest.mark.asyncio
async def test_gives_up_after_all_attempts():
    page = _FakePage(goto_failures=5)
    with pytest.raises(PlaywrightTimeoutError):
        await goto_resilient(page, "https://www.douyin.com", attempts=3)
    assert len(page.goto_calls) == 3
