# -*- coding: utf-8 -*-
"""Test tầng báo cáo HTML — synthetic, không gọi mạng, không phụ thuộc thời gian."""

from __future__ import annotations

import pandas as pd
import pytest

from kit.report import build_report, charts


# ---------------------------------------------------------------------------
# charts (SVG thuần, kiểm chuỗi trả về)
# ---------------------------------------------------------------------------

def test_donut_co_lat_va_chu_giai():
    svg = charts.donut([("A", 3), ("B", 1)], title="Cơ cấu")
    assert svg.count("<path") == 2          # 2 lát
    assert "75%" in svg and "25%" in svg    # % trong chú giải
    assert "var(--c-1)" in svg and "var(--c-2)" in svg


def test_donut_gop_khac_khi_qua_nhieu_lat():
    data = [(f"K{i}", 10 - i) for i in range(9)]   # 9 nhóm > N_COLORS
    svg = charts.donut(data)
    assert "Khác" in svg
    assert svg.count("<path") == charts.N_COLORS


def test_donut_rong_tra_ve_khoi_trong():
    assert "Không đủ dữ liệu" in charts.donut([])
    assert "Không đủ dữ liệu" in charts.donut([("A", 0), ("B", -1)])


def test_hbar_co_thanh_va_gia_tri():
    svg = charts.hbar([("X", 100), ("Y", 50)], title="Top")
    assert svg.count("hb-fill") == 2
    assert "100" in svg and "var(--c-1)" in svg


def test_line_da_chuoi_co_polyline():
    svg = charts.line(
        [{"name": "Like", "points": [1, 2, 3]},
         {"name": "Save", "points": [3, 2, 1]}],
        ["t1", "t2", "t3"], title="Theo tuần")
    assert svg.count("<polyline") == 2
    assert "t1" in svg and "t3" in svg


def test_line_rong_khi_thieu_diem():
    assert "Không đủ dữ liệu" in charts.line([], [])


# ---------------------------------------------------------------------------
# build_report — từng loại, ghi vào tmp reports/
# ---------------------------------------------------------------------------

@pytest.fixture()
def _in_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_build_trend_co_link_video_va_chart(_in_tmp):
    top = pd.DataFrame({
        "title": ["Bài A", "Bài B"], "format": ["review", "khác"],
        "source_keyword": ["kw1", "kw2"],
        "liked_count": [100, 50], "collected_count": [20, 5],
        "share_count": [3, 1], "trend_score": [88.0, 40.0],
        "aweme_url": ["https://douyin.com/v/1", "https://douyin.com/v/2"],
    })
    fmt = pd.DataFrame({"format": ["review", "khác"], "so_bai": [1, 1],
                        "diem_tb": [88.0, 40.0], "save_tb": [20.0, 5.0]})
    result = {"top_posts": top, "formats": fmt, "sounds": pd.DataFrame()}
    df = pd.DataFrame({"source_keyword": ["kw1", "kw2"], "liked_count": [100, 50],
                       "collected_count": [20, 5], "share_count": [3, 1],
                       "comment_count": [2, 1]})
    p = build_report("trend", result, df=df,
                     meta={"keyword": "kw", "platform": "dy",
                           "generated": "01/01/2026 08:00"})
    assert p.exists() and p.name == "trend_report.html"
    html = p.read_text(encoding="utf-8")
    assert "Trend Radar" in html
    assert 'href="https://douyin.com/v/1"' in html      # link video nhúng
    assert "▶ Xem" in html
    assert "chart-donut" in html and "chart-line" in html
    assert "01/01/2026 08:00" in html                   # timestamp truyền vào


def test_build_koc_co_chip_verdict(_in_tmp):
    s = pd.DataFrame({
        "creator": ["c1", "c2"], "nickname": ["A", "B"], "so_video": [8, 6],
        "eng_tb": [500.0, 200.0], "do_deu": [0.6, 0.5], "velocity": [1.8, 1.1],
        "nhip_dang_ngay": [2.0, 3.0], "diem_tong": [82.0, 40.0],
        "verdict": pd.Categorical(["ký ngay", "bỏ qua"]),
        "rising": [True, False],
    })
    p = build_report("koc", s, meta={"generated": "x"})
    html = p.read_text(encoding="utf-8")
    assert "chip-good" in html            # verdict 'ký ngay' -> chip xanh
    assert "▲ có" in html                 # rising badge
    assert "chart-donut" in html


def test_build_sov_line_theo_tuan(_in_tmp):
    g = pd.DataFrame({
        "week": ["2026-W01", "2026-W01", "2026-W02", "2026-W02"],
        "brand": ["A", "B", "A", "B"],
        "so_bai": [5, 3, 6, 2], "eng": [500, 300, 600, 200],
        "sov_pct": [62.5, 37.5, 75.0, 25.0],
    })
    p = build_report("sov", g, meta={"generated": "x"})
    html = p.read_text(encoding="utf-8")
    assert "Share of Voice" in html
    assert "chart-line" in html           # >=2 tuần -> có line
    assert "chart-donut" in html


def test_build_generic_opportunity(_in_tmp):
    g = pd.DataFrame({
        "source_keyword": ["kw1", "kw2"], "so_bai": [3, 10],
        "eng_tb": [100.0, 50.0], "save_tb": [30.0, 5.0],
        "quadrant": ["🌊 biển xanh — đánh ngay", "🔴 bão hoà — tránh"],
    })
    p = build_report("opportunity", g, meta={"generated": "x"})
    assert p.name == "opportunity_report.html"
    html = p.read_text(encoding="utf-8")
    assert "Opportunity Map" in html and "chart-hbar" in html


def test_build_report_du_lieu_rong_khong_loi(_in_tmp):
    p = build_report("price", pd.DataFrame(), meta={"generated": "x"})
    assert p.exists()
    assert "Không có dữ liệu" in p.read_text(encoding="utf-8")


def test_escape_chong_html_injection(_in_tmp):
    top = pd.DataFrame({
        "title": ["<script>alert(1)</script>"], "format": ["x"],
        "source_keyword": ["k"], "liked_count": [1], "collected_count": [1],
        "share_count": [1], "trend_score": [1.0],
        "aweme_url": ["https://x/1"],
    })
    result = {"top_posts": top,
              "formats": pd.DataFrame({"format": ["x"], "so_bai": [1],
                                       "diem_tb": [1.0], "save_tb": [1.0]}),
              "sounds": pd.DataFrame()}
    p = build_report("trend", result, meta={"generated": "x"})
    html = p.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html      # đã escape
    assert "&lt;script&gt;" in html
