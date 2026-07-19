# -*- coding: utf-8 -*-
"""Test kit/storage/checkpoint — SQLite tạm, chứng minh lần 2 skip post cũ."""

from __future__ import annotations

import pandas as pd
import pytest

from kit.storage.checkpoint import (
    SqliteCheckpoint,
    commit_checkpoint,
    detect_id_column,
    filter_new_posts,
    make_checkpoint_store,
)


@pytest.fixture
def store(tmp_path) -> SqliteCheckpoint:
    return SqliteCheckpoint(tmp_path / "ckpt.db")


def _df(ids: list[str]) -> pd.DataFrame:
    return pd.DataFrame({
        "aweme_id": ids,
        "title": [f"bài {i}" for i in ids],
        "created_at": pd.date_range("2026-07-01", periods=len(ids), freq="D"),
    })


def test_lan_dau_xu_ly_het_lan_hai_skip_post_cu(store):
    """Nghiệm thu PROMPT 7: lần chạy 2 trên cùng keyword xử lý ÍT dòng hơn."""
    # Lần 1: 3 post đều mới
    df1 = _df(["a", "b", "c"])
    new1, ids1 = filter_new_posts(df1, store, "dy", "护肤")
    assert len(new1) == 3 and set(ids1) == {"a", "b", "c"}
    commit_checkpoint(new1, ids1, store, "dy", "护肤")

    # Lần 2: 2 post cũ + 1 post mới -> chỉ còn 1
    df2 = _df(["b", "c", "d"])
    new2, ids2 = filter_new_posts(df2, store, "dy", "护肤")
    assert len(new2) == 1 and ids2 == ["d"]
    assert new2["aweme_id"].tolist() == ["d"]
    commit_checkpoint(new2, ids2, store, "dy", "护肤")

    # Lần 3: toàn post cũ -> 0 dòng
    new3, ids3 = filter_new_posts(_df(["a", "d"]), store, "dy", "护肤")
    assert len(new3) == 0 and ids3 == []


def test_checkpoint_tach_theo_platform_keyword(store):
    df = _df(["x"])
    new, ids = filter_new_posts(df, store, "dy", "kw1")
    commit_checkpoint(new, ids, store, "dy", "kw1")
    # Cùng id nhưng keyword khác -> vẫn coi là mới
    new2, _ = filter_new_posts(df, store, "dy", "kw2")
    assert len(new2) == 1
    # Cùng keyword -> đã thấy
    new3, _ = filter_new_posts(df, store, "dy", "kw1")
    assert len(new3) == 0


def test_max_ts_duoc_cap_nhat(store):
    df = _df(["a", "b"])
    new, ids = filter_new_posts(df, store, "dy", "kw")
    commit_checkpoint(new, ids, store, "dy", "kw")
    assert store.max_ts("dy", "kw").startswith("2026-07-02")


def test_update_idempotent_khong_loi_khi_trung(store):
    store.update("dy", "kw", ["a", "b"])
    store.update("dy", "kw", ["b", "c"])   # trùng "b" — insert or ignore
    assert store.seen_ids("dy", "kw") == {"a", "b", "c"}


def test_detect_id_column_uu_tien_dung_cot():
    assert detect_id_column(pd.DataFrame({"note_id": [1], "title": ["x"]})) == "note_id"
    assert detect_id_column(pd.DataFrame({"title": ["x"]})) is None


def test_khong_co_cot_id_tra_nguyen_df(store):
    df = pd.DataFrame({"title": ["a", "b"]})
    new, ids = filter_new_posts(df, store, "dy", "kw")
    assert len(new) == 2 and ids == []


def test_make_store_fallback_sqlite(monkeypatch, tmp_path):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    s = make_checkpoint_store(tmp_path / "x.db")
    assert isinstance(s, SqliteCheckpoint)


def test_tich_hop_run_analyzer_incremental(tmp_path, monkeypatch):
    """Chạy _run_analyzer 2 lần cùng file: lần 2 skip toàn bộ."""
    from kit.queue.tasks import _run_analyzer

    df = pd.DataFrame({
        "aweme_id": ["p1", "p2"],
        "title": ["7天变化", "开箱"], "desc": ["前后", "到货"],
        "liked_count": ["100", "50"], "comment_count": ["5", "2"],
        "share_count": ["1", "0"], "collected_count": ["20", "3"],
        "create_time": [1767600000, 1767700000],
        "source_keyword": ["kw", "kw"],
    })
    f = tmp_path / "search_kw.xlsx"
    df.to_excel(f, index=False)
    monkeypatch.chdir(tmp_path)
    db = tmp_path / "ckpt.db"

    r1 = _run_analyzer("trend", str(f), incremental=True,
                       checkpoint_db=str(db), platform="dy", keyword="kw")
    assert r1["rows"] == 2
    r2 = _run_analyzer("trend", str(f), incremental=True,
                       checkpoint_db=str(db), platform="dy", keyword="kw")
    assert r2["rows"] == 0 and r2.get("skipped") is True
