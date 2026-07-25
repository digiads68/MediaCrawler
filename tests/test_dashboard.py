# -*- coding: utf-8 -*-
"""Test dashboard đa nền tảng — synthetic, không gọi mạng."""

from __future__ import annotations

import pandas as pd

from kit.dashboard import adapters
from kit.dashboard.metrics import (
    add_trend_score,
    compute_sections,
    dedupe,
)
from kit.dashboard.render import render_dashboard
from kit.enrich.normalize import normalize

# ---------------------------------------------------------------------------
# Dữ liệu synthetic từng nền tảng (đúng chữ ký cột thật)
# ---------------------------------------------------------------------------

def _douyin_raw() -> pd.DataFrame:
    return pd.DataFrame({
        "aweme_id": ["dy1", "dy2"],
        "title": ["4 招 kiếm tiền #副业", "Vibe coding教程 #AI"],
        "desc": ["", ""],
        "create_time": [1760000000, 1761000000],
        "nickname": ["a***a", "b***b"],
        "creator_hash": ["h1", "h2"],
        "liked_count": [1000, 2000],
        "collected_count": [500, 400],
        "comment_count": [50, 80],
        "share_count": [20, 30],
        "aweme_url": ["https://douyin.com/video/1", "https://douyin.com/video/2"],
        "cover_url": ["https://c/1.jpg", "https://c/2.jpg"],
        "video_download_url": ["https://dl/1.mp4", "https://dl/2.mp4"],
        "music_download_url": ["https://m/1", ""],
        "source_keyword": ["编程副业", "编程副业"],
    })


def _bili_raw() -> pd.DataFrame:
    return pd.DataFrame({
        "video_id": ["bv1", "bv2"],
        "title": ["Python 全套教程 tại sao", "副业 review"],
        "desc": ["", ""],
        "create_time": [1724000000, 1762000000],
        "nickname": ["c***c", "d***d"],
        "creator_hash": ["h3", "h3"],
        "liked_count": [400000, 700],
        "video_favorite_count": [700000, 500],
        "video_comment": [300000, 20],
        "video_share_count": [90000, 5],
        "video_play_count": [18000000, 20000],
        "video_coin_count": [340000, 10],
        "video_danmaku": [110000, 2],
        "disliked_count": [0, 0],
        "video_url": ["https://bili/av1", "https://bili/av2"],
        "video_cover_url": ["http://i.hdslb/1.jpg", "http://i.hdslb/2.jpg"],
        "source_keyword": ["编程副业", "编程兼职"],
    })


def _xhs_raw() -> pd.DataFrame:
    return pd.DataFrame({
        "note_id": ["xhs1", "xhs2"],
        "type": ["normal", "video"],
        "title": ["1 giờ kiếm 1600", "月赚167万 bí mật"],
        "desc": ["", ""],
        "time": [1706018587000, 1737536491000],  # epoch ms
        "nickname": ["e***e", "f***f"],
        "creator_hash": ["h4", "h5"],
        "liked_count": [4831, 2657],
        "collected_count": [3916, 3378],
        "comment_count": [482, 61],
        "share_count": [1211, 530],
        "image_list": ["http://r/1.webp,http://r/2.webp", "http://r/3.webp"],
        "tag_list": ["转码,搞钱", "创业"],
        "note_url": ["https://xhs.com/explore/1", "https://xhs.com/explore/2"],
        "source_keyword": ["编程副业", "编程兼职"],
        "video_url": ["", "https://xhscdn/2.mp4"],
    })


# ---------------------------------------------------------------------------
# adapters
# ---------------------------------------------------------------------------

def test_detect_platform():
    assert adapters.detect_platform(_douyin_raw()) == "douyin"
    assert adapters.detect_platform(_bili_raw()) == "bilibili"
    assert adapters.detect_platform(_xhs_raw()) == "xhs"


def test_adapt_dua_ve_cot_hop_nhat():
    out = adapters.adapt(_bili_raw(), source="bilibili_search_x.xlsx")
    for c in adapters.UNIFIED_COLS:
        assert c in out.columns
    assert (out["platform"] == "bilibili").all()
    assert out["content_kind"].iloc[0] == "search"
    # favorite -> collected_count; play_count giữ nguyên
    assert out["collected_count"].iloc[0] == 700000
    assert out["play_count"].iloc[0] == 18000000


def test_adapt_xhs_cover_lay_anh_dau_va_thoi_gian_ms():
    out = adapters.adapt(_xhs_raw(), source="xhs_search.xlsx")
    assert out["cover_url"].iloc[0] == "http://r/1.webp"      # ảnh đầu tiên
    assert out["media_type"].iloc[1] == "video"
    # create_time vẫn epoch ms — normalize sẽ tự quy đổi
    assert out["create_time"].iloc[0] == 1706018587000


def test_adapt_douyin_creator_kind_tu_ten_file():
    out = adapters.adapt(_douyin_raw(), source="douyin_creator_x.xlsx")
    assert out["content_kind"].iloc[0] == "creator"


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------

def _unified() -> pd.DataFrame:
    frames = [adapters.adapt(_douyin_raw(), source="douyin_search.xlsx"),
              adapters.adapt(_bili_raw(), source="bili_search.xlsx"),
              adapters.adapt(_xhs_raw(), source="xhs_search.xlsx")]
    df = normalize(pd.concat(frames, ignore_index=True))
    return add_trend_score(dedupe(df))


def test_dedupe_go_bai_trung_giu_tuong_tac_cao():
    df = adapters.adapt(_douyin_raw(), source="s.xlsx")
    dup = pd.concat([df, df], ignore_index=True)      # nhân đôi
    dup = normalize(dup)
    out = dedupe(dup)
    assert len(out) == 2                               # còn 2 item duy nhất


def test_trend_score_chuan_hoa_theo_nen_tang():
    df = _unified()
    assert df["trend_score"].between(0, 100).all()
    # mỗi nền tảng có ít nhất 1 bài đạt đỉnh ~100
    for _, g in df.groupby("platform"):
        assert g["trend_score"].max() > 90


def test_compute_sections_day_du_khoa():
    sec = compute_sections(_unified())
    for key in ["kpis", "platform_mix", "keyword_mix", "format_mix",
                "timeline", "trend", "creators", "hooks", "opportunity"]:
        assert key in sec
    assert len(sec["platform_mix"]) == 3               # 3 nền tảng
    assert not sec["trend"].empty


def test_hook_lab_bat_hashtag_va_cong_thuc():
    sec = compute_sections(_unified())
    hooks = sec["hooks"]
    tags = {t for t, _ in hooks["top_tags"]}
    assert "副业" in tags or "AI" in tags              # hashtag từ title
    assert hooks["patterns"]                            # có nhận diện công thức


# ---------------------------------------------------------------------------
# render (tự chứa, không mạng)
# ---------------------------------------------------------------------------

def test_render_tao_html_tu_chua_co_nut_n8n():
    sec = compute_sections(_unified())
    html = render_dashboard(sec, meta={"sources": ["a.xlsx"],
                                        "n8n_webhook": "https://n8n/x"})
    assert html.startswith("<!doctype html>")
    assert "tab-pane" in html
    assert 'data-action="download"' in html            # nút n8n
    assert 'data-action="transcribe"' in html
    assert "__MC_CFG__" in html and "https://n8n/x" in html
    assert "preview-modal" in html                      # modal preview


def test_render_khong_ro_ri_nan_none():
    sec = compute_sections(_unified())
    html = render_dashboard(sec)
    assert ">nan<" not in html and ">None<" not in html and "NaT" not in html


def test_render_grid_rong_khong_vo():
    sec = compute_sections(_unified())
    sec["trend"] = sec["trend"].iloc[0:0]              # rỗng
    html = render_dashboard(sec)
    assert "Không có dữ liệu" in html
