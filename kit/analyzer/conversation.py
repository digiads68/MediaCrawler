# -*- coding: utf-8 -*-
"""
Conversation Pulse — đọc nhịp thảo luận từ file BÌNH LUẬN (bổ sung cho Voice of Customer).

Trả lời: bài nào kéo thảo luận, bình luận đến nhanh hay chậm, bao nhiêu là câu hỏi,
và quan trọng nhất — mẫu bình luận đã cào phủ được bao nhiêu phần số bình luận thật.
Crawler mặc định chỉ lấy ~10 bình luận nổi bật mỗi bài (đo thật: ~3% số thật), nên
mọi con số ở đây là MẪU; report phải nói rõ điều đó ngay đầu trang.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from kit.analyzer.insights import _metric

QUESTION_RE = re.compile(r"[?？]|吗|怎么|为什么|多少|哪里|哪个|如何|能不能|可以吗|求|有没有")
LOW_COVERAGE = 0.20        # phủ < 20% số bình luận thật -> cảnh báo mẫu nhỏ


def sibling_contents_file(comments_path: str | Path) -> Path | None:
    """File bài cùng phiên: `search_comments_X.json` -> `search_contents_X.json`."""
    p = Path(comments_path)
    if "_comments_" not in p.name:
        return None
    cand = p.with_name(p.name.replace("_comments_", "_contents_"))
    return cand if cand.exists() else None


def _is_root(d: pd.DataFrame) -> pd.Series:
    if "parent_comment_id" not in d.columns:
        return pd.Series(True, index=d.index)
    parent = d["parent_comment_id"].astype(str)
    # dy/bili/xhs ghi "0" cho bình luận gốc; Weibo ghi chính id của nó (đo thật 100%).
    root = parent.isin(["0", "", "nan", "None"])
    if "comment_id" in d.columns:
        root |= parent == d["comment_id"].astype(str)
    if "post_id" in d.columns:
        root |= parent == d["post_id"].astype(str)
    return root


def conversation_pulse(comments: pd.DataFrame, posts: pd.DataFrame | None = None) -> dict[str, Any]:
    """
    Tổng hợp nhịp thảo luận. `comments`, `posts` là DataFrame đã `load()`.

    Không có `posts` thì bỏ phần độ phủ và thời gian đến (chỉ tính trên bình luận).
    """
    c = comments.copy()
    if c.empty or "content" not in c.columns:
        return {}
    text = c["content"].fillna("").astype(str)
    like = _metric(c, "like")
    c["_like"] = like if like is not None else 0
    c["_q"] = text.str.contains(QUESTION_RE)
    root = _is_root(c)
    subs = pd.to_numeric(c.get("sub_comment_count"), errors="coerce").fillna(0)
    pics = c["pictures"].fillna("").astype(str).str.strip().ne("") if "pictures" in c.columns else None

    per_post = c.groupby("post_id").agg(crawled=("content", "size"),
                                        questions=("_q", "sum"),
                                        comment_likes=("_like", "sum"))
    out: dict[str, Any] = {
        "comments": int(len(c)),
        "posts": int(c["post_id"].nunique()),
        "per_post_median": float(per_post["crawled"].median()),
        "question_share": round(float(c["_q"].mean()), 3),
        "picture_share": round(float(pics.mean()), 3) if pics is not None else None,
        "root_with_replies": round(float((subs[root] > 0).mean()), 3) if root.any() else None,
        "replies_crawled": int((~root).sum()),
        "coverage": None, "coverage_median": None, "lag_hours": None, "low_coverage": None,
    }

    if posts is not None and not posts.empty and "post_id" in posts.columns:
        p = posts.drop_duplicates("post_id").set_index("post_id")
        real = _metric(posts.drop_duplicates("post_id"), "comment")
        if real is not None:
            p["_real"] = real.values
            joined = per_post.join(p[["_real"]], how="left")
            ok = joined["_real"] > 0
            if ok.any():
                out["coverage"] = round(float(joined.loc[ok, "crawled"].sum()
                                              / joined.loc[ok, "_real"].sum()), 3)
                out["coverage_median"] = round(float((joined.loc[ok, "crawled"]
                                                      / joined.loc[ok, "_real"]).median()), 3)
                out["low_coverage"] = out["coverage"] < LOW_COVERAGE
            per_post = joined
        if "created_at" in p.columns and "created_at" in c.columns:
            post_t = c["post_id"].map(pd.to_datetime(p["created_at"], errors="coerce"))
            lag = (pd.to_datetime(c["created_at"], errors="coerce") - post_t).dt.total_seconds() / 3600
            lag = lag[lag >= 0]
            if len(lag):
                out["lag_hours"] = {k: round(float(lag.quantile(q)), 1)
                                    for k, q in (("p25", .25), ("p50", .5), ("p75", .75), ("p90", .9))}
        title_col = next((col for col in ("title", "title_text", "content", "desc") if col in p.columns), None)
        if title_col:
            per_post["title"] = p[title_col].reindex(per_post.index).fillna("").astype(str).str.slice(0, 80)
        for col in ("aweme_url", "note_url", "video_url"):
            if col in p.columns:
                per_post["url"] = p[col].reindex(per_post.index)
                break

    per_post["question_share"] = (per_post["questions"] / per_post["crawled"]).round(3)
    out["top_posts"] = per_post.sort_values("comment_likes", ascending=False).reset_index()
    qs = c[c["_q"]].sort_values("_like", ascending=False)
    out["questions"] = qs[[col for col in ("content", "_like", "post_id") if col in qs.columns]] \
        .rename(columns={"_like": "like_count"}).reset_index(drop=True)
    out["verdict"], out["decisions"] = _verdict(out)
    return out


def _pct(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.1f}%".replace(".", ",") if v < 0.01 else f"{v * 100:.0f}%"


def _n(v: int) -> str:
    return f"{v:,}".replace(",", ".")


def _verdict(o: dict[str, Any]) -> tuple[str, list[str]]:
    dec = []
    cov = o.get("coverage")
    if cov is not None and o.get("low_coverage"):
        verdict = (f"Đây mới là mẫu nhỏ: đã cào {_n(o['comments'])} bình luận, khoảng {_pct(cov)} số "
                   f"bình luận thật của {_n(o['posts'])} bài.")
        dec.append("Tăng số bình luận mỗi bài (MAX_COMMENTS 50–100) khi cần phân tích sâu một bài.")
    elif cov is not None:
        verdict = f"Mẫu bình luận phủ {_pct(cov)} số bình luận thật — đủ để đọc xu hướng."
    else:
        verdict = (f"{_n(o['comments'])} bình luận trên {_n(o['posts'])} bài. Chưa có file bài cùng "
                   f"phiên nên chưa tính được độ phủ.")
    if o.get("root_with_replies") and o["root_with_replies"] >= 0.3 and o.get("replies_crawled") == 0:
        dec.append(f"Bật Sub-comments: {_pct(o['root_with_replies'])} bình luận gốc có trả lời "
                   f"nhưng chưa cào phần trả lời.")
    if o.get("question_share") and o["question_share"] >= 0.1:
        dec.append(f"Dùng {_pct(o['question_share'])} bình luận dạng câu hỏi làm ý tưởng video "
                   f"tiếp theo (bảng Câu hỏi bên dưới).")
    return verdict, dec[:3]
