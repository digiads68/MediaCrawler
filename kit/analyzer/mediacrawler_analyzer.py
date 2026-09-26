# -*- coding: utf-8 -*-
"""
DigiAds · MediaCrawler Analyzer
================================
Bộ phân tích dùng chung cho 11 case study — đọc dữ liệu MediaCrawler xuất ra
(Excel/JSONL) và tính toán chỉ số cho từng case.

Cách chạy:
    python mediacrawler_analyzer.py <lệnh> <file_dữ_liệu> [tuỳ chọn]

Các lệnh (map với case study):
    trend       CS1/CS10 : chấm điểm trend + gom nhạc trending
    insight     CS2      : chuẩn bị comment bank cho LLM phân cụm
    koc         CS3/CS9  : scorecard KOC + phát hiện creator đang lên
    opportunity CS4/CS6  : bản đồ cơ hội ngách (volume vs engagement)
    seasonal    CS7      : radar mùa vụ theo tuần
    price       CS8      : tình báo giá & khuyến mãi từ desc/comment
    sov         CS11     : share-of-voice theo rổ brand
    angle       CS5      : xuất angle_library.jsonl cho pipeline AI video

Phụ thuộc: pandas, openpyxl (có sẵn trong stack chuẩn của DigiAds).
Dữ liệu vào: file .xlsx / .jsonl / .csv do MediaCrawler xuất
(cột chuẩn: title, desc, liked_count, comment_count, share_count,
 collected_count, create_time, source_keyword, nickname(đã ẩn danh),
 creator_hash, music_download_url, aweme_url/note_url ...).
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

# Cho phép chạy trực tiếp `python kit/analyzer/mediacrawler_analyzer.py ...`
# (thêm gốc repo vào sys.path để import được package kit)
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Console Windows mặc định cp1252 — ép UTF-8 để log tiếng Việt/ký hiệu không vỡ
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Nguồn sự thật của COUNT_COLS/FORMAT_RULES/normalize nằm ở kit/enrich/normalize.py
from kit.enrich.normalize import (  # noqa: E402,F401
    COUNT_COLS,
    FORMAT_RULES,
    normalize,
    tag_format_stats,
    tag_hook,
    text_series,
)
from kit.enrich.schema import add_canonical, dedupe_posts, infer_platform, music_id_of  # noqa: E402

# ============================================================================
# 0. TIỆN ÍCH CHUNG — nạp & chuẩn hoá dữ liệu MediaCrawler
# ============================================================================

PRICE_PATTERNS = [
    r"(\d+(?:\.\d+)?)\s*元", r"¥\s*(\d+(?:\.\d+)?)", r"(\d+(?:\.\d+)?)\s*块",
    r"(\d{1,3}(?:[.,]\d{3})+)\s*[dđ]", r"(\d+)\s*k\b",
]
PROMO_KEYWORDS = ["买一送一", "第二件", "折", "券", "满减", "秒杀", "限时",
                  "freeship", "sale", "giảm", "tặng", "voucher", "flash"]


def _read_raw(path: str | Path) -> pd.DataFrame:
    """Đọc thô file MediaCrawler xuất ra (xlsx / jsonl / json / csv)."""
    p = Path(path)
    if p.suffix == ".xlsx":
        return pd.read_excel(p)
    if p.suffix in (".jsonl", ".json"):
        # convert_dates=False: mặc định pandas tự đổi `create_time` sang datetime,
        # rồi normalize() coi nó là epoch -> NaT -> mọi file JSON mất trục thời
        # gian (KOC/Seasonal/SOV/tuổi bài sai). Giữ nguyên số epoch như file Excel.
        return pd.read_json(p, lines=(p.suffix == ".jsonl"), convert_dates=False)
    if p.suffix == ".csv":
        return pd.read_csv(p)
    raise ValueError(f"Định dạng chưa hỗ trợ: {p.suffix}")


def load(path: str | Path) -> pd.DataFrame:
    """
    Nạp file MediaCrawler xuất ra thành DataFrame đã chuẩn hoá.

    Chuỗi xử lý: đọc thô -> đóng dấu nền tảng + cột canonical -> bỏ dòng trùng
    -> normalize. Suy nền tảng từ đường dẫn là cách duy nhất phủ được cả 3 đường
    vào (CLI, /kit/analyze, job) vì dữ liệu thô không có cột `platform`.
    """
    df = _read_raw(path)
    platform = infer_platform(path, df)
    df = add_canonical(df, platform)
    df = dedupe_posts(df)
    return normalize(df)


def load_many(paths: Sequence[str | Path]) -> pd.DataFrame:
    """
    Nạp NHIỀU file (nhiều nền tảng / nhiều đợt) rồi gộp thành 1 DataFrame.

    Dùng cho dashboard so sánh chéo nền tảng. Mỗi file được đóng dấu `platform`
    riêng trước khi gộp, rồi dedupe theo `(platform, post_id)` — cần thiết vì
    Bilibili ghi Excel vào `data/bilibili/` và JSON vào `data/bili/`, gộp cả hai
    sẽ trùng bài.
    """
    frames: list[pd.DataFrame] = []
    for path in paths:
        df = _read_raw(path)
        df = add_canonical(df, infer_platform(path, df))
        frames.append(df)
    if not frames:
        raise ValueError("Không có file nào để nạp.")
    merged = pd.concat(frames, ignore_index=True, sort=False)
    return normalize(dedupe_posts(merged))


# reports/ suy từ vị trí file này, KHÔNG phải CWD — nếu không, chạy uvicorn từ
# thư mục khác sẽ ghi báo cáo ra chỗ mà `api/routers/kit.py` không đọc tới.
REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports"


def _take(df: pd.DataFrame, n: int | None) -> pd.DataFrame:
    """N dòng đầu; None = giữ hết (mặc định mọi lệnh: báo cáo phải đủ dữ liệu đã cào)."""
    return df if n is None else df.head(n)


def _out(df: pd.DataFrame, name: str) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    p = REPORTS_DIR / name
    if p.suffix == ".xlsx":
        df.to_excel(p, index=False)
    else:
        df.to_csv(p, index=False)
    print(f"[✓] Xuất: {p}  ({len(df)} dòng)")
    return p


def _out_sheets(sheets: dict[str, pd.DataFrame], name: str) -> Path:
    """Ghi nhiều DataFrame vào 1 file Excel nhiều sheet (Voice-of-Customer cần)."""
    REPORTS_DIR.mkdir(exist_ok=True)
    p = REPORTS_DIR / name
    with pd.ExcelWriter(p) as writer:
        for sheet, sdf in sheets.items():
            (sdf if sdf is not None else pd.DataFrame()).to_excel(
                writer, sheet_name=sheet[:31], index=False)
    total = sum(len(s) for s in sheets.values() if s is not None)
    print(f"[✓] Xuất: {p}  ({len(sheets)} sheet, {total} dòng)")
    return p


# ============================================================================
# CS1 + CS10 · TREND RADAR & SOUND WATCHLIST
# ============================================================================

def trend_radar(df: pd.DataFrame, top: int | None = None) -> dict:
    """
    Chấm điểm trend cho từng bài và tổng hợp kết luận cho báo cáo.

    trend_score (0–100) = trung bình có trọng số THỨ HẠNG phần trăm của
    lưu 0.4 · chia sẻ 0.3 · bình luận 0.2 · like 0.1 (xem kit/analyzer/insights.py).
    Trước đây chia cho giá trị lớn nhất nên 1 bài viral ép mọi bài khác về ~0.

    Args:
        df: dữ liệu đã chuẩn hoá (`load`).
        top: None = giữ MỌI bài (mặc định — báo cáo và Excel phải đủ dữ liệu đã
            cào); số nguyên = chỉ giữ N bài điểm cao nhất.
    """
    from kit.analyzer.insights import add_post_insights, trend_summary

    d = add_post_insights(df)
    platform = str(d["platform"].iloc[0]) if "platform" in d.columns and len(d) else ""
    cols = [c for c in ["title", "format", "source_keyword", "liked_count",
                        "collected_count", "share_count", "comment_count",
                        "trend_score", "save_rate", "share_rate",
                        "goal", "goal_label", "age_days", "creator_hash", "desc", "tag_list",
                        "nickname", "created_at", "cover_url",
                        # canonical: nền tảng + cover gộp (xhs lưu cover trong
                        # image_list nên không có cột cover_url) + chỉ số đã map
                        "platform", "cover_url_c", "title_text",
                        "m_like", "m_comment", "m_share", "m_save", "m_view",
                        "music_download_url",
                        # Link trang xem theo nền tảng: dy=aweme_url, xhs=note_url,
                        # bili=video_url. Link tải file trực tiếp: dy=video_download_url,
                        # bili=download_url, xhs=video_url (là MP4 trên CDN).
                        "aweme_url", "note_url", "video_url",
                        "video_download_url", "download_url"] if c in d.columns]
    ranked = d.sort_values("trend_score", ascending=False)
    top_posts = (ranked if top is None else ranked.head(top))[cols]

    # Format nào đang thắng.
    # save_tb phải suy cột theo nền tảng: bilibili/weibo không có
    # `collected_count` (bilibili đặt là `video_favorite_count`, weibo không có
    # save) — trước đây agg cứng vào `collected_count` nên trend_radar CRASH
    # hoàn toàn trên 2 nền tảng đó. Tên cột output giữ nguyên `save_tb`.
    save_col = next((c for c in ("m_save", "collected_count") if c in d.columns), None)
    if save_col is None:
        d = d.copy()
        d["_save_na"] = float("nan")
        save_col = "_save_na"
    fmt = (d.groupby("format")
             .agg(so_bai=("format", "size"),
                  diem_tb=("trend_score", "mean"),
                  save_tb=(save_col, "mean"))
             .sort_values("diem_tb", ascending=False).reset_index())

    # Sound watchlist (CS10).
    # Gom theo music_id (tên file trong URL) chứ không phải URL nguyên vẹn: cùng
    # một bản nhạc được phục vụ từ nhiều host CDN — đo thật trên Douyin 28 URL
    # ra 25 URL khác nhau nhưng chỉ 20 bản nhạc. Gom theo URL sẽ đếm thiếu số
    # lần dùng lại. Cột output vẫn tên `music_download_url` (giữ URL đại diện).
    sounds = pd.DataFrame()
    if "music_download_url" in d.columns:
        s = d[d["music_download_url"].notna() & (d["music_download_url"] != "")].copy()
        if len(s):
            s["_music_id"] = s["music_download_url"].map(music_id_of)
            sounds = (s.groupby("_music_id")
                        .agg(music_download_url=("music_download_url", "first"),
                             so_video=("_music_id", "size"),
                             eng_tb=("eng_total", "mean"))
                        .query("so_video >= 2")
                        .sort_values(["so_video", "eng_tb"], ascending=False)
                        .reset_index(drop=True))
    _out(top_posts, "CS1_trend_top_posts.xlsx")
    _out(fmt, "CS1_trend_formats.xlsx")
    if len(sounds):
        _out(sounds, "CS10_sound_watchlist.xlsx")
    return {"top_posts": top_posts, "formats": fmt, "sounds": sounds,
            "summary": trend_summary(d, platform)}


# ============================================================================
# CS2 · INSIGHT / COMMENT BANK
# ============================================================================

def comment_bank(df: pd.DataFrame, min_like: int = 1, top: int | None = None) -> pd.DataFrame:
    """
    Chuẩn bị comment cho LLM phân cụm: lọc rác, dedupe, xếp theo like,
    cắt top N để vừa context window. Đầu ra nạp thẳng vào prompt phân cụm
    (xem angle_to_video_prompts.py / handbook CS2).
    """
    col = "content" if "content" in df.columns else "comment_content"
    d = df[[c for c in [col, "like_count", "sub_comment_count"] if c in df.columns]].copy()
    d = d.rename(columns={col: "content"})
    d["content"] = d["content"].astype(str).str.strip()
    d = d[d["content"].str.len().between(4, 300)]
    d = d[~d["content"].str.fullmatch(r"[\W\d_]+")]          # bỏ toàn ký tự/emoji
    d = d.drop_duplicates("content")
    if "like_count" in d.columns:
        d = d[d["like_count"] >= min_like].sort_values("like_count", ascending=False)
    d = _take(d, top).reset_index(drop=True)
    _out(d, "CS2_comment_bank.xlsx")
    return d


# ============================================================================
# CS3 + CS9 · KOC SCORECARD & RISING CREATOR
# ============================================================================

def koc_scorecard(df: pd.DataFrame, min_videos: int = 5) -> pd.DataFrame:
    """
    Chấm KOC theo 3 trục:
      - eng_tb      : engagement trung bình / video
      - do_deu      : 1/(1+CV)  — CV = std/mean, càng đều điểm càng cao
      - velocity    : ER nửa sau so với nửa đầu (đang lên hay nguội) -> CS9
    Điểm tổng = 0.4*eng_norm + 0.35*do_deu + 0.25*velocity_norm
    """
    key = "creator_hash" if "creator_hash" in df.columns else "nickname"
    rows = []
    for cid, g in df.sort_values("created_at").groupby(key):
        if len(g) < min_videos:
            continue
        eng = g["eng_total"]
        half = len(g) // 2
        v1, v2 = eng.iloc[:half].mean(), eng.iloc[half:].mean()
        velocity = (v2 / v1) if v1 > 0 else 1.0
        cv = eng.std() / eng.mean() if eng.mean() > 0 else 9
        rows.append({
            "creator": cid, "nickname": g.get("nickname", pd.Series([""])).iloc[0],
            "so_video": len(g), "eng_tb": round(eng.mean(), 1),
            "do_deu": round(1 / (1 + cv), 3),
            "velocity": round(velocity, 2),
            "nhip_dang_ngay": round(
                (g["created_at"].max() - g["created_at"].min()).days / max(len(g) - 1, 1), 1)
                if g["created_at"].notna().all() else None,
        })
    s = pd.DataFrame(rows)
    if s.empty:
        print("[!] Không đủ dữ liệu (mỗi creator cần ≥", min_videos, "video)")
        return s
    for c in ["eng_tb", "velocity"]:
        s[f"{c}_norm"] = s[c] / s[c].max()
    s["diem_tong"] = (0.40 * s["eng_tb_norm"] + 0.35 * s["do_deu"]
                      + 0.25 * s["velocity_norm"]).round(3) * 100
    s["verdict"] = pd.cut(s["diem_tong"], [-1, 40, 65, 200],
                          labels=["bỏ qua", "theo dõi", "ký ngay"])
    s["rising"] = (s["velocity"] >= 1.3) & (s["do_deu"] >= 0.4)   # CS9: đang lên & đủ đều
    s = s.sort_values("diem_tong", ascending=False)
    _out(s.drop(columns=["eng_tb_norm", "velocity_norm"]), "CS3_koc_scorecard.xlsx")
    _out(s[s["rising"]], "CS9_rising_creators.xlsx")
    return s


# ============================================================================
# CS4 + CS6 · OPPORTUNITY MAP (ngách & sản phẩm)
# ============================================================================

def opportunity_map(df: pd.DataFrame) -> pd.DataFrame:
    """
    Gom theo source_keyword: volume bài vs engagement/save trung bình.
    Quadrant:
      🌊 biển xanh  : ít bài, save cao      -> đánh ngay
      ⚔ cạnh tranh  : nhiều bài, save cao   -> cần angle khác biệt
      🏜 sa mạc     : ít bài, save thấp     -> chưa có cầu, bỏ
      🔴 bão hoà    : nhiều bài, save thấp  -> tránh
    """
    g = (df.groupby("source_keyword")
           .agg(so_bai=("source_keyword", "size"),
                eng_tb=("eng_total", "mean"),
                save_tb=("collected_count", "mean"))
           .reset_index())
    vol_med, save_med = g["so_bai"].median(), g["save_tb"].median()
    def quad(r):
        hi_vol, hi_save = r["so_bai"] > vol_med, r["save_tb"] > save_med
        if not hi_vol and hi_save: return "🌊 biển xanh — đánh ngay"
        if hi_vol and hi_save:     return "⚔ cạnh tranh — cần angle khác biệt"
        if not hi_vol:             return "🏜 sa mạc — chưa có cầu"
        return "🔴 bão hoà — tránh"
    g["quadrant"] = g.apply(quad, axis=1)
    # Trục thứ 3 "độ khó vào": lượng like dồn về vài creator hay trải đều (HHI).
    from kit.analyzer.insights import concentration
    conc = {kw: concentration(sub) for kw, sub in df.groupby("source_keyword")}
    g["so_creator"] = g["source_keyword"].map(lambda k: conc.get(k, {}).get("creators"))
    g["top3_pct"] = g["source_keyword"].map(
        lambda k: round(conc[k]["top3_share"] * 100, 1) if conc.get(k) else None)
    g["hhi"] = g["source_keyword"].map(lambda k: conc.get(k, {}).get("hhi"))
    g["do_kho_vao"] = g["source_keyword"].map(
        lambda k: {"Phân tán": "dễ vào", "Vừa": "vừa", "Tập trung": "khó vào"}.get(
            conc.get(k, {}).get("label", ""), "—"))
    g = g.sort_values(["quadrant", "save_tb"], ascending=[True, False])
    _out(g, "CS6_opportunity_map.xlsx")
    return g


# ============================================================================
# CS7 · SEASONAL RADAR
# ============================================================================

def seasonal_radar(df: pd.DataFrame) -> pd.DataFrame:
    """Tổng hợp theo tuần: số bài & engagement — dò đợt sóng mùa vụ để lên lịch content."""
    if "week" not in df.columns:
        raise ValueError("Thiếu create_time — bật thu thập thời gian đăng.")
    g = (df.groupby(["week", "source_keyword"])
           .agg(so_bai=("week", "size"), eng_tong=("eng_total", "sum"))
           .reset_index().sort_values("week"))
    # spike = tuần có eng vượt 1.5x trung bình trượt 4 tuần của chính keyword đó
    g["eng_ma4"] = (g.groupby("source_keyword")["eng_tong"]
                      .transform(lambda s: s.rolling(4, min_periods=1).mean()))
    g["spike"] = g["eng_tong"] > 1.5 * g["eng_ma4"]
    _out(g, "CS7_seasonal_radar.xlsx")
    return g


# ============================================================================
# CS8 · PRICE & PROMO INTEL
# ============================================================================

def price_intel(df: pd.DataFrame) -> pd.DataFrame:
    """Trích giá & mồi khuyến mãi từ desc/title/comment bằng regex."""
    text_col = next((c for c in ["desc", "content", "title"] if c in df.columns), None)
    if not text_col:
        raise ValueError("Không thấy cột văn bản (desc/content/title).")
    rows = []
    for _, r in df.iterrows():
        t = str(r.get(text_col, ""))
        prices = []
        for pat in PRICE_PATTERNS:
            prices += re.findall(pat, t)
        promos = [k for k in PROMO_KEYWORDS if k in t.lower()]
        if prices or promos:
            rows.append({"text": t[:120], "gia_phat_hien": ", ".join(prices[:5]),
                         "moi_km": ", ".join(promos),
                         "nguon_keyword": r.get("source_keyword", ""),
                         "eng_total": r.get("eng_total", 0)})
    out = pd.DataFrame(rows).sort_values("eng_total", ascending=False)
    _out(out, "CS8_price_intel.xlsx")
    return out


# ============================================================================
# CS11 · SHARE OF VOICE
# ============================================================================

def sov(df: pd.DataFrame, brand_map: dict[str, list[str]]) -> pd.DataFrame:
    """
    brand_map = {"BrandA": ["từ1","từ2"], "BrandB": [...]}  — gắn bài vào brand
    theo title/desc rồi tính % engagement mỗi brand chiếm trong ngành, theo tuần.
    """
    text = (text_series(df, "title") + " " + text_series(df, "desc")).str.lower()
    def which(t):
        for b, kws in brand_map.items():
            if any(k.lower() in t for k in kws):
                return b
        return None
    d = df.copy(); d["brand"] = text.map(which)
    d = d[d["brand"].notna()]
    g = (d.groupby(["week", "brand"])
           .agg(so_bai=("brand", "size"), eng=("eng_total", "sum")).reset_index())
    g["sov_pct"] = (g["eng"] / g.groupby("week")["eng"].transform("sum") * 100).round(1)
    _out(g, "CS11_sov_weekly.xlsx")
    return g


# ============================================================================
# CS5 · ANGLE LIBRARY EXPORT (nạp pipeline AI video)
# ============================================================================

def export_angles(df: pd.DataFrame, top_pct: float = 0.2) -> Path:
    """
    Lọc top X% theo trend_score, chuẩn hoá schema Angle rồi ghi angle_library.jsonl
    — file này là đầu vào của angle_to_video_prompts.py (Stage normalize/concept).
    """
    d = df.copy()
    if "trend_score" not in d.columns:
        for col, w in [("collected_count", .4), ("share_count", .3),
                       ("comment_count", .2), ("liked_count", .1)]:
            m = d[col].max() if col in d.columns and d[col].max() > 0 else 1
            d[f"_{col}"] = w * d.get(col, 0) / m
        d["trend_score"] = (d["_collected_count"] + d["_share_count"]
                            + d["_comment_count"] + d["_liked_count"]) * 100
    cut = d["trend_score"].quantile(1 - top_pct)
    top = d[d["trend_score"] >= cut]
    out = Path("reports"); out.mkdir(exist_ok=True)
    path = out / "angle_library.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for i, r in top.iterrows():
            f.write(json.dumps({
                "angle_id": f"{r.get('source_keyword','kw')}_{i}",
                # Trước đây hardcode "dy" nên angle từ xhs/bilibili bị gắn sai
                # nền tảng khi nạp vào pipeline AI video.
                "platform": str(r.get("platform") or "unknown"),
                "source_keyword": r.get("source_keyword", ""),
                "hook": str(r.get("title", ""))[:120],
                "format": r.get("format", "khác"),
                "pain_or_desire": "",                     # LLM Stage-0 sẽ điền
                "cta_observed": "",
                "sound_ref": r.get("music_download_url", ""),
                "metrics": {"like": r.get("liked_count", 0),
                            "comment": r.get("comment_count", 0),
                            "share": r.get("share_count", 0),
                            "collect": r.get("collected_count", 0)},
                "lang": "zh",
            }, ensure_ascii=False) + "\n")
    print(f"[✓] Xuất: {path}  ({len(top)} angle, top {int(top_pct*100)}%)")
    return path


# ============================================================================
# TIỆN ÍCH CHUNG CHO CÁC DASHBOARD SÁNG TẠO (Pha 2)
# ============================================================================
# Dùng median + p90 thay vì mean: engagement lệch cực mạnh (trong cùng 1 file
# Bilibili có bài 472.430 và bài 73), mean sẽ bị 1 bài viral kéo lệch hết.

def _p90(s: pd.Series) -> float:
    return float(s.quantile(0.9)) if len(s) else 0.0


def _stability(s: pd.Series) -> float:
    """Độ ổn định = 1/(1+CV). Cao = đều tay; thấp = ăn may vài bài viral."""
    if len(s) < 2 or s.mean() == 0:
        return 0.0
    return float(1 / (1 + (s.std() / s.mean())))


def _group_metrics(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """
    Chỉ số chuẩn cho mọi dashboard nhóm-theo-thuộc-tính.

    Trả: so_bai, phan_tram, eng_median, eng_p90, lift (so với median toàn file),
    do_on_dinh, so_creator, save_rate_median, share_rate_median.
    """
    if df is None or df.empty or by not in df.columns:
        return pd.DataFrame()
    base = df["eng_total"].median() if "eng_total" in df.columns else 0
    rows = []
    creator_col = "creator_hash" if "creator_hash" in df.columns else None
    for key, g in df.groupby(by, dropna=False):
        eng = g["eng_total"] if "eng_total" in g.columns else pd.Series(dtype=float)
        rows.append({
            by: str(key),
            "so_bai": len(g),
            "phan_tram": round(len(g) / len(df) * 100, 1),
            "eng_median": round(float(eng.median()) if len(eng) else 0, 1),
            "eng_p90": round(_p90(eng), 1),
            "lift": round(float(eng.median() / base), 2) if base else 0.0,
            "do_on_dinh": round(_stability(eng), 2),
            "so_creator": int(g[creator_col].nunique()) if creator_col else 0,
            "save_rate_median": (round(float(g["save_rate"].median()), 3)
                                 if "save_rate" in g.columns
                                 and g["save_rate"].notna().any() else None),
            "share_rate_median": (round(float(g["share_rate"].median()), 3)
                                  if "share_rate" in g.columns
                                  and g["share_rate"].notna().any() else None),
        })
    out = pd.DataFrame(rows)
    return out.sort_values("eng_median", ascending=False).reset_index(drop=True)


def _crosstab_median(df: pd.DataFrame, row_col: str, col_col: str,
                     value_col: str = "eng_total", *, min_count: int = 1
                     ) -> tuple[list[str], list[str], list[list[float | None]]]:
    """
    Bảng chéo median cho heatmap. Ô không đủ mẫu -> None (n/a), KHÔNG phải 0.

    Phân biệt None với 0 là bắt buộc: "chưa có ai làm cách này" khác hẳn
    "làm rồi nhưng không ai tương tác".
    """
    if df is None or df.empty or row_col not in df.columns or col_col not in df.columns:
        return [], [], []
    rows = [str(v) for v in df[row_col].value_counts().index]
    cols = [str(v) for v in df[col_col].value_counts().index]
    grid: list[list[float | None]] = []
    for r in rows:
        line: list[float | None] = []
        for c in cols:
            sub = df[(df[row_col].astype(str) == r) & (df[col_col].astype(str) == c)]
            if len(sub) < min_count or value_col not in sub.columns:
                line.append(None)
            else:
                line.append(round(float(sub[value_col].median()), 1))
        grid.append(line)
    return rows, cols, grid


# ============================================================================
# CS14 · FORMAT PLAYBOOK (đạo diễn — quyết định sản xuất format nào)
# ============================================================================

def format_playbook(df: pd.DataFrame, top_examples: int = 8) -> dict:
    """
    Từng format: hiệu quả, độ ổn định, và ghép với kiểu hook nào thì thắng.

    Khác `trend_radar().formats` (chỉ điểm trend trung bình): ở đây thêm median/
    p90 (chống lệch do bài viral), `do_on_dinh` (format ăn đều hay ăn may),
    `so_creator` (nhiều người làm được hay chỉ 1 kênh), và bảng chéo
    format × hook_type — câu trả lời trực tiếp cho đạo diễn.

    Cũng TỰ CHẤM ĐIỂM chính nó: `other_pct` = tỉ lệ bài không nhận ra format,
    kèm backlog title "khác" có engagement cao để mở rộng bộ luật. Nói thật
    "nhận diện được bao nhiêu" thay vì nhồi mọi bài vào một rổ.
    """
    d = tag_hook(df)
    stats = _group_metrics(d, "format")
    fmt_stats = tag_format_stats(d)

    # Bảng chéo format × hook_type (bỏ nhóm "khác" ở cả 2 trục cho gọn)
    sub = d[(d["format"] != "khác") & (d["hook_type"] != "khác")]
    rows, cols, grid = _crosstab_median(sub, "format", "hook_type")

    unclassified = pd.DataFrame()
    if fmt_stats["other_pct"] > 0:
        u = d[d["format"] == "khác"].copy()
        if "eng_total" in u.columns:
            u = u.sort_values("eng_total", ascending=False)
        keep = [c for c in ("title", "hook_text", "hook_type", "eng_total",
                            "platform", "source_keyword") if c in u.columns]
        unclassified = u[keep]

    examples = pd.DataFrame()
    if len(stats):
        top_formats = stats.head(3)["format"].tolist()
        ex = d[d["format"].isin(top_formats)].copy()
        if "eng_total" in ex.columns:
            ex = ex.sort_values("eng_total", ascending=False)
        examples = ex.groupby("format", group_keys=False).head(top_examples)

    _out(stats, "CS14_format_playbook.xlsx")
    if len(unclassified):
        _out(unclassified, "CS14_format_unclassified.xlsx")
    return {"stats": stats, "crosstab": (rows, cols, grid),
            "format_stats": fmt_stats, "unclassified": unclassified,
            "examples": examples}


# ============================================================================
# CS12 · HOOK LAB (người viết kịch bản — viết câu mở đầu)
# ============================================================================

def hook_lab(df: pd.DataFrame, top: int | None = None) -> dict:
    """
    Mổ xẻ câu mở đầu: kiểu hook nào ăn, dài bao nhiêu thì tốt, ai đang dùng.

    LƯU Ý TRUNG THỰC: "hook" ở đây là câu mở của TIÊU ĐỀ/CAPTION, không phải
    3 giây đầu video — dữ liệu không có transcript và không có thời lượng video.

    Đầu ra:
      types    : chỉ số theo `hook_type` (median/p90/lift/độ ổn định/số creator)
      lengths  : chỉ số theo nhóm độ dài hook
      top_posts: bài top kèm `hook_text` để copy trực tiếp vào kịch bản
    """
    from kit.enrich.lexicon import HOOK_LEN_BUCKETS, bucket_of

    d = tag_hook(df)
    if "hook_text" not in d.columns or not d["hook_text"].str.strip().any():
        raise ValueError("Thiếu tiêu đề/caption — Hook Lab đọc câu mở của caption.")

    types = _group_metrics(d, "hook_type")
    d = d.copy()
    d["nhom_do_dai"] = d["hook_len"].map(lambda v: bucket_of(v, HOOK_LEN_BUCKETS))
    lengths = _group_metrics(d[d["nhom_do_dai"] != ""], "nhom_do_dai")
    # Giữ đúng thứ tự bucket thay vì xếp theo engagement (đọc như thang đo)
    if len(lengths):
        order = {b[0]: i for i, b in enumerate(HOOK_LEN_BUCKETS)}
        lengths = (lengths.assign(_o=lengths["nhom_do_dai"].map(order))
                          .sort_values("_o").drop(columns="_o")
                          .reset_index(drop=True))

    cols = [c for c in ["hook_text", "hook_type", "hook_len", "format",
                        "source_keyword", "eng_total", "m_like", "liked_count",
                        "collected_count", "share_count", "comment_count",
                        "save_rate", "share_rate", "nickname", "created_at",
                        "cover_url", "cover_url_c", "platform", "title",
                        "aweme_url", "note_url", "video_url",
                        "video_download_url", "download_url",
                        "music_download_url"] if c in d.columns]
    top_posts = _take(d.sort_values("eng_total", ascending=False)
                      if "eng_total" in d.columns else d, top)[cols]

    _out(types, "CS12_hook_lab_types.xlsx")
    _out(top_posts, "CS12_hook_lab_top.xlsx")
    return {"types": types, "lengths": lengths, "top_posts": top_posts}


# ============================================================================
# CS10 + CS13 · SOUND & EDIT KIT (editor — chọn nhạc, dựng theo mẫu)
# ============================================================================

def _count_images(v: object) -> int:
    """Số ảnh trong 1 bài (cột image_list là chuỗi URL nối bằng dấu phẩy)."""
    if v is None or pd.isna(v):
        return 0
    s = str(v).strip()
    return len([x for x in s.split(",") if x.strip()]) if s else 0


def sound_edit_kit(df: pd.DataFrame, top: int | None = None) -> dict:
    """
    Bộ tư liệu cho editor: nhạc dùng lại + kết cấu nội dung.

    NỬA "SOUND" — chỉ Douyin có (`music_download_url`), và chỉ là URL mp3:
    nền tảng không xuất tên/tác giả/BPM nhạc. Gom theo `music_id` (tên file) chứ
    không theo URL, vì cùng một bản nhạc được phục vụ từ nhiều host CDN.
    Xếp theo `so_creator` (số creator KHÁC NHAU dùng chung nhạc) thay vì số bài:
    một creator đăng lại nhạc của chính mình không phải là tín hiệu trend.

    NỬA "EDIT" — mọi nền tảng: dạng nội dung (video vs bài ảnh), số ảnh, số
    hashtag. Đây là các yếu tố kết cấu DUY NHẤT đo được từ dữ liệu (không có
    thời lượng, không có cắt cảnh), và đều hành động được ngay khi dựng.
    """
    from kit.enrich.lexicon import HASHTAG_COUNT_BUCKETS, IMAGE_COUNT_BUCKETS, bucket_of
    from kit.enrich.schema import split_hashtags

    d = tag_hook(df).copy()

    # --- Sound watchlist ---
    sounds = pd.DataFrame()
    has_music = ("music_download_url" in d.columns
                 and d["music_download_url"].notna().any()
                 and (d["music_download_url"].astype(str).str.strip() != "").any())
    if has_music:
        s = d[d["music_download_url"].notna()
              & (d["music_download_url"].astype(str).str.strip() != "")].copy()
        s["music_id"] = s["music_download_url"].map(music_id_of)
        agg = {"music_download_url": ("music_download_url", "first"),
               "so_bai": ("music_id", "size"),
               "eng_median": ("eng_total", "median")}
        if "creator_hash" in s.columns:
            agg["so_creator"] = ("creator_hash", "nunique")
        sounds = s.groupby("music_id").agg(**agg).reset_index()
        sort_by = ["so_creator", "so_bai"] if "so_creator" in sounds.columns else ["so_bai"]
        sounds = sounds.sort_values(sort_by + ["eng_median"], ascending=False)
        sounds["eng_median"] = sounds["eng_median"].round(1)
        sounds["nhan_dien"] = "chỉ có URL mp3 — nền tảng không xuất tên nhạc"
        sounds = sounds.reset_index(drop=True)

    # --- Edit signals ---
    d["so_anh"] = d["image_list"].map(_count_images) if "image_list" in d.columns else 0
    d["so_hashtag"] = split_hashtags(d).map(len)
    if "media_kind" in d.columns:
        d["dang_noi_dung"] = d["media_kind"].astype(str).map(
            # douyin dùng mã số: 0 = video, 68 = bài ảnh
            lambda v: {"0": "video", "68": "bài ảnh", "normal": "bài ảnh",
                       "video": "video"}.get(v, v or "khác"))
    else:
        d["dang_noi_dung"] = d["so_anh"].map(lambda n: "bài ảnh" if n > 1 else "video")

    kinds = _group_metrics(d, "dang_noi_dung")
    d["nhom_so_anh"] = d["so_anh"].map(lambda v: bucket_of(v, IMAGE_COUNT_BUCKETS))
    images = _group_metrics(d[d["nhom_so_anh"] != ""], "nhom_so_anh")
    d["nhom_hashtag"] = d["so_hashtag"].map(lambda v: bucket_of(v, HASHTAG_COUNT_BUCKETS))
    hashtags = _group_metrics(d[d["nhom_hashtag"] != ""], "nhom_hashtag")

    # liked/collected/share/comment: thẻ trong kệ tư liệu đọc các cột này — trước đây
    # thiếu nên mọi thẻ hiện 0 like/0 save.
    cols = [c for c in ["hook_text", "format", "dang_noi_dung", "so_anh",
                        "so_hashtag", "eng_total", "nickname", "created_at",
                        "liked_count", "collected_count", "share_count", "comment_count",
                        "save_rate", "share_rate", "source_keyword",
                        "cover_url", "cover_url_c", "platform", "title",
                        "aweme_url", "note_url", "video_url",
                        "video_download_url", "download_url",
                        "music_download_url"] if c in d.columns]
    shelf = _take(d.sort_values("eng_total", ascending=False)
                  if "eng_total" in d.columns else d, top)[cols]

    if len(sounds):
        _out(sounds, "CS10_sound_watchlist.xlsx")
    edit_tables = {"dang_noi_dung": kinds, "so_anh": images, "hashtag": hashtags}
    _out(pd.concat([t.assign(_bang=name) for name, t in edit_tables.items()
                    if len(t)] or [pd.DataFrame()]), "CS13_edit_kit.xlsx")
    from kit.analyzer.insights import hashtag_stats, tag_pairs
    tag_stats = pd.DataFrame(hashtag_stats(d))
    pairs = pd.DataFrame(tag_pairs(d))
    if len(tag_stats):
        _out(tag_stats, "CS13_hashtag_stats.xlsx")
    return {"sounds": sounds, "kinds": kinds, "images": images,
            "hashtags": hashtags, "shelf": shelf, "has_music": has_music,
            "tag_stats": tag_stats, "tag_pairs": pairs}


# ============================================================================
# CS15 · COVER MOODBOARD (đạo diễn — tường ảnh tham khảo)
# ============================================================================

def cover_moodboard(df: pd.DataFrame, top: int | None = None) -> dict:
    """
    Tường ảnh cover của bài top, xếp theo hạng phần trăm engagement.

    KHÔNG phân tích nội dung ảnh (không có thị giác máy tính, không có LLM) —
    chỉ trưng bày kèm nhãn suy từ văn bản (format, kiểu hook) để đạo diễn tự đọc
    pattern thị giác. Có nút tải ảnh vì link cover của Douyin/XHS mang timestamp
    trong đường dẫn nên sẽ hết hạn sau vài ngày.
    """
    from kit.enrich.schema import cover_of_row

    d = tag_hook(df).copy()
    d["cover"] = d.apply(cover_of_row, axis=1)
    have = d[d["cover"].astype(str).str.strip() != ""].copy()
    coverage = len(have) / len(d) if len(d) else 0.0
    if have.empty:
        raise ValueError(
            "Không có ảnh cover nào — nền tảng này không xuất ảnh bìa "
            "(Weibo/Tieba/Zhihu). Dùng nền tảng có cover: Douyin, XHS, "
            "Bilibili, Kuaishou.")

    if "eng_total" in have.columns:
        have["pct_rank"] = (have["eng_total"].rank(pct=True) * 100).round(1)
        have = have.sort_values("eng_total", ascending=False)
    board = _take(have, top)

    kinds = _group_metrics(have, "format")
    cols = [c for c in ["cover", "hook_text", "format", "hook_type", "pct_rank",
                        "eng_total", "platform", "source_keyword", "nickname",
                        "aweme_url", "note_url", "video_url"] if c in board.columns]
    _out(board[cols].rename(columns={"cover": "cover_url_c"}),
         "CS15_cover_moodboard.xlsx")
    return {"board": board, "coverage": coverage, "formats": kinds,
            "total": len(d)}


# ============================================================================
# CLI
# ============================================================================

def _parse_args(argv: list[str]) -> tuple[list[str], str | None, bool, bool]:
    """Tách cờ tuỳ chọn (--to <đích>, --dry-run, --notify) khỏi đối số vị trí."""
    to: str | None = None
    dry_run = False
    notify = False
    pos: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--to":
            if i + 1 >= len(argv):
                print("Thiếu giá trị cho --to (vd: --to supabase)"); sys.exit(1)
            to = argv[i + 1]; i += 2
        elif a == "--dry-run":
            dry_run = True; i += 1
        elif a == "--notify":
            notify = True; i += 1
        else:
            pos.append(a); i += 1
    return pos, to, dry_run, notify


def main():
    pos, to, dry_run, notify = _parse_args(sys.argv[1:])
    if len(pos) < 2:
        print(__doc__); sys.exit(0)
    cmd, path = pos[0], pos[1]
    df = load(path)

    writer = None
    if to == "supabase":
        from kit.storage.supabase_writer import SupabaseWriter
        writer = SupabaseWriter(dry_run=dry_run)
    elif to is not None:
        print(f"Đích lưu chưa hỗ trợ: {to} (hiện có: supabase)"); sys.exit(1)

    if cmd == "trend":
        res = trend_radar(df)
        if writer:
            writer.upsert_trend_posts(res["top_posts"])
        if notify:
            from kit.webhook import notify_trend_brief
            fmt = res["formats"]
            top_fmt = fmt.iloc[0]["format"] if len(fmt) else "khác"
            notify_trend_brief(
                f"Trend radar: {len(res['top_posts'])} bài top, "
                f"format thắng thế: {top_fmt}.")
    elif cmd == "insight":
        comment_bank(df)
    elif cmd == "koc":
        s = koc_scorecard(df)
        if writer and len(s):
            writer.upsert_koc(s)
        if notify and len(s):
            from kit.webhook import notify_rising_koc
            rising = s[s["rising"]]
            notify_rising_koc(rising[["creator", "so_video", "eng_tb",
                                      "velocity", "diem_tong"]]
                              .to_dict(orient="records"))
    elif cmd == "opportunity":
        opportunity_map(df)
    elif cmd == "seasonal":
        seasonal_radar(df)
    elif cmd == "price":
        p = price_intel(df)
        if writer and len(p):
            writer.upsert_price(p)
    elif cmd == "angle":
        out_path = export_angles(df)
        if writer:
            with open(out_path, encoding="utf-8") as f:
                records = [json.loads(line) for line in f if line.strip()]
            writer.upsert_angles(records)
    elif cmd == "sov":
        bm = json.loads(Path(pos[2]).read_text(encoding="utf-8")) \
             if len(pos) > 2 else {}
        g = sov(df, bm)
        if writer and len(g):
            writer.upsert_sov(g)
        if notify:
            from kit.webhook import notify_sov_updated
            notify_sov_updated()
    else:
        print(f"Lệnh không hợp lệ: {cmd}"); sys.exit(1)


if __name__ == "__main__":
    main()
