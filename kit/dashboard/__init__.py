# -*- coding: utf-8 -*-
"""DigiAds · Dashboard nghiên cứu nội dung (đa nền tảng, chuyên sâu theo mode cào).

MediaCrawler có 3 mode cào — mỗi mode cho ra dữ liệu có "hình" khác nhau, nên
mỗi mode có 1 dashboard chuyên sâu riêng thay vì một bản tổng quan chung:

| Loại       | Mode cào         | Chuyên sâu về                              |
|------------|------------------|--------------------------------------------|
| `search`   | `--type search`  | Trend Radar: chuẩn ngách, khe trống, hook  |
| `creator`  | `--type creator` | Channel Audit: nhịp đăng, bài bứt phá      |
| `video`    | `--type detail`  | Teardown: giải phẫu video + bình luận      |
| `overview` | trộn nhiều mode  | Bức tranh chéo nền tảng để họp             |

Dùng nhanh:
    from kit.dashboard import build_dashboard, build_all
    build_dashboard(["data/douyin/search.xlsx"], profile="search")
    build_all(["data/douyin/search.xlsx", "data/douyin/creator.xlsx"])
"""

from __future__ import annotations

from kit.dashboard.build import build_all, build_dashboard, pick_profile
from kit.dashboard.profiles import PROFILES

__all__ = ["PROFILES", "build_all", "build_dashboard", "pick_profile"]
