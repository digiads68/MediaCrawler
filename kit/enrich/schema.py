# -*- coding: utf-8 -*-
"""
Bản đồ cột của 7 nền tảng -> tên canonical dùng chung (nguồn sự thật duy nhất).

Vì sao cần: mỗi nền tảng đặt tên cột khác nhau cho cùng một thứ, nên analyzer và
báo cáo chỉ chạy đúng với vài nền tảng. Ví dụ đã đo trên dữ liệu thật:
  - Bài Bilibili có like 472K + favorite 744K + comment 320K + share 91K nhưng
    `eng_total` chỉ ra 472K (đúng phần like), `save_rate`/`share_rate` = 0, vì
    `COUNT_COLS` không biết `video_favorite_count`/`video_share_count`/`video_comment`.
  - Báo cáo XHS không hiện ảnh nào vì XHS lưu cover ở `image_list[0]`, không có
    cột `cover_url` như Douyin.
  - Không nền tảng nào ghi cột `platform`, nên không gộp/so sánh đa nền tảng được.

Phân vai với `normalize.py`: file này là *bản đồ cột*, `normalize.py` là *phép
biến đổi*. Tách ra để `normalize.py` không phồng lên và vẫn giữ đúng vai "nguồn
sự thật cho COUNT_COLS/FORMAT_RULES".

Hai quy ước đặt tên BẮT BUỘC (đừng đổi, sẽ vỡ âm thầm):
  1. Cột chỉ số là `m_*` (m_like/m_comment/...) chứ không phải `like`/`comment`.
     Lý do: file bình luận cũng có cột `like_count` — cùng tên nhưng khác nghĩa
     (like của 1 bình luận, không phải của bài).
  2. Cover canonical là `cover_url_c`, KHÔNG ghi đè `cover_url`. Douyin đã có sẵn
     cột `cover_url`; ghi đè sẽ phá `_media_grid` theo cách khó thấy.

Mọi hàm ở đây chỉ THÊM cột, không rename/xoá cột gốc -> 8 lệnh analyzer cũ và
toàn bộ test hiện có không bị ảnh hưởng.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

# ---------------------------------------------------------------------------
# Mã nền tảng <-> thư mục dữ liệu
# ---------------------------------------------------------------------------
# CẢNH BÁO: mã nền tảng KHÔNG trùng tên thư mục. Đã đo qua API đang chạy:
#   /api/data/files?platform=dy     -> 0 file
#   /api/data/files?platform=douyin -> 3 file
# vì bộ lọc so khớp chuỗi con của đường dẫn, mà thư mục là `data/douyin/`.
# Hệ quả: MCP (gửi mã ngắn `dy`) luôn báo "chưa thấy file kết quả" dù cào xong.
#
# Bilibili ghi vào HAI thư mục: Excel -> `data/bilibili/`, JSON -> `data/bili/`.
PLATFORM_DIRS: dict[str, tuple[str, ...]] = {
    "xhs": ("xhs",),
    "dy": ("douyin",),
    "ks": ("kuaishou",),
    "bili": ("bilibili", "bili"),
    "wb": ("weibo",),
    "tieba": ("tieba",),
    "zhihu": ("zhihu",),
}

# Alias người/agent hay dùng -> mã chuẩn
PLATFORM_ALIASES: dict[str, str] = {
    "xhs": "xhs", "xiaohongshu": "xhs", "red": "xhs", "rednote": "xhs",
    "dy": "dy", "douyin": "dy", "tiktok_cn": "dy",
    "ks": "ks", "kuaishou": "ks",
    "bili": "bili", "bilibili": "bili",
    "wb": "wb", "weibo": "wb",
    "tieba": "tieba", "baidu_tieba": "tieba",
    "zhihu": "zhihu",
}

PLATFORM_LABELS: dict[str, str] = {
    "xhs": "Xiaohongshu", "dy": "Douyin", "ks": "Kuaishou",
    "bili": "Bilibili", "wb": "Weibo", "tieba": "Tieba", "zhihu": "Zhihu",
}


def resolve(name: str) -> str:
    """Alias -> mã chuẩn. Không biết thì trả nguyên chuỗi đã lower."""
    key = (name or "").strip().lower()
    return PLATFORM_ALIASES.get(key, key)


def dirs_for(code: str) -> tuple[str, ...]:
    """Tên thư mục dữ liệu của 1 mã nền tảng (có thể nhiều — xem Bilibili)."""
    return PLATFORM_DIRS.get(resolve(code), (resolve(code),))


def code_from_path(path: str | Path) -> str:
    """
    Suy mã nền tảng từ đường dẫn file dữ liệu.

    Ưu tiên tên thư mục (`data/douyin/...`), sau đó tiền tố tên file
    (`douyin_search_...xlsx`). Không suy được -> "".
    """
    parts = [p.lower() for p in Path(path).parts]
    for code, names in PLATFORM_DIRS.items():
        if any(n in parts for n in names):
            return code
    stem = Path(path).stem.lower()
    for code, names in PLATFORM_DIRS.items():
        if any(stem.startswith(n + "_") for n in names):
            return code
    return ""


# Cột "dấu vết" chỉ tồn tại ở 1 nền tảng — dùng khi đường dẫn không nói gì
# (vd file đã copy đi nơi khác, hoặc DataFrame dựng trong bộ nhớ).
_FINGERPRINTS: tuple[tuple[str, str], ...] = (
    ("xsec_token", "xhs"),
    ("aweme_id", "dy"),
    ("video_danmaku", "bili"),
    ("video_coin_count", "bili"),
    ("viewd_count", "ks"),
    ("shared_count", "wb"),
    ("tieba_name", "tieba"),
    ("voteup_count", "zhihu"),
)


def sniff_platform_from_columns(df: pd.DataFrame) -> str:
    """Suy nền tảng từ cột đặc trưng. Không chắc -> ""."""
    cols = set(df.columns)
    for col, code in _FINGERPRINTS:
        if col in cols:
            return code
    return ""


def infer_platform(path: str | Path | None = None,
                   df: pd.DataFrame | None = None) -> str:
    """Suy nền tảng: đường dẫn trước, cột đặc trưng sau."""
    if path:
        code = code_from_path(path)
        if code:
            return code
    if df is not None:
        return sniff_platform_from_columns(df)
    return ""


# ---------------------------------------------------------------------------
# Bản đồ cột canonical -> tên cột gốc theo từng nền tảng
# ---------------------------------------------------------------------------
# Chỉ liệt kê cột THỰC SỰ tồn tại (đã đối chiếu store/*/__init__.py và
# model/m_*.py). Thiếu = nền tảng đó không có dữ liệu đó, và phải để NaN chứ
# KHÔNG điền 0 — 0 nghĩa là "đo được và bằng 0", NaN nghĩa là "không đo được".
PLATFORM_COLUMN_MAP: dict[str, dict[str, str]] = {
    "xhs": {
        "post_id": "note_id", "title_text": "title", "body_text": "desc",
        "page_url": "note_url", "media_kind": "type",
        "m_like": "liked_count", "m_comment": "comment_count",
        "m_share": "share_count", "m_save": "collected_count",
    },
    "dy": {
        "post_id": "aweme_id", "title_text": "title", "body_text": "desc",
        "page_url": "aweme_url", "media_url": "video_download_url",
        "cover_url_c": "cover_url", "media_kind": "aweme_type",
        "m_like": "liked_count", "m_comment": "comment_count",
        "m_share": "share_count", "m_save": "collected_count",
    },
    "ks": {
        "post_id": "video_id", "title_text": "title", "body_text": "desc",
        "page_url": "video_url", "media_url": "video_play_url",
        "cover_url_c": "video_cover_url", "media_kind": "video_type",
        "m_like": "liked_count", "m_view": "viewd_count",
    },
    "bili": {
        "post_id": "video_id", "title_text": "title", "body_text": "desc",
        "page_url": "video_url", "media_url": "download_url",
        "cover_url_c": "video_cover_url", "media_kind": "video_type",
        "m_like": "liked_count", "m_comment": "video_comment",
        "m_share": "video_share_count", "m_save": "video_favorite_count",
        "m_view": "video_play_count",
    },
    "wb": {
        # Weibo không có title/desc riêng — chỉ `content` (đã strip HTML).
        "post_id": "note_id", "title_text": "content", "body_text": "content",
        "page_url": "note_url",
        "m_like": "liked_count", "m_comment": "comments_count",
        "m_share": "shared_count",
    },
    "tieba": {
        "post_id": "note_id", "title_text": "title", "body_text": "desc",
        "page_url": "note_url", "nickname": "user_nickname",
        "m_comment": "total_replay_num",
    },
    "zhihu": {
        "post_id": "content_id", "title_text": "title", "body_text": "desc",
        "page_url": "content_url", "nickname": "user_nickname",
        "media_kind": "content_type",
        "m_like": "voteup_count", "m_comment": "comment_count",
    },
}

# Cột bình luận: mọi nền tảng đều `content`, nhưng like thì Weibo đặt tên khác.
COMMENT_LIKE_ALIASES: tuple[str, ...] = ("like_count", "comment_like_count")

# Thứ tự thử khi lấy cover cho 1 dòng (không phụ thuộc nền tảng)
_COVER_CANDIDATES: tuple[str, ...] = ("cover_url", "video_cover_url", "cover_url_c")

_MEDIA_EXTS = (".mp3", ".m4a", ".aac", ".wav", ".mp4", ".flv", ".webm")


def cover_of_row(r: "pd.Series") -> str:
    """
    Link ảnh cover của 1 dòng, thử lần lượt các tên cột rồi tới `image_list`.

    XHS không có cột cover riêng — ảnh đầu trong `image_list` chính là cover.
    Đây là lý do báo cáo XHS trước đây không hiện ảnh nào.
    """
    for col in _COVER_CANDIDATES:
        v = r.get(col)
        if v is not None and not pd.isna(v) and str(v).strip():
            return str(v).strip()
    imgs = r.get("image_list")
    if imgs is not None and not pd.isna(imgs) and str(imgs).strip():
        first = str(imgs).split(",")[0].strip()
        if first:
            return first
    return ""


def music_id_of(url: object) -> str:
    """
    ID ổn định của 1 bản nhạc, suy từ tên file trong URL.

    Cùng một bản nhạc được phục vụ từ NHIỀU host CDN khác nhau — đã đo trên dữ
    liệu Douyin thật: 28 URL -> 25 URL khác nhau nhưng chỉ 20 bản nhạc (thấy 5
    host: lf3-/lf9-/lf26-music-east, sf6-/sf11-cdn-tos). Gom theo URL nguyên vẹn
    sẽ đếm thiếu số lần dùng lại. Tên file thì giữ nguyên giữa các host.

    Chuỗi không phải URL (không có "/") thì trả lại chính nó — giữ cho dữ liệu
    tổng hợp trong test dùng được.
    """
    if url is None or pd.isna(url):
        return ""
    s = str(url).strip()
    if not s:
        return ""
    tail = urlparse(s).path.rsplit("/", 1)[-1] if "/" in s else s
    for ext in _MEDIA_EXTS:
        if tail.lower().endswith(ext):
            tail = tail[: -len(ext)]
            break
    return tail or s


_HASHTAG_RE = re.compile(r"#([^\s#，,。]+)")


def split_hashtags(df: pd.DataFrame) -> pd.Series:
    """
    Danh sách hashtag của từng dòng.

    XHS có `tag_list` đã tách sẵn (nền tảng duy nhất). Còn lại phải tự bóc `#x`
    từ title+desc.
    """
    if "tag_list" in df.columns:
        tags = df["tag_list"].fillna("").astype(str)
        if tags.str.strip().any():
            return tags.map(lambda s: [t.strip() for t in s.split(",") if t.strip()])
    parts = []
    for col in ("title", "desc", "content", "title_text", "body_text"):
        if col in df.columns:
            parts.append(df[col].fillna("").astype(str))
            break
    if not parts:
        return pd.Series([[] for _ in range(len(df))], index=df.index, dtype="object")
    return parts[0].map(lambda s: _HASHTAG_RE.findall(s))


def add_canonical(df: pd.DataFrame, platform: str = "") -> pd.DataFrame:
    """
    Thêm cột canonical (`platform`, `post_id`, `m_*`, `cover_url_c`...).

    CHỈ THÊM cột — không rename, không xoá — nên mọi lệnh analyzer và test cũ
    vẫn thấy nguyên dữ liệu như trước.

    Args:
        df: DataFrame thô đọc từ file MediaCrawler.
        platform: mã nền tảng; để trống thì tự suy từ cột đặc trưng.
    """
    df = df.copy()
    code = resolve(platform) or sniff_platform_from_columns(df)
    if code:
        df["platform"] = code
        df["platform_label"] = PLATFORM_LABELS.get(code, code)

    mapping = PLATFORM_COLUMN_MAP.get(code, {})
    for canon, src in mapping.items():
        if src in df.columns and canon not in df.columns:
            df[canon] = df[src]

    # Cover: gộp mọi biến thể (kể cả image_list của XHS) về 1 cột
    if len(df) and "cover_url_c" not in df.columns:
        cover = df.apply(cover_of_row, axis=1)
        if cover.str.strip().any():
            df["cover_url_c"] = cover

    # Like của BÌNH LUẬN: Weibo đặt tên `comment_like_count`, các nền tảng khác
    # dùng `like_count`. Gộp về `m_like` để Voice-of-Customer xếp hạng được.
    if "m_like" not in df.columns:
        for alias in COMMENT_LIKE_ALIASES:
            if alias in df.columns:
                df["m_like"] = df[alias]
                break

    if "nickname" not in df.columns and "user_nickname" in df.columns:
        df["nickname"] = df["user_nickname"]

    return df


def dedupe_posts(df: pd.DataFrame, *, verbose: bool = True) -> pd.DataFrame:
    """
    Bỏ các dòng trùng bài (cùng `post_id` trong cùng nền tảng).

    Dữ liệu xuất ra THỰC TẾ có dòng trùng — đã đo:
        xhs      40 dòng,  8 trùng note_id   (phồng 20%)
        bilibili 39 dòng, 10 trùng video_id  (phồng 26%)
        douyin   28 dòng,  8 trùng aweme_id  (phồng 29%)
    Nghĩa là trước khi có hàm này, MỌI chỉ số của MỌI báo cáo đang phồng 20-29%.

    Không giải được `post_id` (hoặc cột toàn rỗng) thì trả nguyên df — giữ cho
    dữ liệu tổng hợp không có cột id vẫn dùng được.
    """
    if "post_id" not in df.columns or df.empty:
        return df
    ids = df["post_id"]
    if ids.isna().all() or not ids.astype(str).str.strip().any():
        return df

    keys = ["post_id"]
    if "platform" in df.columns:
        keys.insert(0, "platform")
    before = len(df)
    out = df.drop_duplicates(subset=keys, keep="first")
    removed = before - len(out)
    if removed and verbose:
        print(f"[!] Bỏ {removed} dòng trùng post_id ({before} -> {len(out)})")
    return out.reset_index(drop=True)
