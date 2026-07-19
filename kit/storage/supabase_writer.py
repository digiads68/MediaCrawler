# -*- coding: utf-8 -*-
"""
Ghi kết quả analyzer vào Supabase (Tier 1 — kho dữ liệu dashboard).

Đọc SUPABASE_URL/SUPABASE_KEY từ env (service_role, chỉ dùng backend).
Upsert theo khoá tự nhiên (angle_id; (week,brand); creator_hash) — idempotent,
chạy lại không nhân đôi. Batch ~500 dòng/lần. Chế độ dry-run chỉ in số dòng
sẽ ghi, không gọi mạng — dùng cho test/kiểm tra payload.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

BATCH_SIZE = 500

# Cột URL ưu tiên lấy làm link bài (tuỳ nền tảng)
_URL_COLS = ["aweme_url", "note_url", "video_url", "url"]


def _pick_url(row: pd.Series) -> str:
    """Chọn URL đầu tiên có giá trị trong các cột URL đã biết."""
    for c in _URL_COLS:
        v = row.get(c)
        if isinstance(v, str) and v:
            return v
    return ""


def _iso(v: Any) -> str | None:
    """Datetime/Timestamp -> chuỗi ISO (None nếu thiếu)."""
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return None
    return pd.Timestamp(v).isoformat()


def _num(v: Any, default: float = 0) -> float:
    """Ép số an toàn (NaN/None -> default)."""
    try:
        f = float(v)
        return default if pd.isna(f) else f
    except (TypeError, ValueError):
        return default


# ----------------------------------------------------------------------------
# Build payload (hàm thuần — test không cần client)
# ----------------------------------------------------------------------------

def build_trend_rows(df: pd.DataFrame, run_id: str | None,
                     platform: str = "unknown") -> list[dict]:
    """DataFrame trend (có trend_score) -> payload bảng trend_posts."""
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "run_id": run_id,
            "platform": str(r.get("platform", platform) or platform),
            "source_keyword": str(r.get("source_keyword", "") or ""),
            "title": str(r.get("title", "") or ""),
            "format": str(r.get("format", "khác") or "khác"),
            "liked": int(_num(r.get("liked_count"))),
            "comment": int(_num(r.get("comment_count"))),
            "share": int(_num(r.get("share_count"))),
            "collect": int(_num(r.get("collected_count"))),
            "created_at": _iso(r.get("created_at")),
            "url": _pick_url(r),
            "trend_score": round(_num(r.get("trend_score")), 2),
        })
    return rows


def build_koc_rows(df: pd.DataFrame, run_id: str | None) -> list[dict]:
    """DataFrame koc_scorecard -> payload bảng koc_scores (creator đã ẩn danh)."""
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "run_id": run_id,
            "creator_hash": str(r.get("creator", "") or ""),
            "nickname_masked": str(r.get("nickname", "") or ""),
            "so_video": int(_num(r.get("so_video"))),
            "eng_tb": _num(r.get("eng_tb")),
            "do_deu": _num(r.get("do_deu")),
            "velocity": _num(r.get("velocity"), 1),
            "diem_tong": _num(r.get("diem_tong")),
            "verdict": str(r.get("verdict", "") or ""),
            "rising": bool(r.get("rising", False)),
        })
    return rows


def build_angle_rows(records: list[dict]) -> list[dict]:
    """Bản ghi angle_library.jsonl -> payload bảng angle_library (flatten metrics)."""
    rows = []
    for rec in records:
        m = rec.get("metrics") or {}
        rows.append({
            "angle_id": rec["angle_id"],
            "platform": rec.get("platform", "dy"),
            "source_keyword": rec.get("source_keyword", ""),
            "hook": rec.get("hook", ""),
            "format": rec.get("format", "khác"),
            "pain_or_desire": rec.get("pain_or_desire", ""),
            "cta_observed": rec.get("cta_observed", ""),
            "sound_ref": rec.get("sound_ref", ""),
            "like": int(_num(m.get("like"))),
            "comment": int(_num(m.get("comment"))),
            "share": int(_num(m.get("share"))),
            "collect": int(_num(m.get("collect"))),
            "lang": rec.get("lang", "zh"),
            "status": rec.get("status", "new"),
        })
    return rows


def build_sov_rows(df: pd.DataFrame) -> list[dict]:
    """DataFrame sov tuần -> payload bảng sov_weekly."""
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "week": str(r.get("week", "") or ""),
            "brand": str(r.get("brand", "") or ""),
            "so_bai": int(_num(r.get("so_bai"))),
            "eng": int(_num(r.get("eng"))),
            "sov_pct": _num(r.get("sov_pct")),
        })
    return rows


def build_price_rows(df: pd.DataFrame, run_id: str | None) -> list[dict]:
    """DataFrame price_intel -> payload bảng price_intel."""
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "run_id": run_id,
            "competitor": str(r.get("competitor", "") or ""),
            "price_text": str(r.get("gia_phat_hien", "") or ""),
            "promo_text": str(r.get("moi_km", "") or ""),
            "source_keyword": str(r.get("nguon_keyword", "") or ""),
            "eng": int(_num(r.get("eng_total"))),
        })
    return rows


# ----------------------------------------------------------------------------
# Writer
# ----------------------------------------------------------------------------

class SupabaseWriter:
    """Ghi payload vào Supabase — batch + upsert idempotent + dry-run."""

    def __init__(self, url: str | None = None, key: str | None = None,
                 client: Any | None = None, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self._client = client
        self._url = url or os.getenv("SUPABASE_URL", "")
        self._key = key or os.getenv("SUPABASE_KEY", "")

    @property
    def client(self) -> Any:
        """Khởi tạo client trễ — dry-run không bao giờ chạm tới đây."""
        if self._client is None:
            if not self._url or not self._key:
                raise RuntimeError("Thiếu SUPABASE_URL/SUPABASE_KEY trong môi trường.")
            from supabase import create_client
            self._client = create_client(self._url, self._key)
        return self._client

    # -- nhật ký run ----------------------------------------------------------
    def start_run(self, platform: str, crawler_type: str, keywords: str = "") -> str | None:
        """Mở 1 crawl_run, trả run_id (None nếu dry-run/lỗi)."""
        if self.dry_run:
            print(f"[dry-run] start_run({platform}, {crawler_type})")
            return None
        try:
            res = (self.client.table("crawl_runs")
                   .insert({"platform": platform, "crawler_type": crawler_type,
                            "keywords": keywords})
                   .execute())
            return res.data[0]["id"]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Không mở được crawl_run: %s", exc)
            return None

    def finish_run(self, run_id: str | None, note_count: int = 0,
                   status: str = "done") -> None:
        """Đóng crawl_run với số dòng và trạng thái."""
        if self.dry_run or not run_id:
            return
        try:
            (self.client.table("crawl_runs")
             .update({"finished_at": "now()", "note_count": note_count,
                      "status": status})
             .eq("id", run_id).execute())
        except Exception as exc:  # noqa: BLE001
            logger.warning("Không đóng được crawl_run %s: %s", run_id, exc)

    # -- upsert ----------------------------------------------------------------
    def _upsert(self, table: str, rows: list[dict],
                on_conflict: str | None = None) -> int:
        """Upsert theo lô BATCH_SIZE; lỗi 1 lô chỉ log, không crash job."""
        if self.dry_run:
            print(f"[dry-run] sẽ ghi {len(rows)} dòng vào bảng {table}"
                  + (f" (on_conflict={on_conflict})" if on_conflict else ""))
            return len(rows)
        written = 0
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            try:
                q = self.client.table(table)
                if on_conflict:
                    q.upsert(batch, on_conflict=on_conflict).execute()
                else:
                    q.insert(batch).execute()
                written += len(batch)
            except Exception as exc:  # noqa: BLE001
                logger.error("Ghi bảng %s lô %s lỗi: %s", table, i // BATCH_SIZE, exc)
        print(f"[✓] Supabase: ghi {written}/{len(rows)} dòng vào {table}")
        return written

    def upsert_trend_posts(self, df: pd.DataFrame, run_id: str | None = None,
                           platform: str = "unknown") -> int:
        """Ghi top post trend (CS1) — insert theo run."""
        return self._upsert("trend_posts", build_trend_rows(df, run_id, platform))

    def upsert_koc(self, df: pd.DataFrame, run_id: str | None = None) -> int:
        """Ghi scorecard KOC (CS3/CS9) — upsert theo creator_hash."""
        return self._upsert("koc_scores", build_koc_rows(df, run_id),
                            on_conflict="creator_hash")

    def upsert_angles(self, records: list[dict]) -> int:
        """Ghi angle library (CS5) — upsert theo angle_id."""
        return self._upsert("angle_library", build_angle_rows(records),
                            on_conflict="angle_id")

    def upsert_sov(self, df: pd.DataFrame) -> int:
        """Ghi SOV tuần (CS11) — upsert theo (week, brand)."""
        return self._upsert("sov_weekly", build_sov_rows(df),
                            on_conflict="week,brand")

    def upsert_price(self, df: pd.DataFrame, run_id: str | None = None) -> int:
        """Ghi tình báo giá (CS8) — insert theo run."""
        return self._upsert("price_intel", build_price_rows(df, run_id))
