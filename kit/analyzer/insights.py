# -*- coding: utf-8 -*-
"""
Kết luận & bằng chứng cho Trend Radar (luật cố định, không gọi AI).

Tách khỏi `mediacrawler_analyzer.py` vì đây là phần "đọc số ra quyết định":
mọi ngưỡng nằm ở đầu file để người làm nội dung chỉnh được mà không phải đọc
code phân tích. Các hàm chỉ THÊM cột / trả dict — không sửa dữ liệu gốc.

Nguồn các mốc (đo trên dữ liệu thật 09/2026, xem docs/PROJECT_STATUS.md):
  - lưu/like: Douyin #aigc 0,67 · Douyin creator giải trí 0,16 · XHS 编程副业 0,74
  - tuổi bài trong kết quả tìm kiếm: trung vị 70–158 ngày
  - HHI theo like/creator: 1.848 (#aigc) → 4.873 (Weibo 编程副业)
"""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
import pandas as pd

from kit.enrich.schema import split_hashtags

# --- Trọng số điểm trend (giữ tinh thần công thức cũ: lưu & chia sẻ nặng nhất) ---
TREND_WEIGHTS = {"save": 0.4, "share": 0.3, "comment": 0.2, "like": 0.1}

# --- Mục tiêu nội dung: tỷ lệ trên like, vượt >= GOAL_LIFT lần trung vị của bộ ---
GOAL_LIFT = 1.5
GOALS = {
    "luu": "Lưu",
    "ban_luan": "Bàn luận",
    "lan_truyen": "Lan truyền",
    "can_bang": "Cân bằng",
}

# --- Mức lưu/like theo nền tảng: (thấp dưới, cao từ). Mốc tạm, sẽ chỉnh khi đủ dữ liệu ---
SAVE_LEVELS = {"dy": (0.10, 0.30), "xhs": (0.30, 0.60), "bili": (0.15, 0.40),
               "ks": (0.05, 0.20)}
DEFAULT_SAVE_LEVEL = (0.10, 0.30)

# --- Tuổi bài ---
AGE_BUCKETS = [(0, 30, "< 30 ngày"), (30, 90, "30–90 ngày"), (90, 180, "90–180 ngày"),
               (180, 365, "180–365 ngày"), (365, math.inf, "> 1 năm")]
EVERGREEN_OLD_SHARE = 0.50      # >= 50% bài trên 90 ngày -> Evergreen
LEAN_EVERGREEN_SHARE = 0.35     # 35–50% -> Nghiêng evergreen
FLASH_NEW_SHARE = 0.50          # >= 50% bài dưới 30 ngày -> Flash

# --- Mức tập trung creator (HHI, thang 0–10.000) ---
HHI_SPREAD = 1500
HHI_CONCENTRATED = 2500
MIN_POSTS_FOR_CONCENTRATION = 50

# --- Hashtag ---
MIN_TAG_POSTS = 2
MIN_TAG_POSTS_TO_RECOMMEND = 3   # 2 bài + 1 bài viral là ra "gấp 20 lần" giả
TAG_UP = 1.2       # like trung vị của tag >= 1,2 lần cả bộ -> chip xanh
TAG_DOWN = 0.6     # <= 0,6 lần -> chip đỏ
SYSTEM_TAGS = {"内容启发搜索", "抖音精选", "dou十小助手", "dou+小助手", "抖音小助手",
               "热门", "上热门", "推荐", "fyp", "foryou"}


def _metric(d: pd.DataFrame, key: str) -> pd.Series | None:
    """Cột số của 1 chỉ số, ưu tiên cột canonical `m_*` (đúng cho mọi nền tảng)."""
    cands = {"like": ("m_like", "liked_count"), "save": ("m_save", "collected_count"),
             "comment": ("m_comment", "comment_count"), "share": ("m_share", "share_count")}[key]
    for c in cands:
        if c in d.columns:
            s = pd.to_numeric(d[c], errors="coerce")
            if s.notna().any():
                return s.fillna(0)
    return None


def percentile_trend_score(d: pd.DataFrame) -> pd.Series:
    """
    Điểm trend 0–100 theo THỨ HẠNG phần trăm của từng chỉ số.

    Công thức cũ chia cho giá trị lớn nhất: 1 bài viral (vd 18M view) ép mọi bài
    còn lại về gần 0 nên điểm không phân biệt được gì. Thứ hạng không bị lệch
    như vậy. Chỉ số nền tảng không có (Weibo không có lưu) bị bỏ và chia lại trọng số.
    """
    parts, weights = [], []
    for key, w in TREND_WEIGHTS.items():
        s = _metric(d, key)
        if s is None or not (s > 0).any():
            continue
        parts.append(s.rank(pct=True, method="average") * w)
        weights.append(w)
    if not parts:
        return pd.Series(0.0, index=d.index)
    return (sum(parts) / sum(weights) * 100).round(1)


def crawl_age_days(d: pd.DataFrame) -> pd.Series:
    """Tuổi bài lúc cào (ngày) = thời điểm cào − thời điểm đăng."""
    if "created_at" not in d.columns:
        return pd.Series(np.nan, index=d.index)
    created = pd.to_datetime(d["created_at"], errors="coerce")
    if "last_modify_ts" in d.columns:
        crawled = pd.to_datetime(pd.to_numeric(d["last_modify_ts"], errors="coerce"),
                                 unit="ms", errors="coerce")
    else:
        crawled = pd.Series(pd.Timestamp.utcnow().tz_localize(None), index=d.index)
    if getattr(created.dt, "tz", None) is not None:
        created = created.dt.tz_convert(None)
    age = (crawled - created).dt.total_seconds() / 86400
    return age.clip(lower=0).round(0)


def content_goal(d: pd.DataFrame) -> pd.Series:
    """
    Mục tiêu nội dung của từng bài: Lưu / Bàn luận / Lan truyền / Cân bằng.

    So tỷ lệ (chỉ số / like) của bài với trung vị CỦA CHÍNH BỘ DỮ LIỆU — vì mức
    tuyệt đối khác xa giữa nền tảng (lưu/like XHS 0,74 so với Douyin 0,16).
    """
    like = _metric(d, "like")
    out = pd.Series("can_bang", index=d.index)
    if like is None:
        return out
    base = like.where(like > 0)
    rel = {}
    for key, goal in (("save", "luu"), ("comment", "ban_luan"), ("share", "lan_truyen")):
        s = _metric(d, key)
        if s is None:
            continue
        ratio = s / base
        med = ratio.median()
        if med and med > 0:
            rel[goal] = ratio / med
    if not rel:
        return out
    r = pd.DataFrame(rel).fillna(0)
    best = r.idxmax(axis=1)
    strong = r.max(axis=1) >= GOAL_LIFT
    return best.where(strong, "can_bang").fillna("can_bang")


def add_post_insights(d: pd.DataFrame) -> pd.DataFrame:
    """Thêm `trend_score` (thứ hạng %), `age_days`, `goal`, `goal_label`."""
    d = d.copy()
    d["trend_score"] = percentile_trend_score(d)
    d["age_days"] = crawl_age_days(d)
    d["goal"] = content_goal(d)
    d["goal_label"] = d["goal"].map(GOALS)
    return d


def _median(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    return float(s.median()) if len(s) else float("nan")


def _ratio_median(d: pd.DataFrame, key: str) -> float | None:
    like, s = _metric(d, "like"), _metric(d, key)
    if like is None or s is None:
        return None
    r = (s / like.where(like > 0)).dropna()
    return round(float(r.median()), 3) if len(r) else None


def age_profile(d: pd.DataFrame) -> dict[str, Any]:
    """Số bài + like trung vị theo nhóm tuổi, và nhãn Evergreen / Flash."""
    age = pd.to_numeric(d.get("age_days"), errors="coerce")
    like = _metric(d, "like")
    buckets = []
    for lo, hi, label in AGE_BUCKETS:
        m = (age >= lo) & (age < hi)
        buckets.append({"label": label, "posts": int(m.sum()),
                        "like_median": _median(like[m]) if like is not None and m.any() else None})
    valid = age.notna().sum()
    if not valid:
        return {"buckets": buckets, "label": "", "median": None, "old_share": None,
                "new_share": None}
    old = float((age >= 90).sum() / valid)
    new = float((age < 30).sum() / valid)
    if new >= FLASH_NEW_SHARE:
        label = "Flash"
    elif old >= EVERGREEN_OLD_SHARE:
        label = "Evergreen"
    elif old >= LEAN_EVERGREEN_SHARE:
        label = "Nghiêng evergreen"
    else:
        label = "Hỗn hợp"
    return {"buckets": buckets, "label": label, "median": _median(age),
            "old_share": round(old, 3), "new_share": round(new, 3)}


def hashtag_stats(d: pd.DataFrame) -> list[dict[str, Any]]:
    """Tag có >= MIN_TAG_POSTS bài: số bài, like trung vị, mức so với cả bộ."""
    like = _metric(d, "like")
    if like is None or d.empty:
        return []
    tags = split_hashtags(d).map(lambda ts: {str(t).strip().lower() for t in ts if str(t).strip()})
    overall = _median(like)
    rows = []
    for tag in {t for ts in tags for t in ts} - SYSTEM_TAGS:
        if not re.search(r"\w", tag):          # bỏ tag rác kiểu "】" (Weibo viết #tag#)
            continue
        m = tags.map(lambda ts, t=tag: t in ts)
        n = int(m.sum())
        if n < MIN_TAG_POSTS:
            continue
        med = _median(like[m])
        lift = med / overall if overall and overall > 0 else float("nan")
        rows.append({"tag": tag, "posts": n, "like_median": med,
                     "lift": round(lift, 2) if not math.isnan(lift) else None})
    rows.sort(key=lambda r: (-r["posts"], -(r["lift"] or 0)))
    return rows


def tag_pairs(d: pd.DataFrame, min_posts: int = MIN_TAG_POSTS, top: int | None = None
              ) -> list[dict[str, Any]]:
    """Cặp hashtag hay xuất hiện cùng bài: số bài chung, like trung vị, so với cả bộ."""
    like = _metric(d, "like")
    if like is None or d.empty:
        return []
    tags = split_hashtags(d).map(
        lambda ts: sorted({str(t).strip().lower() for t in ts if str(t).strip()
                           and re.search(r"\w", str(t))} - SYSTEM_TAGS))
    overall = _median(like)
    bucket: dict[tuple[str, str], list[float]] = {}
    for ts, lk in zip(tags, like, strict=True):
        for i in range(len(ts)):
            for j in range(i + 1, len(ts)):
                bucket.setdefault((ts[i], ts[j]), []).append(float(lk))
    rows = []
    for (a, b), likes in bucket.items():
        if len(likes) < min_posts:
            continue
        med = float(pd.Series(likes).median())
        rows.append({"tag_a": a, "tag_b": b, "posts": len(likes), "like_median": med,
                     "lift": round(med / overall, 2) if overall else None})
    rows.sort(key=lambda r: (-r["posts"], -(r["lift"] or 0)))
    return rows if top is None else rows[:top]


def concentration(d: pd.DataFrame) -> dict[str, Any]:
    """Phần like của top 3 creator và HHI; kèm nhãn và cảnh báo mẫu nhỏ."""
    like = _metric(d, "like")
    if like is None or "creator_hash" not in d.columns or like.sum() <= 0:
        return {}
    if d["creator_hash"].nunique() < 3:      # dữ liệu 1 kênh: mức tập trung vô nghĩa
        return {}
    by = like.groupby(d["creator_hash"]).sum().sort_values(ascending=False)
    share = by / by.sum()
    hhi = float((share ** 2).sum() * 10000)
    label = ("Phân tán" if hhi < HHI_SPREAD else
             "Vừa" if hhi <= HHI_CONCENTRATED else "Tập trung")
    return {"creators": int(len(by)), "top3_share": round(float(share.head(3).sum()), 3),
            "hhi": round(hhi), "label": label,
            "small_sample": len(d) < MIN_POSTS_FOR_CONCENTRATION}


def _fmt_int(v: float | None) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:,.0f}".replace(",", ".")


def _fmt_ratio(v: float | None, digits: int = 2) -> str:
    return "—" if v is None else f"{v:.{digits}f}".replace(".", ",")


def trend_summary(d: pd.DataFrame, platform: str = "") -> dict[str, Any]:
    """
    Tổng hợp mọi con số cho tầng "Kết luận" + "Bằng chứng" của Trend Radar.

    Trả dict thuần (JSON được) — cũng là dữ liệu đưa cho LLM ở tính năng sau.
    `d` phải đã qua `add_post_insights`.
    """
    like = _metric(d, "like")
    goal_counts = d["goal"].value_counts().to_dict() if "goal" in d.columns else {}
    goal_like = ({g: _median(like[d["goal"] == g]) for g in goal_counts}
                 if like is not None else {})
    save_ratio = _ratio_median(d, "save")
    lo, hi = SAVE_LEVELS.get(platform, DEFAULT_SAVE_LEVEL)
    save_level = (None if save_ratio is None else
                  "Cao" if save_ratio >= hi else "Thấp" if save_ratio < lo else "Trung bình")
    ages = age_profile(d)
    tags = hashtag_stats(d)
    conc = concentration(d)

    summary: dict[str, Any] = {
        "posts": int(len(d)),
        "creators": int(d["creator_hash"].nunique()) if "creator_hash" in d.columns else None,
        "keywords": sorted({str(k) for k in d.get("source_keyword", pd.Series(dtype=str)).dropna()
                            if str(k).strip()}),
        "platform": platform,
        "like_median": _median(like) if like is not None else None,
        "like_p90": float(like.quantile(0.9)) if like is not None and len(like) else None,
        "ratios": {"save": save_ratio, "comment": _ratio_median(d, "comment"),
                   "share": _ratio_median(d, "share")},
        "save_level": save_level,
        "save_level_band": [lo, hi],
        "goals": {g: {"label": GOALS.get(g, g), "posts": int(n),
                      "like_median": goal_like.get(g)} for g, n in goal_counts.items()},
        "age": ages,
        "hashtags": tags,
        "concentration": conc,
        # Dữ liệu quét kênh: không có từ khoá nguồn và < 3 creator. Khi đó "tuổi bài"
        # là toàn bộ kho video cũ của kênh, không phải bài trụ trong kết quả tìm kiếm.
        "mode": ("channel" if not any(str(k).strip() for k in
                                      d.get("source_keyword", pd.Series(dtype=str)).dropna())
                 and d.get("creator_hash", pd.Series(dtype=str)).nunique() < 3 else "search"),
    }
    summary["verdict"], summary["decisions"] = _verdict(summary)
    return summary


def _verdict(s: dict[str, Any]) -> tuple[str, list[str]]:
    """Câu kết luận + tối đa 3 việc nên làm, suy từ các ngưỡng ở đầu file."""
    bits, decisions = [], []
    goals = s.get("goals") or {}
    real = {g: v for g, v in goals.items() if g != "can_bang"}
    ratios = s.get("ratios") or {}

    if s.get("save_level") == "Cao":
        bits.append("người xem lưu nhiều (nội dung để học lại)")
        decisions.append(
            f"Làm nội dung hướng dẫn có quy trình: {_fmt_ratio(ratios.get('save'))} lượt lưu "
            f"mỗi like, mức cao với nền tảng này.")
    elif real:
        top = max(real.items(), key=lambda kv: kv[1]["posts"])
        g, v = top
        hint = {"ban_luan": "đặt câu hỏi, nêu quan điểm để kéo bình luận",
                "lan_truyen": "làm nội dung đáng gửi cho người khác",
                "luu": "làm nội dung đáng lưu lại"}.get(g, "")
        bits.append(f"nhóm “{v['label']}” chiếm nhiều bài nhất")
        if hint:
            decisions.append(f"{hint.capitalize()}: {v['posts']} bài thuộc nhóm {v['label']}.")

    age = s.get("age") or {}
    label = age.get("label") if s.get("mode") != "channel" else None
    if label in ("Evergreen", "Nghiêng evergreen"):
        bits.append("chủ đề sống lâu")
        old = sum(b["posts"] for b in age.get("buckets", []) if b["label"] not in ("< 30 ngày", "30–90 ngày"))
        decisions.append(f"Đầu tư bài dùng lâu: {old}/{s['posts']} bài đã hơn 90 ngày tuổi "
                         f"vẫn nằm trong kết quả.")
    elif label == "Flash":
        bits.append("chủ đề đang bùng, bài mới chiếm ưu thế")
        decisions.append(f"Làm nhanh, bám trend: {_pct(age.get('new_share'))} số bài dưới 30 ngày tuổi.")

    tags = [t for t in (s.get("hashtags") or []) if t.get("lift")]
    if tags and s.get("posts"):
        small = [t for t in tags if MIN_TAG_POSTS_TO_RECOMMEND <= t["posts"] <= max(
            MIN_TAG_POSTS_TO_RECOMMEND, s["posts"] * 0.25) and t["lift"] >= 1.5]
        if small:
            t = max(small, key=lambda x: x["lift"])
            decisions.append(f"Thử tag #{t['tag']}: mới {t['posts']} bài, like trung vị "
                             f"{_fmt_int(t['like_median'])} (gấp {_fmt_ratio(t['lift'], 1)} lần cả bộ).")

    conc = s.get("concentration") or {}
    if conc:
        word = {"Phân tán": "cạnh tranh phân tán, dễ vào", "Vừa": "cạnh tranh ở mức vừa",
                "Tập trung": "vài creator thống trị"}[conc["label"]]
        bits.append(word)
        if conc["label"] == "Tập trung":
            decisions.append(f"Cần góc khác biệt hoặc hợp tác: top 3 creator chiếm "
                             f"{_pct(conc['top3_share'])} lượng like.")

    kw = ", ".join(s.get("keywords") or []) or (
        "kênh này" if s.get("mode") == "channel" else "bộ dữ liệu này")
    verdict = (f"{kw}: " + ", ".join(bits) + ".") if bits else f"{kw}: chưa đủ tín hiệu rõ ràng."
    return verdict[0].upper() + verdict[1:], decisions[:3]


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.0f}%"
