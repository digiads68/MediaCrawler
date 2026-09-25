# -*- coding: utf-8 -*-
"""
Soi file dữ liệu -> dashboard nào chạy được.

WebUI (mục PAYLOAD_MATRIX) gọi qua `GET /kit/analyze/capabilities` để chỉ bật
những dashboard mà dữ liệu thực sự đỡ được, kèm lý do khi không đỡ được — thay
vì để người dùng chọn rồi mới nhận lỗi từ analyzer.

Điều kiện ở đây phản chiếu đúng yêu cầu thật của từng hàm trong
`mediacrawler_analyzer.py`; sửa analyzer thì sửa cả đây.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

# Cột đếm engagement CẤP BÀI ĐĂNG — cần ít nhất 1 cột có số > 0.
#
# CỐ Ý không liệt kê cột cấp bình luận (`like_count`, `comment_like_count`,
# `sub_comment_count`) và không liệt kê cột canonical `m_*`: `m_like` được suy ra
# từ `like_count` với file bình luận, nên nếu tính vào đây thì file bình luận sẽ
# bị coi là "có engagement" và mở sai các dashboard cần dữ liệu bài đăng.
_ENGAGEMENT_COLS = (
    # xhs / douyin
    "collected_count", "share_count", "comment_count", "liked_count",
    # bilibili
    "video_favorite_count", "video_share_count", "video_comment",
    "video_play_count", "video_coin_count",
    # weibo
    "comments_count", "shared_count",
    # kuaishou / zhihu / tieba
    "viewd_count", "voteup_count", "total_replay_num",
)

# Số video tối thiểu / creator để chấm KOC (khớp koc_scorecard.min_videos)
_KOC_MIN_VIDEOS = 5


def _has_any_engagement(df: pd.DataFrame) -> bool:
    """Có chỉ số tương tác CẤP BÀI ĐĂNG nào lớn hơn 0 không."""
    return any(c in df.columns and pd.to_numeric(df[c], errors="coerce").fillna(0).max() > 0
               for c in _ENGAGEMENT_COLS)


def _is_comment_data(df: pd.DataFrame) -> bool:
    """File comment: có cột nội dung bình luận (content/comment_content)."""
    if "comment_content" in df.columns:
        return True
    # Weibo dùng `content` cho CẢ bài đăng lẫn bình luận -> phân biệt bằng cột
    # chỉ có ở bình luận. Nếu chỉ dựa vào `content` thì bài đăng weibo bị nhận
    # nhầm là bình luận và mọi dashboard bài đăng đều bị khoá oan.
    if "content" not in df.columns:
        return False
    comment_only = ("comment_id", "parent_comment_id", "sub_comment_count",
                    "comment_like_count")
    if any(c in df.columns for c in comment_only):
        return True
    # Có `content` mà cũng có dấu hiệu bài đăng -> là bài đăng
    post_only = ("note_url", "aweme_url", "video_url", "content_url", "note_id",
                 "aweme_id", "video_id", "source_keyword")
    return not any(c in df.columns for c in post_only)


def _koc_eligible_creators(df: pd.DataFrame) -> int:
    key = "creator_hash" if "creator_hash" in df.columns else (
        "nickname" if "nickname" in df.columns else None)
    if key is None or "created_at" not in df.columns:
        return 0
    counts = df.groupby(key).size()
    return int((counts >= _KOC_MIN_VIDEOS).sum())


def _check_trend(df: pd.DataFrame) -> tuple[bool, str]:
    # Gate file bình luận VÔ ĐIỀU KIỆN (không kèm "and not has_engagement"):
    # sau khi có tầng canonical, file bình luận cũng sinh ra cột chỉ số nên điều
    # kiện cũ không còn chặn được.
    if _is_comment_data(df):
        return False, "File này là dữ liệu bình luận — Trend Radar cần file bài đăng."
    if not _has_any_engagement(df):
        return False, ("Thiếu chỉ số tương tác (like/save/share/bình luận) "
                       "hoặc toàn bộ đang bằng 0.")
    return True, ""


def _check_insight(df: pd.DataFrame) -> tuple[bool, str]:
    if not _is_comment_data(df):
        return False, ("Cần file BÌNH LUẬN (có cột content). File bài đăng không "
                       "dùng được — bật 'Comment Extraction' khi cào để có file này.")
    return True, ""


def _check_koc(df: pd.DataFrame) -> tuple[bool, str]:
    if "created_at" not in df.columns:
        return False, "Thiếu create_time — không tính được velocity (đang lên/nguội)."
    if not _has_any_engagement(df):
        return False, "Thiếu chỉ số tương tác để tính engagement trung bình."
    n = _koc_eligible_creators(df)
    if n == 0:
        return False, (f"Không creator nào đủ {_KOC_MIN_VIDEOS} video trong file. "
                       f"Dùng Creator Mode hoặc cào thêm dữ liệu.")
    return True, f"{n} creator đủ điều kiện chấm điểm."


def _check_opportunity(df: pd.DataFrame) -> tuple[bool, str]:
    if "source_keyword" not in df.columns:
        return False, "Thiếu source_keyword — bản đồ cơ hội gom theo từ khoá."
    n_kw = int(df["source_keyword"].astype(str).str.strip().replace("", pd.NA)
               .dropna().nunique())
    if n_kw < 2:
        return False, (f"Chỉ có {n_kw} từ khoá — cần ≥2 từ khoá để so sánh ngách "
                       f"(cào nhiều keyword trong 1 lần).")
    if not _has_any_engagement(df):
        return False, "Thiếu chỉ số tương tác để tính save/engagement trung bình."
    return True, f"{n_kw} từ khoá để so sánh."


def _check_seasonal(df: pd.DataFrame) -> tuple[bool, str]:
    if "week" not in df.columns:
        return False, "Thiếu create_time — không dựng được trục thời gian theo tuần."
    n_weeks = int(df["week"].dropna().nunique())
    if n_weeks < 2:
        return False, (f"Dữ liệu chỉ nằm trong {n_weeks} tuần — cần ≥2 tuần mới "
                       f"thấy được sóng mùa vụ.")
    return True, f"{n_weeks} tuần dữ liệu."


def _check_price(df: pd.DataFrame) -> tuple[bool, str]:
    if not any(c in df.columns for c in ("desc", "content", "title")):
        return False, "Thiếu cột văn bản (desc/content/title) để dò giá & khuyến mãi."
    return True, ""


def _check_sov(df: pd.DataFrame) -> tuple[bool, str]:
    if "week" not in df.columns:
        return False, "Thiếu create_time — SOV tính theo tuần."
    if not any(c in df.columns for c in ("title", "desc")):
        return False, "Thiếu title/desc để gắn bài vào brand."
    if not _has_any_engagement(df):
        return False, "Thiếu chỉ số tương tác — SOV tính theo % engagement."
    return True, "Cần thêm brand_map.json (rổ brand cần theo dõi)."


def _check_angle(df: pd.DataFrame) -> tuple[bool, str]:
    if "title" not in df.columns:
        return False, "Thiếu title — angle lấy hook từ tiêu đề bài."
    if not _has_any_engagement(df):
        return False, "Thiếu chỉ số tương tác để lọc top theo điểm trend."
    return True, ""


_CHECKS = {
    "trend": _check_trend,
    "insight": _check_insight,
    "koc": _check_koc,
    "opportunity": _check_opportunity,
    "seasonal": _check_seasonal,
    "price": _check_price,
    "sov": _check_sov,
    "angle": _check_angle,
}


def inspect_data_file(path: str | Path) -> dict[str, Any]:
    """
    Nạp file (xlsx/jsonl/csv) rồi trả về khả năng chạy từng dashboard.

    Returns:
        {
          "file": tên file, "rows": số dòng, "kind": "posts"|"comments",
          "columns": [...],
          "capabilities": {
             "<command>": {"supported": bool, "reason": str}
          }
        }
    """
    p = Path(path)
    # Dùng chung `load()` của analyzer thay vì đọc lại: nhờ đó bảng khả năng được
    # chấm trên ĐÚNG dữ liệu mà analyzer sẽ thấy (đã đóng dấu nền tảng, đã map
    # cột canonical, đã bỏ dòng trùng). Trước đây đọc riêng nên có thể kết luận
    # lệch với lúc chạy thật.
    from kit.analyzer.mediacrawler_analyzer import load

    df = load(p)

    caps: dict[str, dict[str, Any]] = {}
    for command, check in _CHECKS.items():
        try:
            ok, reason = check(df)
        except Exception as exc:  # noqa: BLE001 — 1 check lỗi không chặn cả bảng
            ok, reason = False, f"Không kiểm tra được: {exc}"
        caps[command] = {"supported": bool(ok), "reason": reason}

    return {
        "file": p.name,
        "rows": int(len(df)),
        "kind": "comments" if _is_comment_data(df) else "posts",
        "columns": [str(c) for c in df.columns],
        "capabilities": caps,
    }
