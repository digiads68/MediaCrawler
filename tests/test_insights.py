# -*- coding: utf-8 -*-
"""Kết luận & bằng chứng Trend Radar + các lỗi dữ liệu đi kèm (synthetic, không gọi mạng)."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from kit.analyzer import insights as ins
from kit.analyzer import mediacrawler_analyzer as an
from kit.enrich.schema import dedupe_posts

DAY_MS = 86_400_000
CRAWL_MS = 1_790_000_000_000


def _posts(n: int = 12, *, creators: int | None = None, keyword: str = "#aigc",
           ages: list[int] | None = None) -> pd.DataFrame:
    ages = ages or [10 + i * 20 for i in range(n)]
    rows = []
    for i in range(n):
        like = 1000 + i * 100
        rows.append({
            "aweme_id": str(i), "title": f"bài {i} #aigc #tag{i % 3}",
            "desc": f"bài {i} #aigc #tag{i % 3}",
            "liked_count": like, "collected_count": like // 5, "comment_count": like // 50,
            "share_count": like // 20,
            "create_time": (CRAWL_MS - ages[i] * DAY_MS) // 1000, "last_modify_ts": CRAWL_MS,
            "creator_hash": f"c{i % (creators or n)}", "source_keyword": keyword,
        })
    return pd.DataFrame(rows)


def _load(df: pd.DataFrame, tmp_path, name: str = "search_contents.json") -> pd.DataFrame:
    p = tmp_path / "douyin" / "json" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(df.to_json(orient="records", force_ascii=False), encoding="utf-8")
    return an.load(p)


def test_json_file_keeps_time_axis(tmp_path):
    """Lỗi cũ: read_json tự đổi create_time -> datetime rồi normalize ra NaT."""
    d = _load(_posts(), tmp_path)
    assert d["created_at"].notna().all()
    assert d["week"].notna().all()


def test_percentile_score_not_crushed_by_viral_post(tmp_path):
    """Công thức cũ chia cho max: 1 bài 1000 lần to hơn ép mọi bài khác về ~0."""
    df = _posts()
    for c in ("liked_count", "collected_count", "comment_count", "share_count"):
        df.loc[0, c] = df[c].max() * 1000
    d = ins.add_post_insights(_load(df, tmp_path))
    others = d.loc[d["aweme_id"].astype(str) != "0", "trend_score"]
    assert others.max() > 80          # bài đứng thứ 2 vẫn điểm cao
    assert others.min() < others.max()


def test_trend_radar_keeps_every_post(tmp_path):
    res = an.trend_radar(_load(_posts(60), tmp_path))
    assert len(res["top_posts"]) == 60
    assert {"age_days", "goal", "goal_label"} <= set(res["top_posts"].columns)


def test_content_goal_flags_share_heavy_post(tmp_path):
    df = _posts()
    df.loc[3, "share_count"] = df.loc[3, "liked_count"] * 3
    d = ins.add_post_insights(_load(df, tmp_path))
    assert d.loc[d["aweme_id"].astype(str) == "3", "goal"].iloc[0] == "lan_truyen"
    assert d["goal"].isin(ins.GOALS).all()


@pytest.mark.parametrize("ages,label", [
    ([200] * 8 + [10] * 4, "Evergreen"),
    ([5] * 8 + [200] * 4, "Flash"),
    ([120] * 5 + [40] * 7, "Nghiêng evergreen"),
])
def test_age_profile_label(tmp_path, ages, label):
    d = ins.add_post_insights(_load(_posts(12, ages=ages), tmp_path))
    assert ins.age_profile(d)["label"] == label


def test_hashtag_stats_drop_junk_and_system_tags(tmp_path):
    df = _posts()
    df.loc[0:3, ["title", "desc"]] = "x #】 #内容启发搜索 #thật"
    stats = {t["tag"] for t in ins.hashtag_stats(ins.add_post_insights(_load(df, tmp_path)))}
    assert "】" not in stats and "内容启发搜索" not in stats
    assert "thật" in stats


def test_tag_recommendation_needs_three_posts(tmp_path):
    """2 bài + 1 viral từng cho ra 'gấp 20 lần' — không được thành khuyến nghị."""
    df = _posts(20)
    df.loc[0:1, ["title", "desc"]] = "#hiem"
    df.loc[0, "liked_count"] = 10_000_000
    s = an.trend_radar(_load(df, tmp_path))["summary"]
    assert not any("#hiem" in x for x in s["decisions"])


def test_single_channel_skips_concentration_and_age_verdict(tmp_path):
    s = an.trend_radar(_load(_posts(12, creators=1, keyword="", ages=[400] * 12), tmp_path))["summary"]
    assert s["mode"] == "channel"
    assert s["concentration"] == {}
    assert not any("90 ngày" in x for x in s["decisions"])
    assert s["verdict"].startswith("Kênh này")


def test_concentration_label(tmp_path):
    s = an.trend_radar(_load(_posts(12, creators=12), tmp_path))["summary"]
    assert s["concentration"]["label"] in {"Phân tán", "Vừa", "Tập trung"}
    assert s["concentration"]["small_sample"] is True


def test_summary_is_json_serialisable(tmp_path):
    s = an.trend_radar(_load(_posts(), tmp_path))["summary"]
    json.dumps(s, ensure_ascii=False, default=str)
    assert s["verdict"] and isinstance(s["decisions"], list)


def test_dedupe_comments_by_comment_id():
    """Lỗi cũ: file bình luận bỏ trùng theo id BÀI -> mất 90% bình luận."""
    df = pd.DataFrame({"platform": "dy", "post_id": ["1", "1", "1", "2"],
                       "comment_id": ["a", "b", "b", "c"]})
    out = dedupe_posts(df, verbose=False)
    assert list(out["comment_id"]) == ["a", "b", "c"]
