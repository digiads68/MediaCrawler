# -*- coding: utf-8 -*-
"""
Nhận diện & chuẩn bị link media của 7 nền tảng (nguồn sự thật duy nhất).

Dùng bởi:
  - api/routers/kit.py  -> endpoint proxy tải media (whitelist chống SSRF)
  - kit/report/html_report.py -> quyết định ô nào là link "xem trang" vs "tải file"

Vì sao cần proxy tải: CDN của các nền tảng trả `Content-Type: video/mp4` nhưng
KHÔNG kèm `Content-Disposition: attachment`, nên bấm link trong HTML thì trình
duyệt phát inline chứ không tải về; thuộc tính `download` của thẻ <a> lại bị bỏ
qua khi link khác origin. Ngoài ra CDN Bilibili đòi đúng `Referer` mới trả file.
Proxy giải quyết cả hai: gắn Referer đúng nền tảng + ép header attachment.
"""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

# Host CDN thuần media — mọi URL trên các host này là file media trực tiếp
# (không phải trang xem). Khớp theo hậu tố domain.
CDN_HOST_SUFFIXES: tuple[str, ...] = (
    # Douyin / ByteDance
    "douyinvod.com", "douyinpic.com", "douyinstatic.com", "zjcdn.com",
    "bytecdn.com", "byteimg.com", "pstatp.com", "ixigua.com", "bdxiguavod.com",
    "ibyteimg.com",
    # Xiaohongshu / rednote
    "xhscdn.com", "rednotecdn.com",
    # Bilibili
    "bilivideo.com", "bilivideo.cn", "hdslb.com", "akamaized.net",
    # Kuaishou
    "kwimgs.com", "yximgs.com", "kwaicdn.com",
    # Weibo
    "sinaimg.cn", "weibocdn.com", "miaopai.com",
    # Zhihu
    "zhimg.com",
    # Tieba / Baidu
    "bdstatic.com", "hiphotos.baidu.com", "baidupcs.com",
)

# Host trang xem (không tải trực tiếp), nhưng vẫn cho phép qua proxy vì một số
# endpoint trên đó thực chất trả file (vd Douyin /aweme/v1/play/).
PAGE_HOST_SUFFIXES: tuple[str, ...] = (
    "douyin.com", "xiaohongshu.com", "rednote.com", "bilibili.com",
    "kuaishou.com", "weibo.com", "weibo.cn", "zhihu.com", "tieba.baidu.com",
)

# Đường dẫn trên host trang xem nhưng trả về file media
_MEDIA_PATH_HINTS: tuple[str, ...] = (
    "/aweme/v1/play",          # Douyin: wrapper tự ký lại link CDN mỗi lần gọi
    "/aweme/v1/playwm",
)

_MEDIA_EXT: tuple[str, ...] = (
    ".mp4", ".m4v", ".flv", ".webm", ".mov", ".ts",
    ".m4a", ".mp3", ".aac", ".wav",
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".heic",
)

# Referer theo nền tảng — CDN Bilibili/Douyin chặn request thiếu Referer đúng
_REFERER_MAP: tuple[tuple[tuple[str, ...], str], ...] = (
    (("bilivideo.com", "bilivideo.cn", "hdslb.com", "bilibili.com"),
     "https://www.bilibili.com/"),
    (("douyinvod.com", "douyinpic.com", "douyinstatic.com", "zjcdn.com",
      "douyin.com", "bytecdn.com", "byteimg.com", "ixigua.com"),
     "https://www.douyin.com/"),
    (("xhscdn.com", "xiaohongshu.com"), "https://www.xiaohongshu.com/"),
    (("rednotecdn.com", "rednote.com"), "https://www.rednote.com/"),
    (("kwimgs.com", "yximgs.com", "kwaicdn.com", "kuaishou.com"),
     "https://www.kuaishou.com/"),
    (("sinaimg.cn", "weibocdn.com", "weibo.com", "weibo.cn"),
     "https://weibo.com/"),
    (("zhimg.com", "zhihu.com"), "https://www.zhihu.com/"),
    (("bdstatic.com", "baidu.com"), "https://tieba.baidu.com/"),
)

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36")

_SAFE_NAME = re.compile(r"[^\w.\-]+", re.UNICODE)
_DOT_RUN = re.compile(r"\.{2,}")


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _host_matches(host: str, suffixes: tuple[str, ...]) -> bool:
    """Khớp hậu tố domain theo ranh giới nhãn (chặn kiểu evil-douyin.com)."""
    return any(host == s or host.endswith("." + s) for s in suffixes)


def is_direct_media(url: str) -> bool:
    """URL này là file media tải trực tiếp được (không phải trang xem)?"""
    if not url or not url.lower().startswith(("http://", "https://")):
        return False
    host = _host(url)
    if not host:
        return False
    if _host_matches(host, CDN_HOST_SUFFIXES):
        return True
    low = url.lower()
    if any(h in low for h in _MEDIA_PATH_HINTS):
        return True
    path = urlparse(url).path.lower()
    return path.endswith(_MEDIA_EXT)


def is_allowed_for_proxy(url: str) -> bool:
    """Chỉ cho proxy tải từ CDN/host nền tảng đã biết (chặn SSRF)."""
    if not url or not url.lower().startswith(("http://", "https://")):
        return False
    host = _host(url)
    if not host:
        return False
    return (_host_matches(host, CDN_HOST_SUFFIXES)
            or _host_matches(host, PAGE_HOST_SUFFIXES))


def referer_for(url: str) -> str | None:
    """Referer phù hợp để CDN chấp nhận request."""
    host = _host(url)
    for suffixes, referer in _REFERER_MAP:
        if _host_matches(host, suffixes):
            return referer
    return None


def guess_extension(url: str, content_type: str = "") -> str:
    """Đuôi file suy từ URL, fallback theo Content-Type."""
    path = urlparse(url).path.lower()
    for ext in _MEDIA_EXT:
        if path.endswith(ext):
            return ext
    ct = (content_type or "").split(";")[0].strip().lower()
    return {
        "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
        "video/x-flv": ".flv", "audio/mpeg": ".mp3", "audio/mp4": ".m4a",
        "audio/aac": ".aac", "image/jpeg": ".jpg", "image/png": ".png",
        "image/webp": ".webp", "image/gif": ".gif",
    }.get(ct, ".mp4" if ct.startswith("video/") else "")


def safe_filename(url: str, requested: str | None = None,
                  content_type: str = "") -> str:
    """
    Tên file tải về an toàn (không path traversal, không ký tự lạ).

    Ưu tiên tên do client yêu cầu (đã làm sạch), fallback tên cuối trong URL,
    cuối cùng là "media". Luôn bảo đảm có đuôi file hợp lý.
    """
    ext = guess_extension(url, content_type)
    base = ""
    if requested:
        base = _SAFE_NAME.sub("_", unquote(requested))
    if not base.strip("._-"):
        tail = unquote(urlparse(url).path.rsplit("/", 1)[-1])
        base = _SAFE_NAME.sub("_", tail)
    # Gộp chuỗi dấu chấm liên tiếp (tránh sinh tên kiểu "ten..mp4") rồi cắt gọn
    base = _DOT_RUN.sub(".", base)[:120].strip("._-") or "media"
    if ext:
        # Bỏ đuôi cũ nếu có để không ra "anh.jpg.mp4", rồi gắn đuôi đúng
        for e in _MEDIA_EXT:
            if base.lower().endswith(e):
                base = base[: -len(e)]
                break
        base = (base.strip("._-") or "media") + ext
    return base
