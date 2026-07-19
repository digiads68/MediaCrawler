# -*- coding: utf-8 -*-
"""Test 11 nhánh analyzer (trend/insight/koc/opportunity/seasonal/price/sov/angle)."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from kit.analyzer import mediacrawler_analyzer as an


@pytest.fixture
def df(synthetic_search_df, tmp_path, monkeypatch):
    """Chuẩn hoá fixture + chdir tmp để reports/ không rơi vào repo."""
    monkeypatch.chdir(tmp_path)
    return an.normalize(synthetic_search_df)


# --- CS1 + CS10 · trend ------------------------------------------------------

def test_trend_radar_cot_va_thu_tu(df):
    res = an.trend_radar(df, top=5)
    top = res["top_posts"]
    assert len(top) == 5
    assert "trend_score" in top.columns
    # sắp giảm dần theo trend_score
    scores = top["trend_score"].tolist()
    assert scores == sorted(scores, reverse=True)
    # trend_score max = 100 (bài dẫn đầu mọi trục)
    assert scores[0] == pytest.approx(100.0)


def test_trend_radar_formats_va_sound(df):
    res = an.trend_radar(df)
    assert set(res["formats"].columns) == {"format", "so_bai", "diem_tb", "save_tb"}
    # sound lặp >= 2 lần phải vào watchlist (CS10)
    assert len(res["sounds"]) == 1
    assert res["sounds"].iloc[0]["music_download_url"] == "bgm_trend_1"
    assert res["sounds"].iloc[0]["so_video"] == 9


# --- CS2 · insight -----------------------------------------------------------

def test_comment_bank_loc_rac_va_dedupe(synthetic_comment_df, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    d = an.comment_bank(synthetic_comment_df, min_like=1, top=100)
    contents = d["content"].tolist()
    assert "用了一周真的有效果" in contents
    assert contents.count("用了一周真的有效果") == 1     # dedupe
    assert "😀😀😀" not in contents                       # lọc emoji
    assert "ab" not in contents                           # lọc quá ngắn
    # xếp theo like giảm dần
    likes = d["like_count"].tolist()
    assert likes == sorted(likes, reverse=True)


# --- CS3 + CS9 · koc ---------------------------------------------------------

def test_koc_scorecard_verdict_va_rising(df):
    s = an.koc_scorecard(df, min_videos=5)
    assert set(s["creator"]) == {"c_a", "c_b", "c_c"}
    a = s.set_index("creator").loc["c_a"]
    # c_a engagement tăng dần -> velocity cao nhất & rising
    assert a["velocity"] > 1.3
    assert bool(a["rising"]) is True
    assert s["verdict"].isin(["bỏ qua", "theo dõi", "ký ngay"]).all()
    # điểm tổng trong [0, 100]
    assert s["diem_tong"].between(0, 100).all()


def test_koc_scorecard_khong_du_video(df):
    s = an.koc_scorecard(df, min_videos=99)
    assert s.empty


# --- CS4 + CS6 · opportunity -------------------------------------------------

def test_opportunity_map_quadrant(df):
    g = an.opportunity_map(df)
    assert set(g.columns) == {"source_keyword", "so_bai", "eng_tb", "save_tb", "quadrant"}
    assert len(g) == 2  # 护肤, 精华
    assert g["quadrant"].str.contains("biển xanh|cạnh tranh|sa mạc|bão hoà").all()


# --- CS7 · seasonal ----------------------------------------------------------

def test_seasonal_radar_theo_tuan(df):
    g = an.seasonal_radar(df)
    assert {"week", "source_keyword", "so_bai", "eng_tong", "spike"} <= set(g.columns)
    assert g["week"].str.match(r"^\d{4}-W\d{2}$").all()
    assert g["spike"].dtype == bool


def test_seasonal_radar_thieu_create_time(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        an.seasonal_radar(pd.DataFrame({"title": ["x"], "eng_total": [1]}))


# --- CS8 · price -------------------------------------------------------------

def test_price_intel_trich_gia_va_khuyen_mai(df):
    out = an.price_intel(df)
    assert len(out) > 0
    r = out.iloc[0]
    assert "99" in r["gia_phat_hien"]
    assert "买一送一" in r["moi_km"] or "秒杀" in r["moi_km"]


# --- CS11 · sov --------------------------------------------------------------

def test_sov_pct_tong_100_moi_tuan(df, monkeypatch):
    # gắn brand vào title để chia rổ
    d = df.copy()
    d.loc[d.index % 2 == 0, "title"] = d["title"] + " BrandA专用"
    d.loc[d.index % 2 == 1, "title"] = d["title"] + " brandb好用"
    g = an.sov(d, {"BrandA": ["branda"], "BrandB": ["brandb"]})
    assert {"week", "brand", "so_bai", "eng", "sov_pct"} <= set(g.columns)
    # mỗi tuần tổng %SOV ~ 100
    for _, wk in g.groupby("week"):
        assert wk["sov_pct"].sum() == pytest.approx(100.0, abs=0.5)


def test_sov_khong_match_tra_rong(df):
    g = an.sov(df, {"BrandX": ["khong_co_tu_nay"]})
    assert len(g) == 0


# --- CS5 · angle -------------------------------------------------------------

def test_export_angles_jsonl_dung_schema(df):
    path = an.export_angles(df, top_pct=0.3)
    lines = [json.loads(x) for x in
             open(path, encoding="utf-8").read().strip().splitlines()]
    assert len(lines) >= 1
    required = {"angle_id", "platform", "source_keyword", "hook", "format",
                "pain_or_desire", "cta_observed", "sound_ref", "metrics", "lang"}
    for rec in lines:
        assert required <= set(rec)
        assert {"like", "comment", "share", "collect"} <= set(rec["metrics"])


# --- load() ------------------------------------------------------------------

def test_load_xlsx_jsonl_csv(synthetic_search_df, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    synthetic_search_df.to_excel(tmp_path / "d.xlsx", index=False)
    synthetic_search_df.to_csv(tmp_path / "d.csv", index=False)
    synthetic_search_df.to_json(tmp_path / "d.jsonl", orient="records",
                                lines=True, force_ascii=False)
    for name in ["d.xlsx", "d.csv", "d.jsonl"]:
        d = an.load(tmp_path / name)
        assert "eng_total" in d.columns and len(d) == len(synthetic_search_df)
    with pytest.raises(ValueError):
        an.load(tmp_path / "d.txt")
