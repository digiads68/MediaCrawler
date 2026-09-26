# -*- coding: utf-8 -*-
"""
Creator Audit — soi sâu từng kênh từ dữ liệu Creator Mode (luật cố định, không gọi AI).

Bổ sung cho `koc_scorecard` (bảng điểm nhiều creator): hàm này trả phần "đọc
kênh" — nhịp đăng, quỹ đạo theo quý, tỷ lệ hit, trụ nội dung, lịch đăng — cho
từng creator đủ video. Mọi ngưỡng ở đầu file.

Số liệu mẫu khi thiết kế (file 246 video, kênh phim tài liệu động vật, 09/2026):
trung vị like 25.026 (video >= 30 ngày), hit 26%, 10% video top = 59% like,
Q2/2026 đăng 42 video nhưng like trung vị không tăng, #虎鲸 x2,45, #非洲 x0,44.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from kit.analyzer.insights import (
    GOALS,
    SYSTEM_TAGS,
    _metric,
    add_post_insights,
)
from kit.enrich.schema import split_hashtags

MIN_VIDEOS = 5                 # cùng ngưỡng với koc_scorecard
MATURE_DAYS = 30               # like cộng dồn: video non tuổi bị loại khi so hiệu suất
HIT_MULT = 2.0                 # hit = like >= 2 lần trung vị kênh
MEGA_MULT = 10.0
HIT_BUCKETS = [(0, 0.5, "< 0,5 lần"), (0.5, 1, "0,5–1 lần"), (1, 2, "1–2 lần"),
               (2, 10, "2–10 lần"), (10, math.inf, "≥ 10 lần")]
TOP_SHARE_DEPENDENT = 0.50     # 10% video top chiếm >= 50% like -> phụ thuộc hit
PILLAR_MIN_VIDEOS = 6
PILLAR_FEW_VIDEOS = 10         # dưới mức này gắn nhãn "ít video"
PILLAR_MAX_SHARE = 0.80        # tag có ở > 80% video = tag chung, không phải trụ
PILLAR_UP, PILLAR_DOWN = 1.2, 0.8
FIXED_SCHEDULE_SHARE = 0.80    # >= 80% video đăng cùng 1 giờ -> lịch cố định
VOLUME_UP = 1.5                # quý đăng >= 1,5 lần trung bình các quý trước
QUALITY_FLAT = 1.10            # like trung vị tăng < 10% -> coi như không tăng
DOW = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật"]
TZ = "Asia/Shanghai"           # giờ đăng hiển thị theo giờ Trung Quốc (UTC+8)


def _med(s: pd.Series) -> float | None:
    s = pd.to_numeric(s, errors="coerce").dropna()
    return float(s.median()) if len(s) else None


def _local(created: pd.Series) -> pd.Series:
    t = pd.to_datetime(created, errors="coerce")
    if getattr(t.dt, "tz", None) is None:
        t = t.dt.tz_localize("UTC")
    return t.dt.tz_convert(TZ)


def _quarters(g: pd.DataFrame, like: pd.Series) -> list[dict[str, Any]]:
    t = _local(g["created_at"])
    q = t.dt.tz_localize(None).dt.to_period("Q").astype(str)
    out = []
    for label in sorted(q.dropna().unique()):
        m = q == label
        mature = m & (g["age_days"] >= MATURE_DAYS)
        ages = g.loc[m, "age_days"]
        young = bool((ages < MATURE_DAYS).mean() > 0.5) if len(ages) else False
        out.append({"quarter": label.replace("Q", " Q"), "videos": int(m.sum()),
                    "like_median": _med(like[mature]) if mature.any() else _med(like[m]),
                    "age_median": _med(ages), "young": young})
    return out


def _pillars(g: pd.DataFrame, like: pd.Series, base: float) -> list[dict[str, Any]]:
    tags = split_hashtags(g).map(lambda ts: {str(t).strip().lower() for t in ts if str(t).strip()})
    mature = g["age_days"] >= MATURE_DAYS
    n = len(g)
    rows = []
    for tag in {t for ts in tags for t in ts} - SYSTEM_TAGS:
        has = tags.map(lambda ts, t=tag: t in ts)
        cnt = int(has.sum())
        if cnt < PILLAR_MIN_VIDEOS or cnt / n > PILLAR_MAX_SHARE:
            continue
        sel = has & mature if (has & mature).sum() >= 3 else has
        med = _med(like[sel]) or 0
        lift = med / base if base else 0
        hit = float((like[sel] >= HIT_MULT * base).mean()) if base else 0
        rec = "Làm thêm" if lift >= PILLAR_UP else "Giảm" if lift < PILLAR_DOWN else "Giữ"
        rows.append({"tag": tag, "videos": cnt, "like_median": med, "lift": round(lift, 2),
                     "hit_rate": round(hit, 2), "recommend": rec,
                     "few": cnt < PILLAR_FEW_VIDEOS})
    rows.sort(key=lambda r: -r["lift"])
    return rows


def _schedule(g: pd.DataFrame, like: pd.Series) -> dict[str, Any]:
    t = _local(g["created_at"])
    hours = t.dt.hour.value_counts()
    top_hour = int(hours.idxmax()) if len(hours) else None
    top_share = float(hours.max() / hours.sum()) if len(hours) else 0
    mature = g["age_days"] >= MATURE_DAYS
    dow = []
    for i, name in enumerate(DOW):
        m = t.dt.dayofweek == i
        dow.append({"day": name, "videos": int(m.sum()),
                    "like_median": _med(like[m & mature]) if (m & mature).any() else _med(like[m])})
    gaps = t.sort_values().diff().dt.total_seconds().dropna() / 86400
    return {"top_hour": top_hour, "top_hour_share": round(top_share, 3),
            "fixed": top_share >= FIXED_SCHEDULE_SHARE, "dow": dow,
            "gap_median_days": round(float(gaps.median()), 1) if len(gaps) else None,
            "gap_max_days": round(float(gaps.max()), 1) if len(gaps) else None}


def channel_audit(g: pd.DataFrame) -> dict[str, Any]:
    """Audit 1 kênh. `g` đã qua `add_post_insights` (có age_days, goal)."""
    like = _metric(g, "like")
    if like is None or g.empty:
        return {}
    mature = g["age_days"] >= MATURE_DAYS
    base = _med(like[mature]) if mature.sum() >= 5 else _med(like)
    base = base or 0.0
    mult = like / base if base else like * 0
    total = like.sum()
    k = max(1, round(len(g) * 0.1))
    buckets = [{"label": lab, "videos": int(((mult >= lo) & (mult < hi)).sum())}
               for lo, hi, lab in HIT_BUCKETS]
    t = _local(g["created_at"])
    audit = {
        "creator": str(g["creator_hash"].iloc[0]) if "creator_hash" in g.columns else "",
        "nickname": str(g["nickname"].iloc[0]) if "nickname" in g.columns else "",
        "videos": int(len(g)),
        "first": str(t.min().date()) if t.notna().any() else "",
        "last": str(t.max().date()) if t.notna().any() else "",
        "like_median": base,
        "like_p90": float(like.quantile(0.9)),
        "hit_rate": round(float((mult >= HIT_MULT).mean()), 3) if base else None,
        "mega_hits": int((mult >= MEGA_MULT).sum()) if base else 0,
        "top10_share": round(float(like.nlargest(k).sum() / total), 3) if total else None,
        "buckets": buckets,
        "quarters": _quarters(g, like),
        "pillars": _pillars(g, like, base),
        "schedule": _schedule(g, like),
        "goals": {gk: int(n) for gk, n in g["goal"].value_counts().items()} if "goal" in g else {},
        "last90_videos": int((g["age_days"] < 90).sum()),
    }
    audit["verdict"], audit["decisions"] = _verdict(audit)
    return audit


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:,.0f}".replace(",", ".")


def _ratio(v: float | None, d: int = 2) -> str:
    return "—" if v is None else f"{v:.{d}f}".replace(".", ",")


def _verdict(a: dict[str, Any]) -> tuple[str, list[str]]:
    bits, dec = [], []
    top = a.get("top10_share")
    if top is not None and top >= TOP_SHARE_DEPENDENT:
        bits.append("sống nhờ một số ít video bùng nổ")
    elif top is not None:
        bits.append("hiệu suất khá đều giữa các video")

    quarters = [q for q in a.get("quarters", []) if not q["young"] and q["like_median"]]
    # Xét 2 quý gần nhất: đợt đăng dày có thể ở quý áp chót, quý cuối đã giảm lại.
    for idx in (len(quarters) - 1, len(quarters) - 2):
        if idx < 2:
            break
        last, prev = quarters[idx], quarters[:idx]
        avg_prev = sum(q["videos"] for q in prev) / len(prev)
        prev_like = pd.Series([q["like_median"] for q in prev]).median()
        if not (avg_prev and last["videos"] >= VOLUME_UP * avg_prev and prev_like
                and last["like_median"] < QUALITY_FLAT * prev_like):
            continue
        bits.append("đăng dày hơn chưa làm mỗi video ăn hơn")
        dec.append(f"Ưu tiên chất lượng hơn số lượng: {last['quarter']} đăng {last['videos']} video "
                   f"(gấp {_ratio(last['videos'] / avg_prev, 1)} lần trung bình), like trung vị "
                   f"{_fmt(last['like_median'])} không cao hơn trước ({_fmt(prev_like)}).")
        break

    pillars = a.get("pillars") or []
    good = [p for p in pillars if p["recommend"] == "Làm thêm"]
    bad = [p for p in pillars if p["recommend"] == "Giảm"]
    if good:
        p = good[0]
        dec.insert(0, f"Làm thêm chủ đề #{p['tag']}: gấp {_ratio(p['lift'])} lần trung vị kênh, "
                      f"{p['hit_rate'] * 100:.0f}% video thành hit ({p['videos']} video).")
    if bad:
        worst = sorted(bad, key=lambda p: p["lift"])[:2]
        tags = ", ".join(f"#{p['tag']} ({_ratio(p['lift'])} lần)" for p in worst)
        dec.append(f"Giảm chủ đề kém: {tags} trung vị kênh.")
    sched = a.get("schedule") or {}
    if sched.get("fixed") and sched.get("top_hour") is not None:
        bits.append(f"đăng cố định lúc {sched['top_hour']}:00")
    verdict = "Kênh này: " + ", ".join(bits) + "." if bits else "Kênh này: chưa đủ tín hiệu rõ ràng."
    return verdict, dec[:3]


def creator_audit(df: pd.DataFrame, min_videos: int = MIN_VIDEOS) -> dict[str, Any]:
    """
    Audit mọi creator có >= `min_videos` video.

    Trả {"mode": "single"|"multi", "channels": [audit...] (xếp theo số video),
         "posts": DataFrame đã add_post_insights (cho lưới thẻ)}.
    """
    d = add_post_insights(df)
    key = "creator_hash" if "creator_hash" in d.columns else "nickname"
    channels = []
    for _, g in d.groupby(key):
        if len(g) >= min_videos:
            a = channel_audit(g)
            if a:
                channels.append(a)
    channels.sort(key=lambda a: -a["videos"])
    return {"mode": "single" if len(channels) == 1 else "multi", "channels": channels,
            "posts": d.sort_values("trend_score", ascending=False), "goal_labels": GOALS}
