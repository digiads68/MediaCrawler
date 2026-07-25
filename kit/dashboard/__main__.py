# -*- coding: utf-8 -*-
"""
CLI: sinh dashboard đa nền tảng từ nhiều file raw MediaCrawler.

    python -m kit.dashboard <file1> [file2 ...] [-o reports/dashboard.html]
                            [--n8n https://.../webhook/mc-action]

Ví dụ:
    python -m kit.dashboard data/douyin/search.xlsx data/bili/search.xlsx \
        -o reports/dashboard.html
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

from kit.dashboard.build import build_dashboard  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="kit.dashboard",
        description="Sinh dashboard nghiên cứu trend/đối thủ đa nền tảng.")
    ap.add_argument("files", nargs="+", help="File raw (.xlsx/.jsonl/.csv)")
    ap.add_argument("-o", "--out", default="reports/dashboard.html",
                    help="File HTML đầu ra (mặc định reports/dashboard.html)")
    ap.add_argument("--n8n", default=None,
                    help="URL webhook n8n mặc định nhúng vào trang")
    args = ap.parse_args(argv)

    missing = [f for f in args.files if not Path(f).exists()]
    if missing:
        ap.error("Không thấy file: " + ", ".join(missing))

    out = build_dashboard(args.files, out=args.out, n8n_webhook=args.n8n)
    print(f"    → Mở bằng trình duyệt: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
