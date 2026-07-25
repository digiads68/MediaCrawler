# -*- coding: utf-8 -*-
"""DigiAds · Dashboard đa nền tảng.

Gộp nhiều file raw MediaCrawler (Douyin / Bilibili / Xiaohongshu, search & creator)
thành **một dashboard HTML tự chứa, tương tác** phục vụ nghiên cứu trend, lên
content và soi kênh đối thủ. Có preview video, biểu đồ, và nút bấm nối sang n8n
(tải video, voice→text, phân tích nội dung/hook).

Dùng nhanh:
    from kit.dashboard import build_dashboard
    build_dashboard(["data/douyin/search.xlsx", "data/bili/search.xlsx"])
"""

from __future__ import annotations

from kit.dashboard.build import build_dashboard

__all__ = ["build_dashboard"]
