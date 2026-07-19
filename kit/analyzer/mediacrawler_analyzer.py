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
from kit.enrich.normalize import COUNT_COLS, FORMAT_RULES, normalize  # noqa: E402,F401

# ============================================================================
# 0. TIỆN ÍCH CHUNG — nạp & chuẩn hoá dữ liệu MediaCrawler
# ============================================================================

PRICE_PATTERNS = [
    r"(\d+(?:\.\d+)?)\s*元", r"¥\s*(\d+(?:\.\d+)?)", r"(\d+(?:\.\d+)?)\s*块",
    r"(\d{1,3}(?:[.,]\d{3})+)\s*[dđ]", r"(\d+)\s*k\b",
]
PROMO_KEYWORDS = ["买一送一", "第二件", "折", "券", "满减", "秒杀", "限时",
                  "freeship", "sale", "giảm", "tặng", "voucher", "flash"]


def load(path: str | Path) -> pd.DataFrame:
    """Nạp file MediaCrawler xuất ra (xlsx / jsonl / csv) thành DataFrame."""
    p = Path(path)
    if p.suffix == ".xlsx":
        df = pd.read_excel(p)
    elif p.suffix in (".jsonl", ".json"):
        df = pd.read_json(p, lines=(p.suffix == ".jsonl"))
    elif p.suffix == ".csv":
        df = pd.read_csv(p)
    else:
        raise ValueError(f"Định dạng chưa hỗ trợ: {p.suffix}")
    return normalize(df)


def _out(df: pd.DataFrame, name: str) -> Path:
    out = Path("reports"); out.mkdir(exist_ok=True)
    p = out / name
    if p.suffix == ".xlsx":
        df.to_excel(p, index=False)
    else:
        df.to_csv(p, index=False)
    print(f"[✓] Xuất: {p}  ({len(df)} dòng)")
    return p


# ============================================================================
# CS1 + CS10 · TREND RADAR & SOUND WATCHLIST
# ============================================================================

def trend_radar(df: pd.DataFrame, top: int = 20) -> dict:
    """
    Chấm điểm trend cho từng bài:
      trend_score = 0.4*save_norm + 0.3*share_norm + 0.2*comment_norm + 0.1*like_norm
    (save & share nặng nhất — báo hiệu format đáng bản địa hoá).
    Đồng thời gom sound xuất hiện lặp -> watchlist nhạc trending.
    """
    d = df.copy()
    for col, w in [("collected_count", .4), ("share_count", .3),
                   ("comment_count", .2), ("liked_count", .1)]:
        if col in d.columns and d[col].max() > 0:
            d[f"_{col}"] = w * d[col] / d[col].max()
        else:
            d[f"_{col}"] = 0
    d["trend_score"] = (d["_collected_count"] + d["_share_count"]
                        + d["_comment_count"] + d["_liked_count"]) * 100
    cols = [c for c in ["title", "format", "source_keyword", "liked_count",
                        "collected_count", "share_count", "trend_score",
                        "aweme_url", "note_url", "video_url"] if c in d.columns]
    top_posts = d.sort_values("trend_score", ascending=False).head(top)[cols]

    # Format nào đang thắng
    fmt = (d.groupby("format")
             .agg(so_bai=("format", "size"),
                  diem_tb=("trend_score", "mean"),
                  save_tb=("collected_count", "mean"))
             .sort_values("diem_tb", ascending=False).reset_index())

    # Sound watchlist (CS10)
    sounds = pd.DataFrame()
    if "music_download_url" in d.columns:
        s = d[d["music_download_url"].notna() & (d["music_download_url"] != "")]
        sounds = (s.groupby("music_download_url")
                    .agg(so_video=("music_download_url", "size"),
                         eng_tb=("eng_total", "mean"))
                    .query("so_video >= 2")
                    .sort_values(["so_video", "eng_tb"], ascending=False)
                    .reset_index())
    _out(top_posts, "CS1_trend_top_posts.xlsx")
    _out(fmt, "CS1_trend_formats.xlsx")
    if len(sounds):
        _out(sounds, "CS10_sound_watchlist.xlsx")
    return {"top_posts": top_posts, "formats": fmt, "sounds": sounds}


# ============================================================================
# CS2 · INSIGHT / COMMENT BANK
# ============================================================================

def comment_bank(df: pd.DataFrame, min_like: int = 1, top: int = 800) -> pd.DataFrame:
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
    d = d.head(top).reset_index(drop=True)
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
    text = (df.get("title", "").fillna("") + " " + df.get("desc", "").fillna("")).str.lower()
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
                "platform": "dy",
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
