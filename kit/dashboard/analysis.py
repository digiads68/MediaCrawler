# -*- coding: utf-8 -*-
"""
Phân tích chuyên sâu — phần "chất" của từng loại dashboard.

Khác với metrics.py (chỉ số tổng quan dùng chung), module này tính những thứ
biến số liệu thành **quyết định content**:

- `benchmark`      : mốc P25/P50/P75/P90 của ngách → biết thế nào là "tốt".
- `outliers`       : bài vượt trội so với trung vị (ngách hoặc chính kênh).
- `format_matrix`  : format nào thắng ở từ khoá nào + phát hiện "khe trống".
- `hook_performance`: công thức hook nào thực sự hiệu quả (không chỉ đếm).
- `posting_heatmap`: giờ × thứ nên đăng.
- `creator_profile`: chân dung 1 kênh (nhịp đăng, đà tăng, bài bứt phá...).
- `comment_mining` : Voice-of-Customer từ sheet Comments (câu hỏi, chủ đề, đau).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import pandas as pd

from kit.dashboard.metrics import HOOK_PATTERNS

# Thứ trong tuần (0 = Thứ 2 theo pandas dayofweek).
WEEKDAYS_VI = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]

# Ngưỡng coi là "bứt phá" so với trung vị.
BREAKOUT_X = 2.0

# Dấu hiệu câu hỏi trong bình luận (ZH + VI + dấu câu) → mỏ ý tưởng content.
_QUESTION_HINTS = ["?", "？", "吗", "怎么", "如何", "为什么", "多少", "哪",
                   "sao", "gì", "thế nào", "bao nhiêu", "ở đâu", "có ai"]

# Từ khoá biểu thị nỗi đau / mong muốn (gợi ý angle).
_PAIN_HINTS = ["难", "累", "坑", "失败", "焦虑", "没钱", "骗", "后悔", "vất vả",
               "khó", "thất bại", "lo", "mệt", "lừa"]
_DESIRE_HINTS = ["想", "求", "教教", "怎么学", "希望", "muốn", "cần", "xin",
                 "chỉ mình", "mong"]

# Stopword tối giản (ZH thường + VI) để lọc n-gram rác.
_STOP = {"的", "了", "是", "我", "你", "他", "在", "和", "就", "都", "也",
         "有", "不", "这", "那", "个", "一", "很", "吗", "啊", "吧", "呢",
         "và", "là", "của", "cho", "với", "một", "các", "được", "này",
         "thì", "mà", "không", "có", "đã", "rất", "để", "nhưng"}

_TOKEN_RE = re.compile(r"[0-9A-Za-zÀ-ỹ]+|[一-鿿]{2,4}")


# ---------------------------------------------------------------------------
# 1. Benchmark ngách
# ---------------------------------------------------------------------------

def benchmark(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """
    Mốc phân vị cho từng chỉ số → team biết "bao nhiêu mới gọi là tốt".

    Trả {chỉ_số: {p25, p50, p75, p90}}.
    """
    out: dict[str, dict[str, float]] = {}
    cols = ["liked_count", "collected_count", "share_count", "comment_count",
            "eng_total", "save_rate", "share_rate"]
    for c in cols:
        if c not in df.columns:
            continue
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if s.empty:
            continue
        out[c] = {
            "p25": float(s.quantile(0.25)),
            "p50": float(s.quantile(0.50)),
            "p75": float(s.quantile(0.75)),
            "p90": float(s.quantile(0.90)),
        }
    return out


def benchmark_by_platform(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """
    Mốc trung vị/P75/P90 của `eng_total` cho TỪNG nền tảng.

    Cần thiết vì thang tương tác giữa các nền tảng lệch nhau rất xa (một video
    Bilibili triệu view vs một note XHS vài nghìn) — so chung sẽ sai lệch.
    """
    out: dict[str, dict[str, float]] = {}
    if "platform" not in df.columns or "eng_total" not in df.columns:
        return out
    for plat, g in df.groupby("platform"):
        s = pd.to_numeric(g["eng_total"], errors="coerce").dropna()
        if s.empty:
            continue
        out[str(plat)] = {"n": float(len(s)), "p50": float(s.median()),
                          "p75": float(s.quantile(0.75)),
                          "p90": float(s.quantile(0.90))}
    return out


def add_outlier_ratio(df: pd.DataFrame, *, by: str | None = None) -> pd.DataFrame:
    """
    Thêm `out_ratio` = eng_total / trung vị (của toàn ngách, hoặc theo nhóm `by`)
    và `breakout` = vượt BREAKOUT_X lần.

    Dùng cho dashboard search (so với ngách) và creator (so với chính kênh).
    """
    d = df.copy()
    if "eng_total" not in d.columns:
        d["out_ratio"] = pd.NA
        d["breakout"] = False
        return d
    if by and by in d.columns:
        med = d.groupby(by)["eng_total"].transform("median")
    else:
        med = pd.Series(float(d["eng_total"].median()), index=d.index)
    med = med.replace(0, pd.NA)
    d["out_ratio"] = (d["eng_total"] / med).round(2)
    d["breakout"] = d["out_ratio"] >= BREAKOUT_X
    return d


# ---------------------------------------------------------------------------
# 2. Ma trận format × từ khoá + khe trống nội dung
# ---------------------------------------------------------------------------

def format_matrix(df: pd.DataFrame, *, max_kw: int = 6,
                  max_fmt: int = 8) -> dict[str, Any]:
    """
    Format nào thắng ở từ khoá nào (giá trị = tương tác TB) + phát hiện ô
    "khe trống": tương tác cao nhưng ít bài → nên làm ngay.
    """
    if not {"format", "source_keyword", "eng_total"} <= set(df.columns):
        return {"cells": {}, "counts": {}, "rows": [], "cols": [], "gaps": []}
    d = df[df["source_keyword"].replace("", pd.NA).notna()]
    if d.empty:
        return {"cells": {}, "counts": {}, "rows": [], "cols": [], "gaps": []}
    cols = list(d["source_keyword"].value_counts().head(max_kw).index)
    rows = list(d["format"].value_counts().head(max_fmt).index)
    cells: dict[tuple[str, str], float] = {}
    counts: dict[tuple[str, str], int] = {}
    for f in rows:
        for k in cols:
            sub = d[(d["format"] == f) & (d["source_keyword"] == k)]
            if sub.empty:
                continue
            cells[(f, k)] = float(sub["eng_total"].mean())
            counts[(f, k)] = int(len(sub))
    # Khe trống: eng TB >= trung vị toàn bộ ô, mà số bài <= trung vị số bài.
    if cells:
        med_eng = pd.Series(list(cells.values())).median()
        med_n = pd.Series(list(counts.values())).median()
        gaps = [{"format": f, "keyword": k, "eng": v, "n": counts[(f, k)]}
                for (f, k), v in cells.items()
                if v >= med_eng and counts[(f, k)] <= med_n]
        gaps.sort(key=lambda x: x["eng"], reverse=True)
    else:
        gaps = []
    return {"cells": cells, "counts": counts, "rows": rows, "cols": cols,
            "gaps": gaps[:5]}


# ---------------------------------------------------------------------------
# 3. Hiệu quả công thức hook (không chỉ đếm số bài)
# ---------------------------------------------------------------------------

def hook_performance(df: pd.DataFrame, *, top_examples: int = 3) -> list[dict[str, Any]]:
    """
    Với mỗi công thức hook: số bài, tương tác TB & trung vị, save-rate TB,
    tỷ lệ bài vào top 25% ngách ("tỷ lệ thắng"), và ví dụ tốt nhất.

    Sắp theo tương tác **trung vị** (bền hơn TB, không bị 1 bài viral kéo lệch).
    """
    if "eng_total" not in df.columns:
        return []
    text = (df.get("title", pd.Series(dtype=str)).fillna("") + " "
            + df.get("desc", pd.Series(dtype=str)).fillna("")).str.lower()
    p75 = float(df["eng_total"].quantile(0.75))
    d_sorted = df.sort_values("eng_total", ascending=False)
    out: list[dict[str, Any]] = []
    for name, kws in HOOK_PATTERNS.items():
        mask = text.apply(lambda s, kws=kws: any(k in s for k in kws))
        sub = df[mask]
        if sub.empty:
            continue
        wins = int((sub["eng_total"] >= p75).sum())
        ex_idx = [i for i in d_sorted.index if bool(mask.get(i, False))][:top_examples]
        out.append({
            "name": name,
            "n": int(len(sub)),
            "eng_mean": float(sub["eng_total"].mean()),
            "eng_median": float(sub["eng_total"].median()),
            "save_rate": float(pd.to_numeric(sub.get("save_rate"),
                                             errors="coerce").mean()) if "save_rate" in sub else 0.0,
            "win_rate": wins / len(sub),
            "examples": [{
                "title": str(df.at[i, "title"])[:140],
                "eng": float(df.at[i, "eng_total"]),
                "url": str(df.at[i, "content_url"]) if "content_url" in df.columns else "",
            } for i in ex_idx],
        })
    out.sort(key=lambda x: x["eng_median"], reverse=True)
    return out


# ---------------------------------------------------------------------------
# 4. Heatmap thời điểm đăng
# ---------------------------------------------------------------------------

def posting_heatmap(df: pd.DataFrame, *, metric: str = "count",
                    bucket_hours: int = 3, min_n: int = 3) -> dict[str, Any]:
    """
    Ma trận [khung giờ] × [thứ]: số bài (metric="count") hoặc tương tác TB
    (metric="eng"). Gom giờ theo khung `bucket_hours` cho dễ đọc.

    `best` chỉ lấy từ ô có **≥ min_n bài** — tránh kết luận "giờ vàng" từ đúng
    một bài viral. Nếu không ô nào đủ mẫu, trả ô cao nhất kèm `low_confidence`.
    """
    empty = {"matrix": [], "rows": [], "cols": WEEKDAYS_VI, "best": None}
    if "created_at" not in df.columns or df["created_at"].isna().all():
        return empty
    d = df.dropna(subset=["created_at"]).copy()
    d["_dow"] = d["created_at"].dt.dayofweek
    d["_hb"] = (d["created_at"].dt.hour // bucket_hours) * bucket_hours
    buckets = list(range(0, 24, bucket_hours))
    rows = [f"{b:02d}-{min(b + bucket_hours, 24):02d}h" for b in buckets]
    matrix: list[list[float]] = []
    cells: list[dict[str, Any]] = []
    for b in buckets:
        row = []
        for dw in range(7):
            sub = d[(d["_hb"] == b) & (d["_dow"] == dw)]
            if sub.empty:
                row.append(0.0)
                continue
            v = float(len(sub)) if metric == "count" else float(sub["eng_total"].mean())
            row.append(v)
            cells.append({"value": v, "n": int(len(sub)),
                          "hour": f"{b:02d}-{min(b + bucket_hours, 24):02d}h",
                          "dow": WEEKDAYS_VI[dw]})
        matrix.append(row)
    if not cells:
        return empty
    solid = [c for c in cells if c["n"] >= min_n]
    if solid:
        best = max(solid, key=lambda c: c["value"]) | {"low_confidence": False}
    else:
        best = max(cells, key=lambda c: c["value"]) | {"low_confidence": True}
    return {"matrix": matrix, "rows": rows, "cols": WEEKDAYS_VI, "best": best}


# ---------------------------------------------------------------------------
# 5. Chân dung 1 kênh
# ---------------------------------------------------------------------------

def creator_profile(df: pd.DataFrame, creator_hash: str) -> dict[str, Any]:
    """
    Chân dung đầy đủ 1 kênh: KPI, nhịp đăng, đà tăng, bài bứt phá, format &
    hook hay dùng, timeline từng bài.
    """
    d = df[df["creator_hash"] == creator_hash].copy()
    if d.empty:
        return {}
    d = d.sort_values("created_at") if "created_at" in d.columns else d
    eng = d["eng_total"]
    med = float(eng.median())

    # Nhịp đăng: số ngày trung vị giữa 2 bài liên tiếp.
    cadence = None
    if "created_at" in d.columns and d["created_at"].notna().sum() >= 2:
        gaps = d["created_at"].dropna().diff().dt.total_seconds().dropna() / 86400
        gaps = gaps[gaps > 0]
        if not gaps.empty:
            cadence = float(gaps.median())

    # Đà tăng: nửa sau so với nửa đầu (theo thời gian).
    half = len(d) // 2
    velocity = 1.0
    if half >= 1:
        v1 = float(eng.iloc[:half].mean())
        v2 = float(eng.iloc[half:].mean())
        velocity = round(v2 / v1, 2) if v1 > 0 else 1.0

    consistency = consistency_score(eng)

    # Bài bứt phá của chính kênh.
    d["_ratio"] = (eng / med).round(2) if med > 0 else 0
    breakouts = d[d["_ratio"] >= BREAKOUT_X].sort_values("_ratio", ascending=False)

    # Timeline điểm
    save_max = float(d.get("collected_count", pd.Series([0])).max() or 1)
    points = []
    for _, r in d.iterrows():
        ts = r.get("created_at")
        if pd.isna(ts):
            continue
        points.append({
            "ts": ts.timestamp(),
            "date": f"{ts:%d/%m/%y}",
            "eng": float(r["eng_total"]),
            "rel_save": float(r.get("collected_count", 0) or 0) / save_max
            if save_max else 0,
            "title": str(r.get("title", ""))[:80],
        })

    # Format & hook hay dùng
    fmt_mix = [(str(k), float(v)) for k, v in
               d["format"].value_counts().head(6).items()] if "format" in d else []
    fmt_perf = []
    if "format" in d.columns:
        g = d.groupby("format")["eng_total"].agg(["size", "mean"])
        fmt_perf = [(str(i), float(row["mean"])) for i, row in
                    g.sort_values("mean", ascending=False).head(6).iterrows()]

    return {
        "creator_hash": creator_hash,
        "nickname": str(d["nickname"].iloc[0]) if "nickname" in d else "",
        "platform": str(d["platform"].iloc[0]) if "platform" in d else "",
        "n_posts": int(len(d)),
        "eng_mean": float(eng.mean()),
        "eng_median": med,
        "eng_total": float(eng.sum()),
        "cadence_days": cadence,
        "velocity": velocity,
        "consistency": round(consistency, 2),
        "best_post": _post_brief(d.loc[eng.idxmax()]) if len(d) else None,
        "worst_post": _post_brief(d.loc[eng.idxmin()]) if len(d) else None,
        "breakouts": [_post_brief(r) for _, r in breakouts.head(5).iterrows()],
        "points": points,
        "format_mix": fmt_mix,
        "format_perf": fmt_perf,
        "posts": d.sort_values("eng_total", ascending=False),
        "span": (f"{d['created_at'].min():%d/%m/%y} → {d['created_at'].max():%d/%m/%y}"
                 if "created_at" in d.columns and d["created_at"].notna().any() else "—"),
    }


def consistency_score(values: pd.Series) -> float:
    """
    Độ đều (0..1) theo **hệ số phân tán tứ phân vị**: 1 - (Q3-Q1)/(Q3+Q1).

    Dùng tứ phân vị thay cho std/mean vì chỉ 1 bài viral là std/mean vọt lên,
    khiến mọi kênh có bài bứt phá đều bị chấm 0 — che mất thông tin thật.
    """
    s = pd.to_numeric(values, errors="coerce").dropna()
    if len(s) < 2:
        return 0.0
    q1, q3 = float(s.quantile(0.25)), float(s.quantile(0.75))
    if q1 + q3 <= 0:
        return 0.0
    return round(max(0.0, min(1.0, 1 - (q3 - q1) / (q3 + q1))), 2)


def _post_brief(r: pd.Series) -> dict[str, Any]:
    """Rút gọn 1 bài cho phần hiển thị."""
    created = r.get("created_at")
    return {
        "title": str(r.get("title", ""))[:160],
        "eng": float(r.get("eng_total", 0) or 0),
        "like": float(r.get("liked_count", 0) or 0),
        "save": float(r.get("collected_count", 0) or 0),
        "share": float(r.get("share_count", 0) or 0),
        "comment": float(r.get("comment_count", 0) or 0),
        "ratio": float(r.get("_ratio", 0) or 0),
        "url": str(r.get("content_url", "") or ""),
        "format": str(r.get("format", "") or ""),
        "date": "" if pd.isna(created) else f"{created:%d/%m/%y}",
    }


def creator_leaderboard(df: pd.DataFrame, *, min_posts: int = 2,
                        top: int = 25) -> pd.DataFrame:
    """Bảng so sánh nhiều kênh (đã có ở metrics, bản này thêm nhịp đăng)."""
    if "creator_hash" not in df.columns:
        return pd.DataFrame()
    d = df[df["creator_hash"].replace("", pd.NA).notna()]
    rows = []
    for ch, g in d.groupby("creator_hash"):
        if len(g) < min_posts:
            continue
        p = creator_profile(df, ch)
        if not p:
            continue
        rows.append({
            "creator_hash": ch, "nickname": p["nickname"],
            "platform": p["platform"], "n_posts": p["n_posts"],
            "eng_mean": p["eng_mean"], "eng_median": p["eng_median"],
            "eng_total": p["eng_total"], "cadence_days": p["cadence_days"],
            "velocity": p["velocity"], "consistency": p["consistency"],
            "n_breakouts": len(p["breakouts"]),
        })
    if not rows:
        return pd.DataFrame()
    return (pd.DataFrame(rows).sort_values("eng_total", ascending=False)
            .head(top).reset_index(drop=True))


# ---------------------------------------------------------------------------
# 6. Voice of Customer từ bình luận
# ---------------------------------------------------------------------------

def comment_mining(cm: pd.DataFrame, *, top: int = 15) -> dict[str, Any]:
    """
    Khai thác sheet Comments: bình luận top theo like, **câu hỏi của khán giả**
    (mỏ ý tưởng content), từ khoá nổi bật, tín hiệu nỗi đau/mong muốn.

    cm cần cột: content, like_count, sub_comment_count, item_id (đã map).
    """
    if cm is None or cm.empty or "content" not in cm.columns:
        return {"n": 0, "n_unique": 0, "top": [], "questions": [],
                "keywords": [], "pain": [], "desire": [], "reply_rate": 0.0}
    d = cm.copy()
    d["content"] = d["content"].fillna("").astype(str)
    d = d[d["content"].str.strip() != ""]
    if d.empty:
        return {"n": 0, "n_unique": 0, "top": [], "questions": [],
                "keywords": [], "pain": [], "desire": [], "reply_rate": 0.0}
    for c in ("like_count", "sub_comment_count"):
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)
        else:
            d[c] = 0

    lc = d["content"].str.lower()
    is_q = lc.apply(lambda s: any(h in s for h in _QUESTION_HINTS))
    pain = lc.apply(lambda s: any(h in s for h in _PAIN_HINTS))
    desire = lc.apply(lambda s: any(h in s for h in _DESIRE_HINTS))

    # Đếm số lần mỗi nội dung lặp lại — nhiều người nói cùng một câu chính là
    # tín hiệu nhu cầu mạnh, nên gộp lại và hiện "xuất hiện N lần" thay vì
    # liệt kê trùng lặp.
    norm = d["content"].str.strip().str.lower()
    repeat = norm.value_counts()

    def brief(rows: pd.DataFrame, *, dedupe: bool = True) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for _, r in rows.iterrows():
            key = str(r["content"]).strip().lower()
            if dedupe:
                if key in seen:
                    continue
                seen.add(key)
            out.append({"text": str(r["content"])[:300],
                        "like": float(r["like_count"]),
                        "replies": float(r["sub_comment_count"]),
                        "repeat": int(repeat.get(key, 1)),
                        "nickname": str(r.get("nickname", "") or "")})
        return out

    counter: Counter[str] = Counter()
    for s in d["content"]:
        for tok in _TOKEN_RE.findall(str(s)):
            t = tok.strip().lower()
            if len(t) > 1 and t not in _STOP:
                counter[t] += 1

    def ranked(mask: pd.Series | None = None) -> pd.DataFrame:
        sub = d if mask is None else d[mask]
        return sub.sort_values("like_count", ascending=False)

    # Cắt `top` SAU khi gộp trùng để luôn đủ số mục khác biệt.
    return {
        "n": int(len(d)),
        "n_unique": int(norm.nunique()),
        "reply_rate": float((d["sub_comment_count"] > 0).mean()),
        "top": brief(ranked())[:top],
        "questions": brief(ranked(is_q))[:top],
        "keywords": [(k, float(v)) for k, v in counter.most_common(15)],
        "pain": brief(ranked(pain))[:8],
        "desire": brief(ranked(desire))[:8],
    }


def engagement_anatomy(r: pd.Series, bm: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    """
    Giải phẫu tương tác 1 bài so với mốc ngách (cho dashboard video).

    Thanh vẽ theo **tỷ lệ so với P50** trên một thang chung cho cả 4 chỉ số của
    bài đó — nhờ vậy thấy ngay chỉ số nào là điểm mạnh thật (nếu lấy thang riêng
    theo từng chỉ số thì mọi bài vượt trội đều đầy thanh, không phân biệt được).
    Vạch dọc = mốc P50 (1×).
    """
    labels = {"liked_count": "Like", "collected_count": "Save",
              "share_count": "Share", "comment_count": "Bình luận"}
    rows = []
    for col, lb in labels.items():
        if col not in bm:
            continue
        v = float(r.get(col, 0) or 0)
        ref = float(bm[col]["p50"])
        ratio = v / ref if ref > 0 else 0.0
        rows.append({"label": lb, "ratio": ratio, "raw": v,
                     "text": f"{ratio:.1f}× P50" if ref > 0 else "—"})
    if not rows:
        return []
    vmax = max(max(x["ratio"] for x in rows), 1.0)
    return [{"label": x["label"], "value": x["ratio"], "ref": 1.0,
             "vmax": vmax, "text": x["text"]} for x in rows]
