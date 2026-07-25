# -*- coding: utf-8 -*-
"""
Điều phối: nhiều file raw → dashboard HTML.

    build_dashboard(paths, out="reports/dashboard.html")
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from kit.dashboard.metrics import compute_sections, load_unified
from kit.dashboard.render import render_dashboard

REPORT_DIR = Path("reports")


def build_dashboard(paths: list[str | Path], *, out: str | Path | None = None,
                    n8n_webhook: str | None = None) -> Path:
    """
    Sinh 1 file dashboard HTML từ danh sách file raw MediaCrawler.

    paths: danh sách .xlsx/.jsonl/.csv (đa nền tảng, trộn search/creator được).
    out: đường dẫn file HTML đầu ra (mặc định reports/dashboard.html).
    n8n_webhook: URL webhook mặc định nhúng vào trang (người dùng vẫn đổi được
        trên UI). Nếu None → đọc N8N_ACTION_WEBHOOK_URL rồi NOTIFY_WEBHOOK_URL.
    Trả về Path file đã ghi.
    """
    if not paths:
        raise ValueError("Cần ít nhất 1 file dữ liệu.")
    df = load_unified(list(paths))
    sections = compute_sections(df)

    webhook = (n8n_webhook if n8n_webhook is not None
               else os.getenv("N8N_ACTION_WEBHOOK_URL")
               or os.getenv("NOTIFY_WEBHOOK_URL", ""))
    meta = {
        "generated": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sources": [Path(p).name for p in paths],
        "n8n_webhook": webhook,
    }
    html = render_dashboard(sections, meta=meta)

    out_path = Path(out) if out else REPORT_DIR / "dashboard.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"[✓] Xuất dashboard: {out_path}  ({len(df)} bài, "
          f"{df['platform'].nunique()} nền tảng)")
    return out_path
