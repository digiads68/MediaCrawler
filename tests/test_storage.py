# -*- coding: utf-8 -*-
"""Test kit/storage/supabase_writer — build payload + dry-run + mock client."""

from __future__ import annotations

import pandas as pd
import pytest

from kit.storage.supabase_writer import (
    SupabaseWriter,
    build_angle_rows,
    build_koc_rows,
    build_sov_rows,
    build_trend_rows,
)


@pytest.fixture
def trend_df() -> pd.DataFrame:
    return pd.DataFrame({
        "title": ["bài A", "bài B"],
        "format": ["review/測評", "khác"],
        "source_keyword": ["护肤", "精华"],
        "liked_count": [100.0, 50.0],
        "collected_count": [30.0, 5.0],
        "share_count": [7.0, 1.0],
        "trend_score": [88.5, 12.3],
        "aweme_url": ["https://v.douyin.com/a", ""],
        "note_url": ["", "https://xhs.com/b"],
    })


def test_build_trend_rows_map_cot(trend_df):
    rows = build_trend_rows(trend_df, run_id="r1", platform="dy")
    assert len(rows) == 2
    r = rows[0]
    assert r["run_id"] == "r1" and r["platform"] == "dy"
    assert r["liked"] == 100 and r["collect"] == 30
    assert r["comment"] == 0            # cột thiếu -> 0, không crash
    assert r["url"] == "https://v.douyin.com/a"
    assert rows[1]["url"] == "https://xhs.com/b"   # fallback note_url


def test_build_koc_rows_an_danh():
    df = pd.DataFrame({
        "creator": ["hash_1"], "nickname": ["用户***"], "so_video": [8],
        "eng_tb": [123.4], "do_deu": [0.62], "velocity": [1.5],
        "diem_tong": [77.0], "verdict": ["ký ngay"], "rising": [True],
    })
    r = build_koc_rows(df, run_id=None)[0]
    assert r["creator_hash"] == "hash_1"
    assert r["rising"] is True and r["verdict"] == "ký ngay"


def test_build_angle_rows_flatten_metrics():
    rec = {"angle_id": "kw_1", "platform": "dy", "source_keyword": "护肤",
           "hook": "h", "format": "pov/skit", "pain_or_desire": "", "cta_observed": "",
           "sound_ref": "", "metrics": {"like": 10, "comment": 2, "share": 1,
                                        "collect": 5}, "lang": "zh"}
    r = build_angle_rows([rec])[0]
    assert r["angle_id"] == "kw_1" and r["like"] == 10 and r["collect"] == 5
    assert r["status"] == "new"


def test_build_sov_rows():
    df = pd.DataFrame({"week": ["2026-W29"], "brand": ["BrandA"],
                       "so_bai": [12], "eng": [3456], "sov_pct": [41.2]})
    r = build_sov_rows(df)[0]
    assert r == {"week": "2026-W29", "brand": "BrandA", "so_bai": 12,
                 "eng": 3456, "sov_pct": 41.2}


def test_dry_run_khong_goi_mang(trend_df, capsys):
    w = SupabaseWriter(dry_run=True)          # không có URL/KEY vẫn chạy được
    n = w.upsert_trend_posts(trend_df)
    assert n == 2
    assert "sẽ ghi 2 dòng" in capsys.readouterr().out
    assert w.start_run("dy", "search") is None


class _FakeQuery:
    def __init__(self, log: list, table: str):
        self.log, self.table = log, table

    def upsert(self, rows, on_conflict=None):
        self.log.append(("upsert", self.table, len(rows), on_conflict))
        return self

    def insert(self, rows):
        self.log.append(("insert", self.table,
                         len(rows) if isinstance(rows, list) else 1, None))
        return self

    def update(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def execute(self):
        return type("Res", (), {"data": [{"id": "run-1"}]})()


class _FakeSupabase:
    def __init__(self):
        self.log: list = []

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(self.log, name)


def test_upsert_voi_mock_client_dung_khoa_tu_nhien(trend_df):
    fake = _FakeSupabase()
    w = SupabaseWriter(client=fake)
    run_id = w.start_run("dy", "search", "护肤")
    assert run_id == "run-1"
    w.upsert_trend_posts(trend_df, run_id)
    w.upsert_sov(pd.DataFrame({"week": ["2026-W29"], "brand": ["A"],
                               "so_bai": [1], "eng": [2], "sov_pct": [100.0]}))
    ops = [(op, tbl, conflict) for op, tbl, _n, conflict in fake.log]
    assert ("insert", "crawl_runs", None) in ops
    assert ("insert", "trend_posts", None) in ops
    assert ("upsert", "sov_weekly", "week,brand") in ops


def test_batch_chia_lo_500():
    fake = _FakeSupabase()
    w = SupabaseWriter(client=fake)
    big = pd.DataFrame({"week": [f"2026-W{i:02d}" for i in range(1, 53)] * 12,
                        "brand": [f"B{i}" for i in range(624)],
                        "so_bai": 1, "eng": 1, "sov_pct": 1.0})
    w.upsert_sov(big)
    sizes = [n for op, tbl, n, _ in fake.log if tbl == "sov_weekly"]
    assert sizes == [500, 124]
