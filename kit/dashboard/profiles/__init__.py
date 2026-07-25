# -*- coding: utf-8 -*-
"""
Các loại dashboard chuyên sâu — mỗi loại ứng 1 mode cào của MediaCrawler.

| Loại       | Mode cào                | Trả lời câu hỏi gì                        |
|------------|-------------------------|-------------------------------------------|
| `search`   | `--type search`         | Trend gì đang chạy? Làm content gì?       |
| `creator`  | `--type creator`        | Kênh đối thủ mạnh yếu ra sao?             |
| `video`    | `--type detail`         | Mổ xẻ video + khán giả nói gì?            |
| `overview` | trộn nhiều mode         | Bức tranh chéo nền tảng để họp            |

Mỗi module có hàm `build(bundle, meta=...) -> str` (HTML tự chứa).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kit.dashboard.profiles import creator, overview, search, video

# Tên loại -> (hàm dựng, tiêu đề ngắn, tên file mặc định)
REGISTRY: dict[str, tuple[Callable[..., str], str, str]] = {
    "search": (search.build, "Trend Radar — săn trend & ý tưởng content",
               "dashboard_search.html"),
    "creator": (creator.build, "Channel Audit — soi kênh đối thủ",
                "dashboard_creator.html"),
    "video": (video.build, "Video Teardown — mổ xẻ video & bình luận",
              "dashboard_video.html"),
    "overview": (overview.build, "Tổng quan đa nền tảng",
                 "dashboard_overview.html"),
}

PROFILES = tuple(REGISTRY)

# Mode cào của MediaCrawler -> loại dashboard tương ứng.
MODE_TO_PROFILE = {"search": "search", "creator": "creator", "detail": "video"}


def render(profile: str, bundle: dict[str, Any], *,
           meta: dict | None = None) -> str:
    """Gọi hàm dựng của `profile`."""
    if profile not in REGISTRY:
        raise ValueError(f"Loại dashboard không hợp lệ: {profile!r}. "
                         f"Chọn một trong: {', '.join(PROFILES)}")
    return REGISTRY[profile][0](bundle, meta=meta)


def title_of(profile: str) -> str:
    """Tiêu đề ngắn của loại dashboard."""
    return REGISTRY[profile][1]


def filename_of(profile: str) -> str:
    """Tên file HTML mặc định."""
    return REGISTRY[profile][2]


__all__ = ["MODE_TO_PROFILE", "PROFILES", "REGISTRY", "filename_of", "render",
           "title_of"]
