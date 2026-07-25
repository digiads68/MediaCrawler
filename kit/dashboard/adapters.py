# -*- coding: utf-8 -*-
"""
Bộ chuyển đổi (adapter) schema riêng từng nền tảng → **schema hợp nhất**.

Mỗi nền tảng MediaCrawler xuất tên cột khác nhau (aweme_id vs video_id vs
note_id; cover_url vs video_cover_url vs image_list; ...). Module này nhận diện
nền tảng theo chữ ký cột rồi ánh xạ về một khung cột chung để analyzer/normalize
và dashboard dùng lại được — KHÔNG lặp logic ở nơi khác.

Khung cột hợp nhất (sau adapter, trước khi normalize):
    platform, content_kind, item_id, title, desc, create_time,
    nickname, creator_hash, liked_count, collected_count, comment_count,
    share_count, play_count, coin_count, danmaku_count, cover_url,
    content_url, download_url, music_url, source_keyword, tags, media_type
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Cột đích chung — dashboard/normalize dựa vào bộ này.
UNIFIED_COLS: list[str] = [
    "platform", "content_kind", "item_id", "title", "desc", "create_time",
    "nickname", "creator_hash", "liked_count", "collected_count",
    "comment_count", "share_count", "play_count", "coin_count",
    "danmaku_count", "cover_url", "content_url", "download_url", "music_url",
    "source_keyword", "tags", "media_type",
]

# Nhãn nền tảng hiển thị (tiếng Việt/gọn) — dùng chung ở render.
PLATFORM_LABELS: dict[str, str] = {
    "douyin": "Douyin", "bilibili": "Bilibili", "xhs": "Xiaohongshu",
    "kuaishou": "Kuaishou", "weibo": "Weibo", "unknown": "Khác",
}


def detect_platform(df: pd.DataFrame) -> str:
    """Nhận diện nền tảng theo chữ ký cột đặc trưng."""
    cols = set(df.columns)
    if "aweme_id" in cols:
        return "douyin"
    if "video_id" in cols and {"video_play_count", "video_danmaku"} & cols:
        return "bilibili"
    if "note_id" in cols:
        return "xhs"
    return "unknown"


def _kind_from_name(source: str | None) -> str:
    """Suy ra loại dữ liệu (search / creator) từ tên file."""
    s = (source or "").lower()
    if "creator" in s or "user" in s or "profile" in s:
        return "creator"
    if "detail" in s:
        return "detail"
    return "search"


def _first_url(value: object) -> str:
    """Lấy URL đầu tiên trong chuỗi ngăn cách bởi dấu phẩy (image_list XHS)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).strip()
    if not s:
        return ""
    return s.split(",")[0].strip()


def _col(df: pd.DataFrame, name: str, default: object = "") -> pd.Series:
    """Trả cột nếu có, nếu không thì Series mặc định cùng độ dài."""
    if name in df.columns:
        return df[name]
    return pd.Series([default] * len(df), index=df.index)


def _adapt_douyin(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["platform"] = "douyin"
    out["content_kind"] = kind
    out["item_id"] = _col(df, "aweme_id").astype(str)
    out["title"] = _col(df, "title")
    out["desc"] = _col(df, "desc")
    out["create_time"] = _col(df, "create_time", 0)
    out["nickname"] = _col(df, "nickname")
    out["creator_hash"] = _col(df, "creator_hash")
    out["liked_count"] = _col(df, "liked_count", 0)
    out["collected_count"] = _col(df, "collected_count", 0)
    out["comment_count"] = _col(df, "comment_count", 0)
    out["share_count"] = _col(df, "share_count", 0)
    out["play_count"] = 0
    out["coin_count"] = 0
    out["danmaku_count"] = 0
    out["cover_url"] = _col(df, "cover_url")
    out["content_url"] = _col(df, "aweme_url")
    out["download_url"] = _col(df, "video_download_url")
    out["music_url"] = _col(df, "music_download_url")
    out["source_keyword"] = _col(df, "source_keyword")
    out["tags"] = ""
    out["media_type"] = "video"
    return out


def _adapt_bilibili(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["platform"] = "bilibili"
    out["content_kind"] = kind
    out["item_id"] = _col(df, "video_id").astype(str)
    out["title"] = _col(df, "title")
    out["desc"] = _col(df, "desc")
    out["create_time"] = _col(df, "create_time", 0)
    out["nickname"] = _col(df, "nickname")
    out["creator_hash"] = _col(df, "creator_hash")
    out["liked_count"] = _col(df, "liked_count", 0)
    # Bilibili gọi "favorite" là save; coin/danmaku là chỉ số riêng của B.
    out["collected_count"] = _col(df, "video_favorite_count", 0)
    out["comment_count"] = _col(df, "video_comment", 0)
    out["share_count"] = _col(df, "video_share_count", 0)
    out["play_count"] = _col(df, "video_play_count", 0)
    out["coin_count"] = _col(df, "video_coin_count", 0)
    out["danmaku_count"] = _col(df, "video_danmaku", 0)
    out["cover_url"] = _col(df, "video_cover_url")
    out["content_url"] = _col(df, "video_url")
    # File mới có cột download_url riêng; file cũ chỉ có trang video.
    dl = _col(df, "download_url")
    out["download_url"] = dl.where(dl.astype(str).str.len() > 0, _col(df, "video_url"))
    out["music_url"] = ""
    out["source_keyword"] = _col(df, "source_keyword")
    out["tags"] = ""
    out["media_type"] = "video"
    return out


def _adapt_xhs(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["platform"] = "xhs"
    out["content_kind"] = kind
    out["item_id"] = _col(df, "note_id").astype(str)
    out["title"] = _col(df, "title")
    out["desc"] = _col(df, "desc")
    # XHS lưu thời gian ở cột `time` (epoch mili-giây).
    out["create_time"] = _col(df, "time", 0)
    out["nickname"] = _col(df, "nickname")
    out["creator_hash"] = _col(df, "creator_hash")
    out["liked_count"] = _col(df, "liked_count", 0)
    out["collected_count"] = _col(df, "collected_count", 0)
    out["comment_count"] = _col(df, "comment_count", 0)
    out["share_count"] = _col(df, "share_count", 0)
    out["play_count"] = 0
    out["coin_count"] = 0
    out["danmaku_count"] = 0
    out["cover_url"] = _col(df, "image_list").map(_first_url)
    out["content_url"] = _col(df, "note_url")
    out["download_url"] = _col(df, "video_url")
    out["music_url"] = ""
    out["source_keyword"] = _col(df, "source_keyword")
    out["tags"] = _col(df, "tag_list")
    out["media_type"] = _col(df, "type").map(
        lambda t: "video" if str(t).lower() == "video" else "image")
    return out


_ADAPTERS = {
    "douyin": _adapt_douyin,
    "bilibili": _adapt_bilibili,
    "xhs": _adapt_xhs,
}


def adapt(df: pd.DataFrame, *, source: str | None = None) -> pd.DataFrame:
    """
    Chuyển 1 DataFrame raw (đã đọc từ file) sang schema hợp nhất.

    `source`: tên/đường dẫn file gốc — dùng để suy ra content_kind
    (search/creator) và điền cột `source_file`.
    """
    platform = detect_platform(df)
    kind = _kind_from_name(source)
    if platform in _ADAPTERS:
        out = _ADAPTERS[platform](df, kind)
    else:
        # Nền tảng lạ: giữ những cột trùng tên, phần còn thiếu để rỗng.
        out = pd.DataFrame(index=df.index)
        for c in UNIFIED_COLS:
            out[c] = _col(df, c, 0 if c.endswith("_count") else "")
        out["platform"] = "unknown"
        out["content_kind"] = kind
    out["source_file"] = Path(source).name if source else ""
    return out
