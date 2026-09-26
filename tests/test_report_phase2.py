# -*- coding: utf-8 -*-
"""Report đợt 2: Creator Audit, Conversation Pulse, hashtag, Opportunity (synthetic, không gọi mạng)."""

from __future__ import annotations

import json
import re

import pandas as pd

from kit.analyzer import mediacrawler_analyzer as an
from kit.analyzer.conversation import conversation_pulse, sibling_contents_file
from kit.analyzer.creator_audit import creator_audit
from kit.analyzer.insights import tag_pairs
from kit.report import html_report as hr

DAY = 86_400
CRAWL_S = 1_790_000_000


def _channel(n: int = 60, creator: str = "c1", *, tag_hot: str = "cavoi", tag_cold: str = "sahara",
             burst_quarter_posts: int = 0) -> list[dict]:
    """Kênh synthetic: video #tag_hot like gấp 3, #tag_cold like 0,3; đăng 8:00 giờ TQ."""
    rows = []
    for i in range(n):
        age = 40 + i * 9
        like = 10_000
        tags = "#chung"
        if i % 6 == 0:
            like, tags = 30_000, f"#chung #{tag_hot}"
        elif i % 6 == 1:
            like, tags = 3_000, f"#chung #{tag_cold}"
        ts = CRAWL_S - age * DAY
        ts -= ts % DAY - 0 * 3600          # 00:00 UTC = 8:00 Asia/Shanghai
        rows.append({"aweme_id": f"{creator}-{i}", "title": f"v{i} {tags}", "desc": f"v{i} {tags}",
                     "liked_count": like, "collected_count": like // 10, "comment_count": like // 100,
                     "share_count": like // 50, "create_time": ts, "last_modify_ts": CRAWL_S * 1000,
                     "creator_hash": creator, "nickname": f"kênh {creator}", "source_keyword": "",
                     "aweme_url": f"https://www.douyin.com/video/{creator}{i}"})
    for j in range(burst_quarter_posts):   # đợt đăng dày gần đây, like không tăng
        ts = CRAWL_S - (35 + j % 20) * DAY
        rows.append({**rows[2], "aweme_id": f"{creator}-b{j}", "create_time": ts - ts % DAY,
                     "title": f"burst {j}", "desc": f"burst {j} #chung"})
    return rows


def _load(rows: list[dict], tmp_path, name: str) -> pd.DataFrame:
    p = tmp_path / "douyin" / "json" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return an.load(p)


def test_single_channel_audit(tmp_path):
    res = creator_audit(_load(_channel(), tmp_path, "creator_contents_x.json"))
    assert res["mode"] == "single" and len(res["channels"]) == 1
    a = res["channels"][0]
    assert a["videos"] == 60 and a["like_median"] == 10_000
    assert a["schedule"]["top_hour"] == 8 and a["schedule"]["fixed"] is True
    pillars = {p["tag"]: p for p in a["pillars"]}
    assert pillars["cavoi"]["recommend"] == "Làm thêm" and pillars["cavoi"]["lift"] == 3.0
    assert pillars["sahara"]["recommend"] == "Giảm"
    assert "chung" not in pillars                       # tag có ở mọi video = tag chung
    assert sum(b["videos"] for b in a["buckets"]) == 60
    assert any("#cavoi" in d for d in a["decisions"])


def test_young_videos_excluded_from_baseline(tmp_path):
    rows = _channel()
    for i in range(10):                                   # 10 video mới, like thấp vì chưa đủ tuổi
        ts = CRAWL_S - 3 * DAY
        rows.append({**rows[2], "aweme_id": f"new{i}", "liked_count": 50, "create_time": ts})
    a = creator_audit(_load(rows, tmp_path, "creator_contents_y.json"))["channels"][0]
    assert a["like_median"] == 10_000


def test_multi_channel_mode(tmp_path):
    rows = _channel(20, "a") + _channel(12, "b") + _channel(3, "c")   # c < 5 video: bị loại
    res = creator_audit(_load(rows, tmp_path, "creator_contents_z.json"))
    assert res["mode"] == "multi"
    assert [c["creator"] for c in res["channels"]] == ["a", "b"]


def test_koc_report_single_and_multi(tmp_path, monkeypatch):
    monkeypatch.setattr(hr, "REPORT_DIR", tmp_path / "r")
    for rows, name in ((_channel(), "single"), (_channel(20, "a") + _channel(12, "b"), "multi")):
        df = _load(rows, tmp_path, f"creator_contents_{name}.json")
        data = {"scorecard": an.koc_scorecard(df), **creator_audit(df)}
        html = hr.build_report("koc", data, df=df, slug=name).read_text(encoding="utf-8")
        assert "Creator Audit" in html and 'class="qchart"' in html and 'id="commentary"' in html
        assert html.count('class="mcard"') == len(df)
        if name == "multi":
            assert 'id="ch-sel"' in html and html.count('class="ch-audit"') == 2


def test_koc_report_accepts_legacy_dataframe(tmp_path, monkeypatch):
    monkeypatch.setattr(hr, "REPORT_DIR", tmp_path)
    s = pd.DataFrame({"creator": ["x"], "nickname": ["n"], "so_video": [6], "eng_tb": [1.0],
                      "do_deu": [0.5], "velocity": [1.4], "nhip_dang_ngay": [2.0],
                      "diem_tong": [70.0], "verdict": ["ký ngay"], "rising": [True]})
    html = hr.build_report("koc", s).read_text(encoding="utf-8")
    assert "Bảng điểm KOC" in html


def _comments_and_posts(tmp_path, *, weibo_style: bool = False):
    posts = [{"aweme_id": str(i), "title": f"bài {i}", "comment_count": 200, "liked_count": 1000,
              "create_time": CRAWL_S - 10 * DAY, "last_modify_ts": CRAWL_S * 1000,
              "creator_hash": "c", "aweme_url": f"https://www.douyin.com/video/{i}"} for i in range(3)]
    comments = []
    for i in range(3):
        for j in range(10):
            cid = f"{i}{j}"
            comments.append({"comment_id": cid, "aweme_id": str(i),
                             "content": "cái này mua ở đâu vậy?" if j < 2 else f"hay quá {cid}",
                             "like_count": 10 - j, "sub_comment_count": 3 if j == 0 else 0,
                             "parent_comment_id": cid if weibo_style else "0",
                             "create_time": CRAWL_S - 10 * DAY + (j + 1) * 3600,
                             "last_modify_ts": CRAWL_S * 1000, "creator_hash": f"u{j}"})
    d = tmp_path / "douyin" / "json"
    d.mkdir(parents=True, exist_ok=True)
    (d / "search_contents_k.json").write_text(json.dumps(posts), encoding="utf-8")
    cp = d / "search_comments_k.json"
    cp.write_text(json.dumps(comments, ensure_ascii=False), encoding="utf-8")
    return cp


def test_conversation_pulse_coverage_and_lag(tmp_path):
    cp = _comments_and_posts(tmp_path)
    sib = sibling_contents_file(cp)
    assert sib is not None and sib.name == "search_contents_k.json"
    o = conversation_pulse(an.load(cp), an.load(sib))
    assert o["comments"] == 30 and o["posts"] == 3
    assert o["coverage"] == 0.05 and o["low_coverage"] is True
    assert o["lag_hours"]["p50"] == 5.5
    assert o["question_share"] == 0.2
    assert o["replies_crawled"] == 0 and o["root_with_replies"] == 0.1
    assert len(o["questions"]) == 6
    assert o["verdict"].startswith("Đây mới là mẫu nhỏ")


def test_weibo_root_comment_is_its_own_parent(tmp_path):
    cp = _comments_and_posts(tmp_path, weibo_style=True)
    o = conversation_pulse(an.load(cp), None)
    assert o["replies_crawled"] == 0          # parent == chính nó -> là bình luận gốc
    assert o["coverage"] is None              # không có file bài -> không tính độ phủ


def test_insight_report_renders_pulse(tmp_path, monkeypatch):
    monkeypatch.setattr(hr, "REPORT_DIR", tmp_path / "r")
    cp = _comments_and_posts(tmp_path)
    c = an.load(cp)
    data = {"bank": an.comment_bank(c), "pulse": conversation_pulse(c, an.load(sibling_contents_file(cp)))}
    html = hr.build_report("insight", data, df=c).read_text(encoding="utf-8")
    assert "verdict-warn" in html and "Độ phủ" in html and "Câu hỏi của khách" in html
    assert re.search(r"Bài kéo thảo luận", html)


def test_tag_pairs_and_sound_report(tmp_path, monkeypatch):
    df = _load(_channel(), tmp_path, "creator_contents_t.json")
    pairs = tag_pairs(df)
    assert {"tag_a", "tag_b", "posts"} <= set(pairs[0])
    assert any({p["tag_a"], p["tag_b"]} == {"cavoi", "chung"} for p in pairs)
    monkeypatch.setattr(hr, "REPORT_DIR", tmp_path / "r")
    res = an.sound_edit_kit(df)
    assert len(res["tag_stats"]) and len(res["tag_pairs"])
    assert (res["shelf"]["liked_count"] > 0).all()       # kệ tư liệu từng hiện 0 like
    html = hr.build_report("sound", res, df=df).read_text(encoding="utf-8")
    assert "Structure &amp; Hashtag Kit" in html and "Cặp tag hay đi cùng" in html


def test_opportunity_has_concentration_columns(tmp_path):
    rows = []
    for kw, creators in (("a", 1), ("b", 20)):
        for i in range(20):
            rows.append({"aweme_id": f"{kw}{i}", "title": "x", "liked_count": 100, "collected_count": 5,
                         "comment_count": 1, "share_count": 1, "create_time": CRAWL_S,
                         "creator_hash": f"{kw}{i % creators}", "source_keyword": kw})
    g = an.opportunity_map(_load(rows, tmp_path, "search_contents_o.json")).set_index("source_keyword")
    assert {"so_creator", "top3_pct", "hhi", "do_kho_vao"} <= set(g.columns)
    assert g.loc["b", "do_kho_vao"] == "dễ vào"
    assert pd.isna(g.loc["a", "hhi"])                   # 1 creator: không tính mức tập trung
