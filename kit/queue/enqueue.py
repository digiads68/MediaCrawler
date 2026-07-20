# -*- coding: utf-8 -*-
"""
CLI đẩy job crawl_and_analyze vào hàng đợi arq.

Ví dụ:
    python kit/queue/enqueue.py dy search "护肤,精华" --analyze trend \
        --to supabase --notify --max-notes 100
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from arq import create_pool  # noqa: E402
from arq.connections import RedisSettings  # noqa: E402

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")


def _parse(argv: list[str]) -> tuple[str, str, str, dict]:
    """Đọc đối số CLI -> (platform, crawler_type, keywords, options)."""
    if len(argv) < 3:
        print(__doc__)
        sys.exit(1)
    platform, crawler_type, keywords = argv[0], argv[1], argv[2]
    opts: dict = {}
    i = 3
    while i < len(argv):
        a = argv[i]
        if a == "--analyze":
            opts["analyze"] = argv[i + 1]; i += 2
        elif a == "--to" and i + 1 < len(argv) and argv[i + 1] == "supabase":
            opts["to_supabase"] = True; i += 2
        elif a == "--notify":
            opts["notify"] = True; i += 1
        elif a == "--dry-run":
            opts["dry_run"] = True; i += 1
        elif a == "--brand-map":
            opts["brand_map"] = argv[i + 1]; i += 2
        elif a == "--max-notes":
            opts["max_notes_count"] = int(argv[i + 1]); i += 2
        else:
            print(f"Đối số không hợp lệ: {a}"); sys.exit(1)
    return platform, crawler_type, keywords, opts


async def enqueue(platform: str, crawler_type: str, keywords: str,
                  options: dict) -> str:
    """Đẩy 1 job vào hàng đợi, trả job_id."""
    pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    try:
        job = await pool.enqueue_job("crawl_and_analyze", platform,
                                     crawler_type, keywords, options)
        print(f"[✓] Đã xếp job {job.job_id}: {platform}/{crawler_type} '{keywords}' "
              f"→ {options.get('analyze', 'trend')}")
        return job.job_id
    finally:
        await pool.aclose()


def main() -> None:
    platform, crawler_type, keywords, opts = _parse(sys.argv[1:])
    asyncio.run(enqueue(platform, crawler_type, keywords, opts))


if __name__ == "__main__":
    main()
