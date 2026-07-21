# -*- coding: utf-8 -*-
"""Tầng báo cáo DigiAds — sinh HTML tự chứa (kèm biểu đồ SVG) từ kết quả analyzer.

Không thêm thư viện ngoài: biểu đồ vẽ bằng SVG server-side, HTML tự chứa
(mở offline / in được). Bảng màu lấy từ dataviz skill (đã kiểm định CVD).
"""

from __future__ import annotations

from kit.report.html_report import build_report

__all__ = ["build_report"]
