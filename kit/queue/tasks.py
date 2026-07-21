# -*- coding: utf-8 -*-
"""
Task arq: crawl qua REST API MediaCrawler rồi phân tích/lưu/notify.

Ranh giới: KHÔNG tăng tải crawler — job chạy tuần tự (max_jobs=1 ở worker),
poll status lịch sự, không retry dồn dập. Mọi log tiếng Việt.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_BASE_DEFAULT = os.getenv("MEDIACRAWLER_API", "http://127.0.0.1:8080")
POLL_INTERVAL_S = 15.0
CRAWL_TIMEOUT_S = 3600.0

# Lệnh analyzer được phép chạy sau crawl
ANALYZE_COMMANDS = {"trend", "insight", "koc", "opportunity", "seasonal",
                    "price", "sov", "angle"}


def _run_analyzer(command: str, file_path: str, to_supabase: bool = False,
                  dry_run: bool = False, notify: bool = False,
                  brand_map: str | None = None, incremental: bool = False,
                  checkpoint_db: str | None = None, platform: str = "",
                  keyword: str = "") -> dict[str, Any]:
    """Chạy 1 lệnh analyzer trên file dữ liệu (đồng bộ, pandas)."""
    import json

    import pandas as pd

    from kit.analyzer import mediacrawler_analyzer as an

    if command not in ANALYZE_COMMANDS:
        raise ValueError(f"Lệnh phân tích không hợp lệ: {command}")
    df = an.load(file_path)

    # Crawl tăng dần: chỉ xử lý post mới, cập nhật checkpoint sau khi xong
    ckpt_store = None
    ckpt_new_ids: list[str] = []
    if incremental:
        from kit.storage.checkpoint import filter_new_posts, make_checkpoint_store
        ckpt_store = make_checkpoint_store(checkpoint_db)
        df, ckpt_new_ids = filter_new_posts(df, ckpt_store, platform, keyword)
        if df.empty:
            print("[✓] Không có post mới — bỏ qua phân tích.")
            return {"command": command, "rows": 0, "file": file_path,
                    "skipped": True}

    writer = None
    if to_supabase:
        from kit.storage.supabase_writer import SupabaseWriter
        writer = SupabaseWriter(dry_run=dry_run)

    # Kết quả analyzer + danh sách file Excel đã xuất (để sinh HTML + trả về UI).
    # report_data: object truyền cho tầng báo cáo (dict cho trend, DataFrame khác).
    rows = 0
    report_data: Any = None
    xlsx_files: list[str] = []
    if command == "trend":
        res = an.trend_radar(df)
        rows = len(res["top_posts"])
        report_data = res
        xlsx_files = ["CS1_trend_top_posts.xlsx", "CS1_trend_formats.xlsx"]
        if len(res.get("sounds", [])):
            xlsx_files.append("CS10_sound_watchlist.xlsx")
        if writer:
            writer.upsert_trend_posts(res["top_posts"])
        if notify:
            from kit.webhook import notify_trend_brief
            notify_trend_brief(f"Trend radar xong: {rows} bài top.")
    elif command == "insight":
        report_data = an.comment_bank(df)
        rows = len(report_data)
        xlsx_files = ["CS2_comment_bank.xlsx"]
    elif command == "koc":
        s = an.koc_scorecard(df)
        rows = len(s)
        report_data = s
        xlsx_files = ["CS3_koc_scorecard.xlsx", "CS9_rising_creators.xlsx"]
        if writer and rows:
            writer.upsert_koc(s)
        if notify and rows:
            from kit.webhook import notify_rising_koc
            notify_rising_koc(s[s["rising"]].to_dict(orient="records"))
    elif command == "opportunity":
        report_data = an.opportunity_map(df)
        rows = len(report_data)
        xlsx_files = ["CS6_opportunity_map.xlsx"]
    elif command == "seasonal":
        report_data = an.seasonal_radar(df)
        rows = len(report_data)
        xlsx_files = ["CS7_seasonal_radar.xlsx"]
    elif command == "price":
        p = an.price_intel(df)
        rows = len(p)
        report_data = p
        xlsx_files = ["CS8_price_intel.xlsx"]
        if writer and rows:
            writer.upsert_price(p)
    elif command == "angle":
        out = an.export_angles(df)
        with open(out, encoding="utf-8") as f:
            records = [json.loads(line) for line in f if line.strip()]
        rows = len(records)
        report_data = pd.DataFrame(records) if records else pd.DataFrame()
        xlsx_files = ["angle_library.jsonl"]
        if writer:
            writer.upsert_angles(records)
    elif command == "sov":
        bm = json.loads(Path(brand_map).read_text(encoding="utf-8")) if brand_map else {}
        g = an.sov(df, bm)
        rows = len(g)
        report_data = g
        xlsx_files = ["CS11_sov_weekly.xlsx"]
        if writer and rows:
            writer.upsert_sov(g)
        if notify:
            from kit.webhook import notify_sov_updated
            notify_sov_updated()

    # Sinh báo cáo HTML tự chứa (không chặn job nếu lỗi — chỉ log cảnh báo)
    reports = list(xlsx_files)
    try:
        from kit.report import build_report
        html_path = build_report(command, report_data, df=df,
                                  meta={"keyword": keyword, "platform": platform,
                                        "source_file": Path(file_path).name})
        reports.append(html_path.name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Không sinh được báo cáo HTML (%s): %s", command, exc)

    if ckpt_store is not None:
        from kit.storage.checkpoint import commit_checkpoint
        commit_checkpoint(df, ckpt_new_ids, ckpt_store, platform, keyword)
    return {"command": command, "rows": rows, "file": file_path, "reports": reports}


async def _wait_until_idle(client: httpx.AsyncClient, poll_interval: float,
                           timeout: float) -> str:
    """Poll GET /api/crawler/status tới khi idle/error; trả trạng thái cuối."""
    waited = 0.0
    while waited < timeout:
        resp = await client.get("/api/crawler/status")
        resp.raise_for_status()
        status = resp.json().get("status", "error")
        if status in ("idle", "error"):
            return status
        await asyncio.sleep(poll_interval)
        waited += poll_interval
    return "timeout"


async def _latest_data_file(client: httpx.AsyncClient, platform: str) -> str | None:
    """Lấy đường dẫn file dữ liệu mới nhất của platform từ /api/data/files."""
    resp = await client.get("/api/data/files", params={"platform": platform})
    resp.raise_for_status()
    files = resp.json()
    if isinstance(files, dict):
        files = files.get("files", [])
    if not files:
        return None
    files = sorted(files, key=lambda f: f.get("modified_at", ""), reverse=True)
    return files[0].get("path") or files[0].get("name")


async def crawl_and_analyze(ctx: dict[str, Any], platform: str,
                            crawler_type: str = "search", keywords: str = "",
                            options: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Job chính: gọi REST crawler → chờ xong → chạy analyzer → (tuỳ chọn) Supabase/webhook.

    options: {analyze: "trend", to_supabase: bool, dry_run: bool, notify: bool,
              brand_map: str, save_option: "excel", max_notes_count: int,
              api_base: str, poll_interval: float, timeout: float}
    """
    opts = {"analyze": "trend", "to_supabase": False, "dry_run": False,
            "notify": False, "brand_map": None, "save_option": "excel",
            "max_notes_count": None, "api_base": API_BASE_DEFAULT,
            "poll_interval": POLL_INTERVAL_S, "timeout": CRAWL_TIMEOUT_S,
            "incremental": False, "checkpoint_db": None,
            **(options or {})}

    client: httpx.AsyncClient | None = ctx.get("http_client")
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(base_url=opts["api_base"], timeout=30.0)
    try:
        # 1. Khởi động crawl (giữ mặc định tải của repo — không tăng concurrency)
        body = {"platform": platform, "crawler_type": crawler_type,
                "keywords": keywords, "save_option": opts["save_option"]}
        if opts["max_notes_count"]:
            body["max_notes_count"] = opts["max_notes_count"]
        logger.info("Bắt đầu crawl %s/%s: %s", platform, crawler_type, keywords)
        resp = await client.post("/api/crawler/start", json=body)
        resp.raise_for_status()

        # 2. Chờ crawler idle
        status = await _wait_until_idle(client, opts["poll_interval"], opts["timeout"])
        if status != "idle":
            logger.error("Crawl kết thúc bất thường: %s", status)
            return {"status": status, "platform": platform, "keywords": keywords}

        # 3. Lấy file dữ liệu mới nhất
        data_file = await _latest_data_file(client, platform)
        if not data_file:
            logger.warning("Không thấy file dữ liệu cho %s.", platform)
            return {"status": "no_data", "platform": platform}

        # 4. Phân tích (chạy sync trong thread để không chặn event loop)
        result = await asyncio.to_thread(
            _run_analyzer, opts["analyze"], data_file,
            opts["to_supabase"], opts["dry_run"], opts["notify"],
            opts["brand_map"], opts["incremental"], opts["checkpoint_db"],
            platform, keywords)
        logger.info("Job xong: %s — %s dòng.", result["command"], result["rows"])
        return {"status": "ok", **result}
    finally:
        if own_client:
            await client.aclose()
