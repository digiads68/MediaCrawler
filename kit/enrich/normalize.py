# -*- coding: utf-8 -*-
"""
Chuẩn hoá dữ liệu thô MediaCrawler (dùng chung cho analyzer + storage).

Nguồn sự thật duy nhất cho: COUNT_COLS, FORMAT_RULES, các hàm normalize.
Analyzer import lại từ đây — không lặp logic.
"""

from __future__ import annotations

import pandas as pd

# Các cột đếm mà MediaCrawler có thể xuất dạng Text ("1,234", "5678"...)
COUNT_COLS: list[str] = [
    "liked_count", "comment_count", "share_count", "collected_count",
    "video_play_count", "like_count", "sub_comment_count",
]

# Bảng nhận diện FORMAT từ tiêu đề/mô tả (mở rộng dần theo ngành khách)
FORMAT_RULES: dict[str, list[str]] = {
    "before-after": ["前后", "对比", "变化", "7天", "30天", "trước sau", "thay đổi"],
    "review/測評":  ["测评", "评测", "真实", "亲测", "review", "đánh giá"],
    "list/top":     ["清单", "合集", "top", "盘点", "必买", "list"],
    "tutorial":     ["教程", "教你", "步骤", "how", "hướng dẫn", "cách"],
    "unboxing":     ["开箱", "到货", "unboxing", "đập hộp"],
    "storytime":    ["故事", "经历", "翻车", "踩雷", "storytime"],
    "pov/skit":     ["pov", "当你", "剧情", "假如"],
}


def normalize_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Ép cột count Text -> số; parse create_time (epoch s/ms) -> created_at + week ISO."""
    df = df.copy()
    for c in COUNT_COLS:
        if c in df.columns:
            df[c] = (df[c].astype(str)
                     .str.replace(r"[^\d.]", "", regex=True)
                     .replace("", "0").astype(float))
    if "create_time" in df.columns:
        ts = pd.to_numeric(df["create_time"], errors="coerce")
        # MediaCrawler lưu epoch giây hoặc mili-giây tuỳ nền tảng
        ts = ts.where(ts < 1e12, ts / 1000)
        df["created_at"] = pd.to_datetime(ts, unit="s", errors="coerce")
        df["week"] = df["created_at"].dt.strftime("%G-W%V")
    return df


def add_engagement(df: pd.DataFrame) -> pd.DataFrame:
    """Thêm eng_total, save_rate, share_rate (tỷ lệ trên like, tránh chia 0)."""
    df = df.copy()
    like = df.get("liked_count", 0)
    df["eng_total"] = (df.get("liked_count", 0) + df.get("comment_count", 0)
                       + df.get("share_count", 0) + df.get("collected_count", 0))
    if hasattr(like, "replace"):
        df["save_rate"] = df.get("collected_count", 0) / like.replace(0, pd.NA)
        df["share_rate"] = df.get("share_count", 0) / like.replace(0, pd.NA)
    else:
        df["save_rate"] = 0
        df["share_rate"] = 0
    return df


def tag_format(df: pd.DataFrame) -> pd.DataFrame:
    """Gắn nhãn format nội dung theo FORMAT_RULES (dò trong title + desc)."""
    df = df.copy()
    text = (df.get("title", "").fillna("") + " "
            + df.get("desc", "").fillna("")).str.lower()

    def tag(t: str) -> str:
        for fmt, kws in FORMAT_RULES.items():
            if any(k in t for k in kws):
                return fmt
        return "khác"

    df["format"] = text.map(tag)
    return df


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Chuỗi chuẩn hoá đầy đủ: counts/thời gian -> engagement -> format."""
    return tag_format(add_engagement(normalize_counts(df)))
