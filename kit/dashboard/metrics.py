# -*- coding: utf-8 -*-
"""
Tính toán chỉ số cho dashboard đa nền tảng.

Nạp nhiều file raw → adapter → gộp → normalize (dùng lại kit.enrich) → tính:
KPI tổng quan, cơ cấu nền tảng/từ khoá/format, timeline, bảng xếp hạng trend,
scorecard creator (đối thủ), mỏ hook/hashtag, và bản đồ cơ hội ngách.

Nguyên tắc: KHÔNG lặp logic chuẩn hoá — import từ kit.enrich.normalize/velocity.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from kit.dashboard.adapters import PLATFORM_LABELS, adapt
from kit.enrich.normalize import normalize
from kit.enrich.velocity import weekly_velocity

# Trọng số điểm trend (save & share nặng nhất — báo hiệu format đáng nhân bản).
TREND_WEIGHTS: list[tuple[str, float]] = [
    ("collected_count", 0.35), ("share_count", 0.30),
    ("comment_count", 0.20), ("liked_count", 0.15),
]

_HASHTAG_RE = re.compile(r"#([^\s#＃]+)")
_NUM_RE = re.compile(r"\d")

# Nhóm công thức hook (nhận diện theo từ khoá trong tiêu đề/mô tả ZH + VI).
HOOK_PATTERNS: dict[str, list[str]] = {
    "Con số / liệt kê": ["个", "招", "步", "天", "块", "元", "万", "top", "cách", "bước"],
    "Câu hỏi / tò mò": ["?", "？", "如何", "怎么", "为什么", "吗", "tại sao", "làm sao"],
    "Cảnh báo / nỗi đau": ["别", "千万", "避坑", "踩雷", "后悔", "浪费", "错", "đừng", "sai lầm"],
    "Hướng dẫn / dạy": ["教你", "教程", "手把手", "全流程", "拆解", "hướng dẫn", "dạy"],
    "Khoe kết quả": ["月入", "赚", "变现", "收入", "月赚", "涨粉", "kiếm", "thu nhập"],
    "Bí mật / độc quyền": ["秘密", "私藏", "干货", "揭秘", "内幕", "bí mật", "độc quyền"],
}


def load_unified(paths: list[str | Path]) -> pd.DataFrame:
    """Nạp + hợp nhất + chuẩn hoá nhiều file raw thành 1 DataFrame."""
    frames: list[pd.DataFrame] = []
    for p in paths:
        p = Path(p)
        if p.suffix == ".xlsx":
            raw = pd.read_excel(p)
        elif p.suffix in (".jsonl", ".json"):
            raw = pd.read_json(p, lines=(p.suffix == ".jsonl"))
        elif p.suffix == ".csv":
            raw = pd.read_csv(p)
        else:
            raise ValueError(f"Định dạng chưa hỗ trợ: {p.suffix}")
        frames.append(adapt(raw, source=str(p)))
    if not frames:
        raise ValueError("Không có file nào để nạp.")
    df = pd.concat(frames, ignore_index=True)
    df = normalize(df)
    df = dedupe(df)
    return add_trend_score(df)


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Gộp bài trùng (cùng nền tảng + item_id) — một video xuất hiện ở nhiều
    file/từ khoá chỉ tính 1 lần. Giữ dòng có tương tác cao nhất làm đại diện
    (mốc đo mới nhất), tránh đếm lặp ở KPI/leaderboard/hook.
    """
    if "item_id" not in df.columns:
        return df
    d = df.copy()
    d["item_id"] = d["item_id"].astype(str)
    d = d[d["item_id"].str.len() > 0]
    metric = d["eng_total"] if "eng_total" in d.columns else d.get("liked_count", 0)
    d = (d.assign(_e=metric)
           .sort_values("_e", ascending=False)
           .drop_duplicates(["platform", "item_id"])
           .drop(columns="_e")
           .reset_index(drop=True))
    return d


def add_trend_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Thêm cột `trend_score` (0–100), chuẩn hoá theo TỪNG nền tảng để công bằng
    (một video Bilibili triệu view không đè bẹp toàn bộ bài XHS).
    """
    d = df.copy()
    d["trend_score"] = 0.0
    if "platform" not in d.columns:
        d["platform"] = "unknown"
    for _, idx in d.groupby("platform").groups.items():
        sub = d.loc[idx]
        score = pd.Series(0.0, index=idx)
        for col, w in TREND_WEIGHTS:
            if col in sub.columns:
                mx = float(sub[col].max())
                if mx > 0:
                    score = score + w * sub[col].astype(float) / mx
        d.loc[idx, "trend_score"] = (score * 100).round(1)
    return d


def _kpis(df: pd.DataFrame) -> list[dict[str, str]]:
    """Bộ thẻ KPI tổng quan."""
    total = len(df)
    platforms = df["platform"].nunique()
    keywords = df["source_keyword"].replace("", pd.NA).nunique()
    creators = df["creator_hash"].replace("", pd.NA).nunique()
    eng = float(df["eng_total"].sum())
    eng_avg = eng / total if total else 0
    if "created_at" in df.columns and df["created_at"].notna().any():
        lo = df["created_at"].min()
        hi = df["created_at"].max()
        span = f"{lo:%d/%m/%y} → {hi:%d/%m/%y}"
    else:
        span = "—"
    return [
        {"label": "Tổng bài", "value": f"{total:,}",
         "note": f"{platforms} nền tảng · {keywords} từ khoá"},
        {"label": "Tổng tương tác", "value": _human(eng),
         "note": f"TB {_human(eng_avg)}/bài"},
        {"label": "Creator theo dõi", "value": f"{creators:,}",
         "note": "đã ẩn danh (NĐ 13/2023)"},
        {"label": "Khoảng thời gian", "value": span,
         "note": "theo ngày đăng"},
    ]


def _mix(df: pd.DataFrame, col: str, *, label_map: dict | None = None,
         top: int = 8) -> list[tuple[str, float]]:
    """Cơ cấu (đếm bài) theo 1 cột — trả [(nhãn, số bài)]."""
    s = df[col].replace("", pd.NA).dropna()
    vc = s.value_counts().head(top)
    out = []
    for k, v in vc.items():
        lb = label_map.get(k, str(k)) if label_map else str(k)
        out.append((lb, float(v)))
    return out


def _timeline(df: pd.DataFrame) -> dict[str, Any]:
    """Chuỗi số bài theo tuần, tách theo nền tảng (line chart đa chuỗi)."""
    if "week" not in df.columns or df["week"].isna().all():
        return {"x_labels": [], "series": []}
    d = df.dropna(subset=["week"])
    weeks = sorted(d["week"].unique())[-12:]  # 12 tuần gần nhất
    series = []
    for plat, g in d.groupby("platform"):
        counts = g[g["week"].isin(weeks)]["week"].value_counts()
        points = [float(counts.get(w, 0)) for w in weeks]
        if sum(points) > 0:
            series.append({"name": PLATFORM_LABELS.get(plat, plat),
                           "points": points})
    # Nhãn gọn "2026-W29" -> "W29"; nếu đông, thưa bớt để không chồng chữ.
    labels = [w.split("-")[-1] if "-" in w else w for w in weeks]
    step = max(1, len(labels) // 8)
    labels = [lb if i % step == 0 else "" for i, lb in enumerate(labels)]
    return {"x_labels": labels, "series": series}


def _trend_table(df: pd.DataFrame, top: int = 48) -> pd.DataFrame:
    """Bảng xếp hạng bài trend (cho lưới thẻ có nút n8n)."""
    cols = [c for c in [
        "platform", "content_kind", "item_id", "title", "desc", "format",
        "source_keyword", "liked_count", "collected_count", "share_count",
        "comment_count", "play_count", "trend_score", "save_rate",
        "share_rate", "eng_total", "nickname", "created_at", "cover_url",
        "content_url", "download_url", "music_url", "tags", "media_type",
    ] if c in df.columns]
    return df.sort_values("trend_score", ascending=False).head(top)[cols].reset_index(drop=True)


def _creator_scorecard(df: pd.DataFrame, top: int = 20) -> pd.DataFrame:
    """
    Scorecard creator (soi đối thủ): số video, tương tác TB, độ đều (nhất quán),
    đà tăng (velocity WoW), điểm trend TB. Chỉ giữ creator có ≥ 2 bài.
    """
    if "creator_hash" not in df.columns:
        return pd.DataFrame()
    d = df[df["creator_hash"].replace("", pd.NA).notna()]
    if d.empty:
        return pd.DataFrame()
    agg = (d.groupby(["creator_hash", "nickname", "platform"])
             .agg(so_video=("item_id", "size"),
                  eng_tb=("eng_total", "mean"),
                  eng_tong=("eng_total", "sum"),
                  trend_tb=("trend_score", "mean"),
                  eng_std=("eng_total", "std"))
             .reset_index())
    agg = agg[agg["so_video"] >= 2].copy()
    if agg.empty:
        return pd.DataFrame()
    # Độ đều = 1 - hệ số biến thiên (càng cao càng đều tay).
    agg["do_deu"] = (1 - agg["eng_std"] / agg["eng_tb"].replace(0, pd.NA)).clip(0, 1)
    agg["do_deu"] = agg["do_deu"].fillna(0).round(2)
    # Velocity WoW (dùng lại kit.enrich.velocity).
    try:
        vel = weekly_velocity(d, key="creator_hash", metric="eng_total")
        agg = agg.merge(vel[["creator_hash", "velocity"]], on="creator_hash", how="left")
    except Exception:  # noqa: BLE001 — thiếu created_at thì bỏ velocity
        agg["velocity"] = pd.NA
    agg["velocity"] = agg["velocity"].fillna(1.0)
    agg["eng_tb"] = agg["eng_tb"].round(0)
    agg["trend_tb"] = agg["trend_tb"].round(1)
    agg["platform"] = agg["platform"].map(lambda p: PLATFORM_LABELS.get(p, p))
    return (agg.sort_values("eng_tong", ascending=False).head(top)
               [["nickname", "platform", "so_video", "eng_tb", "eng_tong",
                 "trend_tb", "do_deu", "velocity"]].reset_index(drop=True))


def _hook_lab(df: pd.DataFrame) -> dict[str, Any]:
    """
    Mỏ hook/hashtag: top hashtag, phân bố công thức hook, và ví dụ tiêu biểu.
    """
    text_all = (df.get("title", pd.Series(dtype=str)).fillna("") + " "
                + df.get("desc", pd.Series(dtype=str)).fillna(""))
    # Hashtag
    tag_counter: Counter[str] = Counter()
    for t in text_all:
        for m in _HASHTAG_RE.findall(str(t)):
            tag_counter[m.strip()] += 1
    # Thêm tag_list (XHS) nếu có
    for tl in df.get("tags", pd.Series(dtype=str)).fillna(""):
        for tag in str(tl).split(","):
            tag = tag.strip()
            if tag:
                tag_counter[tag] += 1
    top_tags = [(k, float(v)) for k, v in tag_counter.most_common(12)]

    # Phân bố công thức hook (đếm bài khớp mỗi nhóm, có thể trùng nhóm).
    lc = text_all.str.lower()
    pattern_rows: list[tuple[str, float]] = []
    pattern_examples: dict[str, dict] = {}
    d_sorted = df.sort_values("trend_score", ascending=False)
    for name, kws in HOOK_PATTERNS.items():
        mask = lc.apply(lambda s, kws=kws: any(k in s for k in kws))
        n = int(mask.sum())
        if n:
            pattern_rows.append((name, float(n)))
            ex = d_sorted[mask.reindex(d_sorted.index, fill_value=False)]
            if not ex.empty:
                r = ex.iloc[0]
                pattern_examples[name] = {
                    "title": str(r.get("title", ""))[:120],
                    "score": float(r.get("trend_score", 0)),
                    "platform": PLATFORM_LABELS.get(r.get("platform"), ""),
                }
    pattern_rows.sort(key=lambda x: x[1], reverse=True)
    return {"top_tags": top_tags, "patterns": pattern_rows,
            "examples": pattern_examples}


def _opportunity(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Bản đồ cơ hội ngách theo từ khoá: trục X = số bài (độ bão hoà),
    trục Y = tương tác TB (sức hút). Ngách vàng = ít bài + tương tác cao.
    """
    if "source_keyword" not in df.columns:
        return []
    d = df[df["source_keyword"].replace("", pd.NA).notna()]
    if d.empty:
        return []
    agg = (d.groupby("source_keyword")
             .agg(so_bai=("item_id", "size"),
                  eng_tb=("eng_total", "mean"),
                  save_tb=("collected_count", "mean"))
             .reset_index())
    vol_med = agg["so_bai"].median()
    eng_med = agg["eng_tb"].median()

    def verdict(row: pd.Series) -> str:
        low_vol = row["so_bai"] <= vol_med
        high_eng = row["eng_tb"] >= eng_med
        if low_vol and high_eng:
            return "ngách vàng"
        if high_eng:
            return "đông nhưng hot"
        if low_vol:
            return "thử nghiệm"
        return "bão hoà"

    agg["verdict"] = agg.apply(verdict, axis=1)
    out = []
    for _, r in agg.iterrows():
        out.append({
            "keyword": str(r["source_keyword"]),
            "volume": int(r["so_bai"]),
            "eng": float(r["eng_tb"]),
            "save": float(r["save_tb"]),
            "verdict": str(r["verdict"]),
        })
    out.sort(key=lambda x: x["eng"], reverse=True)
    return out


def compute_sections(df: pd.DataFrame) -> dict[str, Any]:
    """Tổng hợp toàn bộ dữ liệu cần cho render dashboard."""
    return {
        "kpis": _kpis(df),
        "platform_mix": _mix(df, "platform", label_map=PLATFORM_LABELS),
        "keyword_mix": _mix(df, "source_keyword"),
        "format_mix": _mix(df, "format"),
        "timeline": _timeline(df),
        "trend": _trend_table(df),
        "creators": _creator_scorecard(df),
        "hooks": _hook_lab(df),
        "opportunity": _opportunity(df),
        "platforms_present": sorted(df["platform"].unique().tolist()),
        "keywords_present": sorted(
            df["source_keyword"].replace("", pd.NA).dropna().unique().tolist()),
    }


def _human(v: float) -> str:
    """Định dạng số gọn cho KPI: 12.3K / 1.2M."""
    v = float(v)
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"{v / 1_000:.1f}K"
    return f"{v:.0f}"
