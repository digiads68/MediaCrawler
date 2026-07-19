# -*- coding: utf-8 -*-
"""
Cấu hình arq worker (Tier 2).

Chạy:  arq kit.queue.worker.WorkerSettings
Cần REDIS_URL trong .env (mặc định redis://127.0.0.1:6379/0).

Ranh giới: max_jobs=1 — job chạy TUẦN TỰ, không tăng tải crawler.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from arq.connections import RedisSettings  # noqa: E402

from kit.queue.tasks import crawl_and_analyze  # noqa: E402

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")


class WorkerSettings:
    """Cài đặt arq worker — tuần tự, timeout dài cho crawl."""

    functions = [crawl_and_analyze]
    max_jobs = 1                    # tôn trọng ranh giới: 1 job crawl một lúc
    job_timeout = 4000              # giây — crawl + phân tích
    max_tries = 1                   # không tự retry job crawl (tránh dồn tải)
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
