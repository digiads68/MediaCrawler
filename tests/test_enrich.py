# -*- coding: utf-8 -*-
"""Test lớp enrichment (kit/enrich) — dữ liệu synthetic, không gọi mạng."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from kit.enrich import (
    add_engagement,
    normalize,
    normalize_counts,
    tag_format,
    translate_zh_vi,
    weekly_velocity,
)


@pytest.fixture
def raw_df() -> pd.DataFrame:
    """DataFrame synthetic giống output MediaCrawler (count Text, epoch trộn s/ms)."""
    return pd.DataFrame({
        "title": ["7天变化太大了", "真实测评这款精华", "开箱新品", "随便聊聊"],
        "desc": ["前后对比", "亲测有效", "到货啦", ""],
        "liked_count": ["1,234", "500", "0", "10"],
        "comment_count": ["56", "20", "1", "2"],
        "share_count": ["7", "3", "0", "0"],
        "collected_count": ["890", "100", "0", "1"],
        # 2 epoch giây + 2 epoch mili-giây (cùng ngày 2026-01-05 .. 2026-01-14)
        "create_time": [1767600000, 1767700000, 1768300000000, 1768400000000],
        "source_keyword": ["护肤", "护肤", "精华", "精华"],
        "creator_hash": ["c1", "c1", "c2", "c2"],
    })


def test_normalize_counts_ep_text_thanh_so(raw_df):
    d = normalize_counts(raw_df)
    assert d["liked_count"].tolist() == [1234.0, 500.0, 0.0, 10.0]
    assert d["collected_count"].dtype == float


def test_normalize_counts_parse_thoi_gian_s_va_ms(raw_df):
    d = normalize_counts(raw_df)
    assert d["created_at"].notna().all()
    # epoch ms phải được chia 1000 — cùng nằm trong năm 2026
    assert (d["created_at"].dt.year == 2026).all()
    assert d["week"].str.match(r"^\d{4}-W\d{2}$").all()


def test_add_engagement_tinh_tong_va_ty_le(raw_df):
    d = add_engagement(normalize_counts(raw_df))
    assert d["eng_total"].iloc[0] == 1234 + 56 + 7 + 890
    assert d["save_rate"].iloc[0] == pytest.approx(890 / 1234)
    # like = 0 -> NA, không chia 0
    assert pd.isna(d["save_rate"].iloc[2])


def test_tag_format_gan_nhan(raw_df):
    d = tag_format(raw_df)
    assert d["format"].tolist() == ["before-after", "review/測評", "unboxing", "khác"]


def test_normalize_chuoi_day_du(raw_df):
    d = normalize(raw_df)
    for col in ["eng_total", "save_rate", "format", "created_at", "week"]:
        assert col in d.columns


def test_analyzer_dung_chung_normalize():
    """Regression: analyzer.normalize phải là chính hàm của kit.enrich."""
    from kit.analyzer import mediacrawler_analyzer as an
    from kit.enrich import normalize as enrich_normalize
    assert an.normalize is enrich_normalize


def test_weekly_velocity_phat_hien_dang_len():
    df = pd.DataFrame({
        "creator_hash": ["a"] * 4 + ["b"] * 4,
        "eng_total": [10, 10, 30, 30, 40, 40, 10, 10],   # a tăng ×3, b giảm
        "created_at": pd.date_range("2026-01-01", periods=8, freq="D"),
    })
    v = weekly_velocity(df, key="creator_hash").set_index("creator_hash")
    assert v.loc["a", "velocity"] == pytest.approx(3.0)
    assert v.loc["b", "velocity"] == pytest.approx(0.25)


def test_weekly_velocity_thieu_cot_bao_loi():
    with pytest.raises(ValueError):
        weekly_velocity(pd.DataFrame({"x": [1]}), key="creator_hash")


class _FakeResp:
    def __init__(self, text: str):
        self.content = [type("Block", (), {"text": text})()]


class _FakeClient:
    """Client Anthropic giả — trả bản dịch [vi]<gốc>, đếm số lần gọi."""

    def __init__(self):
        self.calls: list[dict] = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        batch = json.loads(kwargs["messages"][0]["content"].split(":\n", 1)[1])
        return _FakeResp(json.dumps([f"[vi]{t}" for t in batch], ensure_ascii=False))


def test_translate_provider_none_tra_nguyen_van():
    texts = ["你好", "护肤"]
    assert translate_zh_vi(texts, provider="none") == texts


def test_translate_claude_voi_client_gia_va_batch():
    texts = [f"câu {i}" for i in range(5)]
    fake = _FakeClient()
    out = translate_zh_vi(texts, provider="claude", client=fake, batch_size=2)
    assert out == [f"[vi]{t}" for t in texts]
    assert len(fake.calls) == 3  # 5 câu / batch 2 -> 3 lần gọi


def test_translate_loi_json_khong_raise():
    class _BadClient:
        def __init__(self):
            self.messages = self

        def create(self, **kwargs):
            return _FakeResp("không phải json")

    texts = ["a", "b"]
    out = translate_zh_vi(texts, provider="claude", client=_BadClient())
    assert out == texts  # fallback nguyên văn, không crash
