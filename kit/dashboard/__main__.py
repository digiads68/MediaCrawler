# -*- coding: utf-8 -*-
"""
CLI: sinh dashboard chuyên sâu từ file raw MediaCrawler.

    python -m kit.dashboard [loại] <file...> [-o out.html] [--n8n URL]

`loại` (không bắt buộc, mặc định `auto`):
    auto      tự chọn theo mode cào có trong dữ liệu
    search    Trend Radar — săn trend & ý tưởng content   (--type search)
    creator   Channel Audit — soi kênh đối thủ            (--type creator)
    video     Video Teardown — mổ xẻ video & bình luận    (--type detail)
    overview  Tổng quan chéo nền tảng
    all       sinh tất cả loại phù hợp + trang index

Ví dụ:
    python -m kit.dashboard search data/douyin/search_x.xlsx
    python -m kit.dashboard creator data/douyin/creator_x.xlsx
    python -m kit.dashboard all data/douyin/*.xlsx data/xhs/*.xlsx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Cho phép chạy trực tiếp không cần cài package.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from kit.dashboard.build import build_all, build_dashboard  # noqa: E402
from kit.dashboard.profiles import PROFILES  # noqa: E402

CHOICES = ("auto", "all", *PROFILES)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="kit.dashboard",
        description="Sinh dashboard chuyên sâu theo mode cào của MediaCrawler.",
        epilog="Loại: " + " | ".join(CHOICES))
    ap.add_argument("args", nargs="+",
                    help="[loại] rồi danh sách file raw (.xlsx/.jsonl/.csv)")
    ap.add_argument("-o", "--out", default=None,
                    help="File HTML ra (1 loại) — mặc định reports/dashboard_<loại>.html")
    ap.add_argument("--out-dir", default=None,
                    help="Thư mục ra khi dùng loại 'all' (mặc định reports/)")
    ap.add_argument("--n8n", default=None,
                    help="URL webhook n8n mặc định nhúng vào trang")
    ns = ap.parse_args(argv)

    # Tham số đầu là loại nếu nó khớp danh sách và không phải file tồn tại.
    first = ns.args[0]
    if first in CHOICES and not Path(first).exists():
        profile, files = first, ns.args[1:]
    else:
        profile, files = "auto", ns.args
    if not files:
        ap.error("Thiếu file dữ liệu.")
    missing = [f for f in files if not Path(f).exists()]
    if missing:
        ap.error("Không thấy file: " + ", ".join(missing))

    if profile == "all":
        made = build_all(files, out_dir=ns.out_dir, n8n_webhook=ns.n8n)
        print(f"    → Mở trang điều hướng: {made['index']}")
        return 0

    out = build_dashboard(files, profile=profile, out=ns.out, n8n_webhook=ns.n8n)
    print(f"    → Mở bằng trình duyệt: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
