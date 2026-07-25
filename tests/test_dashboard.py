# -*- coding: utf-8 -*-
"""Test dashboard đa nền tảng — synthetic, không gọi mạng."""

from __future__ import annotations

import pandas as pd
import pytest

from kit.dashboard import adapters
from kit.dashboard import analysis as A
from kit.dashboard import profiles as P
from kit.dashboard.build import build_all, build_dashboard, pick_profile
from kit.dashboard.metrics import (
    add_trend_score,
    compute_sections,
    dedupe,
    load_bundle,
    sanitize_counts,
)
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
        # Cố tình để trống 1 ô — XHS thật có trường hợp này.
        "comment_count": [482, None],
        "share_count": [1211, 530],
        "image_list": ["http://r/1.webp,http://r/2.webp", "http://r/3.webp"],
        "tag_list": ["转码,搞钱", "创业"],
        "note_url": ["https://xhs.com/explore/1", "https://xhs.com/explore/2"],
        "source_keyword": ["编程副业", "编程兼职"],
        "video_url": ["", "https://xhscdn/2.mp4"],
    })


def _comments_raw() -> pd.DataFrame:
    """Bình luận cho dy1 — có câu hỏi, nỗi đau, mong muốn, và câu lặp."""
    texts = ["这个怎么学？求教程", "这个怎么学？求教程", "太难了吧，我试过失败了",
             "想学但没时间，有速成办法吗", "普通分享"]
    return pd.DataFrame({
        "comment_id": [f"c{i}" for i in range(len(texts))],
        "aweme_id": ["dy1"] * len(texts),
        "content": texts,
        "create_time": [1760000100 + i for i in range(len(texts))],
        "nickname": [f"u***{i}" for i in range(len(texts))],
        "creator_hash": [f"ch{i}" for i in range(len(texts))],
        "like_count": [90, 90, 70, 50, 5],
        "sub_comment_count": [2, 0, 1, 0, 0],
        "parent_comment_id": ["0"] * len(texts),
    })


def _write_xlsx(tmp_path, name: str, contents: pd.DataFrame,
                comments: pd.DataFrame | None = None) -> str:
    p = tmp_path / name
    with pd.ExcelWriter(p) as w:
        contents.to_excel(w, sheet_name="Contents", index=False)
        if comments is not None:
            comments.to_excel(w, sheet_name="Comments", index=False)
    return str(p)


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


def test_adapt_comments_map_khoa_bai():
    out = adapters.adapt_comments(_comments_raw(), platform="douyin")
    for c in adapters.COMMENT_COLS:
        assert c in out.columns
    assert (out["item_id"] == "dy1").all()      # aweme_id -> item_id
    assert out["like_count"].iloc[0] == 90


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------

def _unified() -> pd.DataFrame:
    frames = [adapters.adapt(_douyin_raw(), source="douyin_search.xlsx"),
              adapters.adapt(_bili_raw(), source="bili_search.xlsx"),
              adapters.adapt(_xhs_raw(), source="xhs_search.xlsx")]
    df = normalize(sanitize_counts(pd.concat(frames, ignore_index=True)))
    return add_trend_score(dedupe(df))


def test_sanitize_counts_dien_0_cho_o_trong():
    """Ô comment_count trống của XHS không được làm eng_total thành NaN."""
    df = _unified()
    assert df["eng_total"].notna().all()
    assert df["comment_count"].notna().all()


def test_dedupe_go_bai_trung_giu_tuong_tac_cao():
    df = adapters.adapt(_douyin_raw(), source="s.xlsx")
    dup = pd.concat([df, df], ignore_index=True)      # nhân đôi
    dup = normalize(dup)
    out = dedupe(dup)
    assert len(out) == 2                               # còn 2 item duy nhất


def test_trend_score_chuan_hoa_theo_nen_tang():
    df = _unified()
    assert df["trend_score"].between(0, 100).all()
    for _, g in df.groupby("platform"):
        assert g["trend_score"].max() > 90


def test_compute_sections_day_du_khoa():
    sec = compute_sections(_unified())
    for key in ["kpis", "platform_mix", "keyword_mix", "format_mix",
                "timeline", "trend", "creators", "hooks", "opportunity"]:
        assert key in sec
    assert len(sec["platform_mix"]) == 3               # 3 nền tảng
    assert not sec["trend"].empty


def test_load_bundle_doc_ca_2_sheet_va_nhan_dien_mode(tmp_path):
    f1 = _write_xlsx(tmp_path, "douyin_search_x.xlsx", _douyin_raw(),
                     _comments_raw())
    f2 = _write_xlsx(tmp_path, "douyin_creator_x.xlsx", _douyin_raw())
    b = load_bundle([f1, f2])
    assert not b["content"].empty
    assert len(b["comments"]) == len(_comments_raw())
    assert b["modes"]["search"] == 1 and b["modes"]["creator"] == 1


# ---------------------------------------------------------------------------
# analysis (phần chuyên sâu)
# ---------------------------------------------------------------------------

def test_benchmark_phan_vi_tang_dan():
    bm = A.benchmark(_unified())
    q = bm["eng_total"]
    assert q["p25"] <= q["p50"] <= q["p75"] <= q["p90"]


def test_benchmark_theo_nen_tang_tach_rieng():
    bmp = A.benchmark_by_platform(_unified())
    assert set(bmp) == {"douyin", "bilibili", "xhs"}
    # Bilibili có bài triệu view -> P90 phải cao hơn Douyin
    assert bmp["bilibili"]["p90"] > bmp["douyin"]["p90"]


def test_outlier_ratio_tinh_trong_tung_nhom():
    df = A.add_outlier_ratio(_unified(), by="platform")
    assert "out_ratio" in df.columns and "breakout" in df.columns
    # Trong mỗi nền tảng, trung vị nhóm -> phải có bài ratio >= 1
    for _, g in df.groupby("platform"):
        assert (g["out_ratio"] >= 1).any()


def test_consistency_score_ben_voi_bai_viral():
    """1 bài viral không được kéo độ đều về 0 (điểm yếu của std/mean)."""
    steady = pd.Series([100, 105, 95, 100])
    spiky = pd.Series([100, 105, 95, 100_000])
    assert A.consistency_score(steady) > 0.8
    assert A.consistency_score(spiky) > 0.0     # vẫn phản ánh phần lõi đều


def test_format_matrix_va_khe_trong():
    fmx = A.format_matrix(_unified())
    assert fmx["rows"] and fmx["cols"]
    assert all(isinstance(k, tuple) for k in fmx["cells"])
    assert isinstance(fmx["gaps"], list)


def test_hook_performance_co_ty_le_thang():
    hp = A.hook_performance(_unified())
    assert hp
    for h in hp:
        assert 0 <= h["win_rate"] <= 1
        assert h["n"] >= 1
    # sắp giảm dần theo trung vị
    assert hp == sorted(hp, key=lambda x: x["eng_median"], reverse=True)


def test_posting_heatmap_kich_thuoc_dung():
    hm = A.posting_heatmap(_unified(), bucket_hours=3)
    assert len(hm["cols"]) == 7
    assert len(hm["matrix"]) == 8                   # 24h / 3
    assert all(len(row) == 7 for row in hm["matrix"])


def test_creator_profile_day_du_truong():
    df = _unified()
    p = A.creator_profile(df, "h3")                 # Bilibili: 2 bài cùng creator
    for k in ("n_posts", "eng_median", "velocity", "consistency", "points",
              "breakouts", "format_mix", "span"):
        assert k in p
    assert p["n_posts"] == 2


def test_creator_leaderboard_loc_kenh_it_bai():
    lb = A.creator_leaderboard(_unified(), min_posts=2)
    assert not lb.empty
    assert (lb["n_posts"] >= 2).all()


def test_comment_mining_gop_cau_lap_va_bat_cau_hoi():
    cm = adapters.adapt_comments(_comments_raw(), platform="douyin")
    voc = A.comment_mining(cm)
    assert voc["n"] == 5 and voc["n_unique"] == 4    # 1 câu lặp 2 lần
    texts = [c["text"] for c in voc["questions"]]
    assert any("怎么学" in t for t in texts)
    assert len(texts) == len(set(texts))             # đã gộp trùng
    assert any(c["repeat"] == 2 for c in voc["top"])
    assert voc["pain"] and voc["desire"]


def test_comment_mining_rong_khong_vo():
    voc = A.comment_mining(pd.DataFrame())
    assert voc["n"] == 0 and voc["questions"] == []


def test_engagement_anatomy_dung_thang_chung():
    df = _unified()
    bm = A.benchmark(df)
    rows = A.engagement_anatomy(df.iloc[0], bm)
    assert rows
    vmaxes = {r["vmax"] for r in rows}
    assert len(vmaxes) == 1                          # 1 thang chung cho 4 chỉ số
    assert all(r["ref"] == 1.0 for r in rows)        # mốc P50 = 1×


# ---------------------------------------------------------------------------
# profiles + build
# ---------------------------------------------------------------------------

def _bundle(with_comments: bool = False) -> dict:
    cm = (adapters.adapt_comments(_comments_raw(), platform="douyin")
          if with_comments else pd.DataFrame(columns=adapters.COMMENT_COLS))
    from collections import Counter
    return {"content": _unified(), "comments": cm,
            "modes": Counter({"search": 1})}


@pytest.mark.parametrize("profile", P.PROFILES)
def test_moi_profile_sinh_html_tu_chua(profile):
    html = P.render(profile, _bundle(with_comments=True),
                    meta={"sources": ["a.xlsx"], "n8n_webhook": "https://n8n/x"})
    assert html.startswith("<!doctype html>")
    assert "tab-pane" in html and "__MC_CFG__" in html
    assert 'data-action="download"' in html          # nút n8n
    assert 'data-action="transcribe"' in html
    assert "preview-modal" in html
    assert "https://n8n/x" in html


@pytest.mark.parametrize("profile", P.PROFILES)
def test_moi_profile_khong_ro_ri_nan(profile):
    html = P.render(profile, _bundle())
    assert ">nan<" not in html and ">None<" not in html and "NaT" not in html


def test_profile_khong_hop_le_bao_loi():
    with pytest.raises(ValueError, match="không hợp lệ"):
        P.render("khong-ton-tai", _bundle())


def test_video_profile_huong_dan_khi_thieu_comment():
    html = P.render("video", _bundle(with_comments=False))
    assert "get_comment" in html                     # gợi ý bật cờ crawl


def test_pick_profile_theo_mode():
    from collections import Counter
    assert pick_profile(Counter({"search": 3})) == "search"
    assert pick_profile(Counter({"creator": 1})) == "creator"
    assert pick_profile(Counter({"detail": 2})) == "video"
    # trộn nhiều mode -> overview
    assert pick_profile(Counter({"search": 1, "creator": 1})) == "overview"
    assert pick_profile(Counter()) == "overview"


def test_build_dashboard_auto_chon_dung_loai(tmp_path):
    f = _write_xlsx(tmp_path, "douyin_search_x.xlsx", _douyin_raw())
    out = tmp_path / "d.html"
    p = build_dashboard([f], out=out)
    assert p.exists()
    html = p.read_text(encoding="utf-8")
    assert "SEARCH MODE" in html                     # auto -> profile search


def test_build_dashboard_profile_sai_bao_loi(tmp_path):
    f = _write_xlsx(tmp_path, "x_search.xlsx", _douyin_raw())
    with pytest.raises(ValueError, match="không hợp lệ"):
        build_dashboard([f], profile="sai", out=tmp_path / "x.html")


def test_build_dashboard_thieu_file_bao_loi():
    with pytest.raises(ValueError, match="ít nhất 1 file"):
        build_dashboard([])


def test_build_all_sinh_nhieu_loai_va_index(tmp_path):
    f1 = _write_xlsx(tmp_path, "dy_search.xlsx", _douyin_raw(), _comments_raw())
    f2 = _write_xlsx(tmp_path, "dy_creator.xlsx", _douyin_raw())
    made = build_all([f1, f2], out_dir=tmp_path / "out")
    # search + creator + video (có comment) + overview + index
    assert {"search", "creator", "video", "overview", "index"} <= set(made)
    for p in made.values():
        assert p.exists() and p.stat().st_size > 0
    idx = made["index"].read_text(encoding="utf-8")
    for prof in ("search", "creator", "video", "overview"):
        assert P.filename_of(prof) in idx            # index link tới từng trang


def test_posting_heatmap_khong_ket_luan_tu_mau_nho():
    """Giờ vàng không được suy ra từ 1 bài viral lẻ."""
    df = _unified()
    hm = A.posting_heatmap(df, metric="eng", min_n=3)
    assert hm["best"] is not None
    # Dữ liệu synthetic rất ít -> phải tự nhận là chưa đủ mẫu
    assert hm["best"]["low_confidence"] is True
    # Khi hạ ngưỡng xuống 1 thì được coi là đủ mẫu
    hm2 = A.posting_heatmap(df, metric="eng", min_n=1)
    assert hm2["best"]["low_confidence"] is False
