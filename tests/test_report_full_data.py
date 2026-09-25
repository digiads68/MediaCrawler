# -*- coding: utf-8 -*-
"""Báo cáo phải hiện ĐỦ dữ liệu đã cào, giữ lưới thẻ & nút cũ, có ô nhận xét (synthetic)."""

from __future__ import annotations

import json
import re

import pandas as pd

from kit.analyzer import mediacrawler_analyzer as an
from kit.report import html_report as hr

DAY_MS = 86_400_000
CRAWL_MS = 1_790_000_000_000


def _trend_html(tmp_path, monkeypatch, n: int = 70) -> str:
    rows = [{"aweme_id": str(i), "title": f"hook {i} #aigc", "desc": f"hook {i} #aigc",
             "liked_count": 100 + i, "collected_count": 10 + i, "comment_count": 1 + i % 7,
             "share_count": 2 + i % 5, "create_time": (CRAWL_MS - i * DAY_MS) // 1000,
             "last_modify_ts": CRAWL_MS, "creator_hash": f"c{i % 9}", "source_keyword": "#aigc",
             "aweme_url": f"https://www.douyin.com/video/{i}",
             "video_download_url": f"https://www.douyin.com/aweme/v1/play/?video_id={i}",
             "cover_url": f"https://p3.douyinpic.com/{i}.jpg"} for i in range(n)]
    p = tmp_path / "douyin" / "json" / "search_contents.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(rows), encoding="utf-8")
    df = an.load(p)
    monkeypatch.setattr(hr, "REPORT_DIR", tmp_path / "reports")
    out = hr.build_report("trend", an.trend_radar(df), df=df, meta={"keyword": "#aigc"})
    return out.read_text(encoding="utf-8")


def test_trend_report_renders_every_post_with_pagination(tmp_path, monkeypatch):
    html = _trend_html(tmp_path, monkeypatch, 70)
    assert html.count('class="mcard"') == 70            # không còn cắt 20 bài
    assert 'id="trend-size"' in html and 'value="0">Tất cả' in html
    assert 'DAMG("trend")' in html


def test_card_keeps_preview_and_actions(tmp_path, monkeypatch):
    html = _trend_html(tmp_path, monkeypatch, 5)
    card = re.search(r'<article class="mcard".*?</article>', html, re.S).group(0)
    for needle in ('class="mcard-thumb"', "<img ", "mcard-play", "▶ Xem", "⬇ Tải",
                   "📋 Copy hook", "Xem đầy đủ", "Save/Like", "Share/Like"):
        assert needle in card, needle
    assert "/kit/media/download?url=" in card


def test_detailed_filters_present(tmp_path, monkeypatch):
    html = _trend_html(tmp_path, monkeypatch, 10)
    for fid in ("trend-search", "trend-sort", "trend-goal", "trend-age", "trend-chips"):
        assert f'id="{fid}"' in html, fid
    assert 'value="created"' in html                     # sắp theo mới đăng


def test_commentary_panel_and_llm_payload(tmp_path, monkeypatch):
    html = _trend_html(tmp_path, monkeypatch, 10)
    assert 'id="commentary"' in html and 'id="analyst-note"' in html
    assert 'id="llm-commentary"' in html                 # chỗ cắm LLM sau này
    data = re.search(r'<script type="application/json" id="report-summary">(.*?)</script>',
                     html, re.S).group(1)
    payload = json.loads(data)
    assert payload["summary"]["posts"] == 10
    assert len(payload["top_posts"]) == 10
    assert "data-prompt=" in html


def test_verdict_block_before_evidence(tmp_path, monkeypatch):
    html = _trend_html(tmp_path, monkeypatch, 20)
    assert html.index('class="verdict"') < html.index("Bằng chứng") < html.index("Dữ liệu đầy đủ")


def test_table_shows_all_rows_with_pager():
    df = pd.DataFrame({"title": [f"r{i}" for i in range(120)], "liked_count": range(120)})
    html = hr._table(df, max_rows=20)
    assert html.count("<tr>") == 121                     # 120 dòng + header
    assert "pager-bar" in html and 'data-size="20"' in html


def test_every_report_gets_commentary(tmp_path, monkeypatch):
    monkeypatch.setattr(hr, "REPORT_DIR", tmp_path)
    df = pd.DataFrame({"source_keyword": ["a"], "quadrant": ["x"], "save_tb": [1.0]})
    html = hr.build_report("opportunity", df).read_text(encoding="utf-8")
    assert 'id="commentary"' in html
