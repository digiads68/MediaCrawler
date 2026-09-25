# -*- coding: utf-8 -*-
"""Kiểm tra phân trang tìm kiếm Douyin (dữ liệu synthetic, không gọi mạng).

Lỗi cũ: điều kiện vòng lặp chỉ cho chạy 1 trang/từ khoá khi MAX_NOTES=15,
xin count=15 nhưng offset bước 10 -> các trang chồng 5 bài; ngoài ra ô
KEYWORDS rỗng khiến crawler âm thầm dùng từ khoá mặc định của config.
"""

from __future__ import annotations

from typing import Dict, List
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import config
from api.main import app
from media_platform.douyin import core as dy_core
from media_platform.douyin.client import DouYinClient
from media_platform.douyin.core import DouYinCrawler


def _aweme(aweme_id: str) -> Dict:
    return {"type": 1, "aweme_info": {"aweme_id": aweme_id, "desc": f"video {aweme_id}"}}


class _FakeClient:
    """Trả các trang theo offset, ghi lại mọi lần gọi."""

    def __init__(self, pages: Dict[int, Dict]) -> None:
        self.pages = pages
        self.calls: List[Dict] = []

    async def search_info_by_keyword(self, **kwargs) -> Dict:  # noqa: ANN003
        self.calls.append(kwargs)
        return self.pages.get(kwargs["offset"], {"data": [], "has_more": 0})


async def _run_search(pages: Dict[int, Dict], max_count: int, keywords: str = "#aigc"):
    crawler = DouYinCrawler()
    crawler.dy_client = _FakeClient(pages)
    stored: List[str] = []

    async def fake_store(aweme_item: Dict) -> None:
        stored.append(aweme_item["aweme_id"])

    with patch.object(config, "KEYWORDS", keywords), \
            patch.object(config, "CRAWLER_MAX_NOTES_COUNT", max_count), \
            patch.object(config, "START_PAGE", 1), \
            patch.object(config, "PUBLISH_TIME_TYPE", 0), \
            patch.object(dy_core.douyin_store, "update_douyin_aweme", side_effect=fake_store), \
            patch.object(DouYinCrawler, "download_media", new=AsyncMock()), \
            patch.object(DouYinCrawler, "batch_get_note_comments", new=AsyncMock()), \
            patch.object(dy_core.asyncio, "sleep", new=AsyncMock()):
        await crawler.search()
    return crawler.dy_client.calls, stored


def _page(ids: List[str], cursor: int, has_more: int = 1, logid: str = "LOG1") -> Dict:
    return {"data": [_aweme(i) for i in ids], "has_more": has_more,
            "cursor": cursor, "extra": {"logid": logid}}


@pytest.mark.asyncio
async def test_follows_cursor_until_max_count():
    """MAX=25 phải đi đủ 3 trang theo cursor 0 -> 10 -> 20, không dừng ở trang 1."""
    pages = {
        0: _page([f"a{i}" for i in range(9)], cursor=10),   # trang đầu thiếu 1 bài như web thật
        10: _page([f"b{i}" for i in range(10)], cursor=20),
        20: _page([f"c{i}" for i in range(10)], cursor=30),
    }
    calls, stored = await _run_search(pages, max_count=25)
    assert [c["offset"] for c in calls] == [0, 10, 20]
    assert all(c["count"] == 10 for c in calls)
    assert len(stored) == 25
    # search_id của trang đầu được mang theo các trang sau
    assert calls[0]["search_id"] == "" and calls[1]["search_id"] == "LOG1" and calls[2]["search_id"] == "LOG1"


@pytest.mark.asyncio
async def test_dedupes_overlapping_pages_and_skips_non_video_cards():
    pages = {
        0: {**_page(["x1", "x2", "x3"], cursor=10), "data": [_aweme("x1"), {"type": 16, "user_list": []},
                                                              _aweme("x2"), _aweme("x3")]},
        10: _page(["x3", "x4"], cursor=20, has_more=0),  # x3 trùng trang trước
    }
    _, stored = await _run_search(pages, max_count=50)
    assert stored == ["x1", "x2", "x3", "x4"]


@pytest.mark.asyncio
async def test_stops_when_has_more_is_zero():
    pages = {0: _page(["only1", "only2"], cursor=10, has_more=0)}
    calls, stored = await _run_search(pages, max_count=100)
    assert len(calls) == 1
    assert stored == ["only1", "only2"]


@pytest.mark.asyncio
async def test_small_max_count_is_respected():
    pages = {0: _page([f"a{i}" for i in range(10)], cursor=10)}
    calls, stored = await _run_search(pages, max_count=3)
    assert len(calls) == 1 and len(stored) == 3


@pytest.mark.asyncio
async def test_search_params_match_web():
    """Tham số khớp trang web thật (normal_search + single + count=10, không from_group_id)."""
    captured: Dict = {}

    class _StubPage:
        async def evaluate(self, expression):  # noqa: ANN001
            return {}

    client = DouYinClient(headers={"User-Agent": "ua", "Cookie": "a=1"},
                          playwright_page=_StubPage(), cookie_dict={})

    async def fake_get(uri, params=None, headers=None):  # noqa: ANN001
        captured.update(uri=uri, params=dict(params), referer=headers["Referer"])
        return {}

    client.get = fake_get  # type: ignore[method-assign]
    await client.search_info_by_keyword(keyword="#aigc", offset=10, search_id="LOG1")
    p = captured["params"]
    assert p["search_source"] == "normal_search" and p["list_type"] == "single"
    assert p["count"] == "10" and p["offset"] == 10 and p["search_id"] == "LOG1"
    assert "from_group_id" not in p
    assert "%23aigc" in captured["referer"]


@pytest.mark.parametrize("keywords", ["", "  ", " , "])
def test_api_rejects_search_without_keywords(keywords: str):
    """Không có từ khoá -> 400, không được âm thầm dùng từ khoá mặc định của config."""
    client = TestClient(app)
    with patch("api.routers.crawler.crawler_manager.start", new_callable=AsyncMock) as mock_start:
        resp = client.post("/api/crawler/start", json={
            "platform": "dy", "crawler_type": "search", "keywords": keywords})
    assert resp.status_code == 400
    mock_start.assert_not_called()
