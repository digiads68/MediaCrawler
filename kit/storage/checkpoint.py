# -*- coding: utf-8 -*-
"""
Checkpoint crawl tăng dần (Tier 2) — nhớ post đã thấy theo (platform, keyword).

Mục tiêu: lần chạy sau trên cùng keyword chỉ xử lý post MỚI (dedup theo id),
giúp monitoring định kỳ rẻ hơn mà KHÔNG tăng tải crawler.

Backend: Supabase (bảng crawl_checkpoints, xem schema/003_checkpoints.sql)
hoặc SQLite fallback (mặc định database/kit_checkpoints.db) khi thiếu cấu hình.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

logger = logging.getLogger(__name__)

SQLITE_PATH_DEFAULT = Path("database") / "kit_checkpoints.db"

# Cột id bài viết theo từng nền tảng (dò cột đầu tiên có mặt)
ID_COLUMNS = ["aweme_id", "note_id", "video_id", "post_id", "id",
              "aweme_url", "note_url", "video_url"]


class CheckpointStore(Protocol):
    """Giao diện chung cho backend checkpoint."""

    def seen_ids(self, platform: str, keyword: str) -> set[str]: ...
    def max_ts(self, platform: str, keyword: str) -> str | None: ...
    def update(self, platform: str, keyword: str, new_ids: list[str],
               max_ts: str | None = None) -> None: ...


class SqliteCheckpoint:
    """Checkpoint SQLite — không cần dịch vụ ngoài, hợp chạy local/test."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.path = Path(db_path) if db_path else SQLITE_PATH_DEFAULT
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.execute("""create table if not exists seen_posts (
                platform text not null, keyword text not null,
                post_id text not null, added_ts text default (datetime('now')),
                primary key (platform, keyword, post_id))""")
            c.execute("""create table if not exists checkpoint_meta (
                platform text not null, keyword text not null,
                max_ts text, primary key (platform, keyword))""")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def seen_ids(self, platform: str, keyword: str) -> set[str]:
        """Tập post_id đã thấy của (platform, keyword)."""
        with self._conn() as c:
            rows = c.execute(
                "select post_id from seen_posts where platform=? and keyword=?",
                (platform, keyword)).fetchall()
        return {r[0] for r in rows}

    def max_ts(self, platform: str, keyword: str) -> str | None:
        """Mốc thời gian bài mới nhất đã xử lý (ISO) hoặc None."""
        with self._conn() as c:
            row = c.execute(
                "select max_ts from checkpoint_meta where platform=? and keyword=?",
                (platform, keyword)).fetchone()
        return row[0] if row else None

    def update(self, platform: str, keyword: str, new_ids: list[str],
               max_ts: str | None = None) -> None:
        """Ghi thêm post mới + cập nhật mốc thời gian."""
        with self._conn() as c:
            c.executemany(
                "insert or ignore into seen_posts(platform, keyword, post_id) "
                "values (?,?,?)",
                [(platform, keyword, pid) for pid in new_ids])
            if max_ts:
                c.execute(
                    "insert into checkpoint_meta(platform, keyword, max_ts) "
                    "values (?,?,?) on conflict(platform, keyword) "
                    "do update set max_ts=excluded.max_ts",
                    (platform, keyword, max_ts))


class SupabaseCheckpoint:
    """Checkpoint trên Supabase (bảng crawl_checkpoints) — dùng cho server."""

    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            from supabase import create_client
            client = create_client(os.environ["SUPABASE_URL"],
                                   os.environ["SUPABASE_KEY"])
        self.client = client

    def seen_ids(self, platform: str, keyword: str) -> set[str]:
        res = (self.client.table("crawl_checkpoints")
               .select("post_id").eq("platform", platform)
               .eq("keyword", keyword).execute())
        return {r["post_id"] for r in (res.data or [])}

    def max_ts(self, platform: str, keyword: str) -> str | None:
        res = (self.client.table("crawl_checkpoints")
               .select("added_ts").eq("platform", platform).eq("keyword", keyword)
               .order("added_ts", desc=True).limit(1).execute())
        return res.data[0]["added_ts"] if res.data else None

    def update(self, platform: str, keyword: str, new_ids: list[str],
               max_ts: str | None = None) -> None:
        rows = [{"platform": platform, "keyword": keyword, "post_id": pid}
                for pid in new_ids]
        if rows:
            (self.client.table("crawl_checkpoints")
             .upsert(rows, on_conflict="platform,keyword,post_id").execute())


def make_checkpoint_store(db_path: str | Path | None = None) -> CheckpointStore:
    """Chọn backend: Supabase nếu đủ env, ngược lại SQLite fallback."""
    if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY") and db_path is None:
        try:
            return SupabaseCheckpoint()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Supabase checkpoint lỗi (%s) — dùng SQLite.", exc)
    return SqliteCheckpoint(db_path)


def detect_id_column(df: pd.DataFrame) -> str | None:
    """Dò cột id bài viết đầu tiên có trong DataFrame."""
    return next((c for c in ID_COLUMNS if c in df.columns), None)


def filter_new_posts(df: pd.DataFrame, store: CheckpointStore, platform: str,
                     keyword: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Lọc bỏ post đã thấy — trả (df_chỉ_post_mới, danh_sách_id_mới).

    Không tìm được cột id -> trả nguyên df (cảnh báo, không chặn job).
    """
    id_col = detect_id_column(df)
    if id_col is None:
        logger.warning("Không dò được cột id bài — bỏ qua dedup.")
        return df, []
    ids = df[id_col].astype(str)
    seen = store.seen_ids(platform, keyword)
    mask = ~ids.isin(seen)
    new_df = df[mask].copy()
    new_ids = ids[mask].dropna().unique().tolist()
    print(f"[✓] Checkpoint: {len(df) - len(new_df)} post cũ bỏ qua, "
          f"{len(new_df)} post mới.")
    return new_df, new_ids


def commit_checkpoint(df_new: pd.DataFrame, new_ids: list[str],
                      store: CheckpointStore, platform: str, keyword: str) -> None:
    """Cập nhật checkpoint sau khi xử lý xong post mới."""
    if not new_ids:
        return
    max_ts = None
    if "created_at" in df_new.columns and df_new["created_at"].notna().any():
        max_ts = pd.Timestamp(df_new["created_at"].max()).isoformat()
    store.update(platform, keyword, new_ids, max_ts)
