# -*- coding: utf-8 -*-
"""
Test nhận diện & chuẩn bị link media (kit/media_urls.py).

Trọng tâm: phân loại đúng "trang xem" vs "file tải trực tiếp" (khác nhau theo
nền tảng), và whitelist chặn SSRF không bị lách.
"""

from __future__ import annotations

import pytest

from kit.media_urls import (guess_extension, is_allowed_for_proxy, is_direct_media,
                            referer_for, safe_filename)

# (url, là file media trực tiếp?) — dữ liệu tổng hợp theo đúng dạng thật của từng nền tảng
DIRECT_CASES = [
    # Douyin: wrapper /aweme/v1/play/ tự ký lại link CDN mỗi lần gọi -> coi là file
    ("https://www.douyin.com/aweme/v1/play/?video_id=v0300fg&sign=abc", True),
    ("https://www.douyin.com/video/7559775923579407631", False),      # trang xem
    ("https://lf3-music-east.douyinstatic.com/obj/ies-music-hj/755", True),  # nhạc, không đuôi
    # Xiaohongshu/rednote: video_url LÀ mp4 trên CDN, note_url là trang xem
    ("http://sns-v11.rednotecdn.com/stream/1/110/259/01ea.mp4", True),
    ("http://sns-web-i10.rednotecdn.com/2026/abc/1040g0083!nd_dft_wl", True),  # ảnh, không đuôi
    ("https://www.xiaohongshu.com/explore/67514a94", False),
    ("https://www.rednote.com/explore/67514a94", False),
    # Bilibili: ngược với xhs — video_url là TRANG xem, file nằm trên *.bilivideo.com
    ("https://www.bilibili.com/video/av123", False),
    ("https://cn-hbxy-cm-01-06.bilivideo.com/upgcxcode/xx.m4s", True),
]


@pytest.mark.parametrize("url,expected", DIRECT_CASES)
def test_is_direct_media(url, expected):
    assert is_direct_media(url) is expected


# Whitelist proxy: chỉ CDN/host của 7 nền tảng
ALLOWED = [
    "https://www.douyin.com/aweme/v1/play/?video_id=v03",
    "http://sns-v11.rednotecdn.com/stream/a.mp4",
    "https://x.xhscdn.com/stream/a.mp4",
    "https://cn-1.bilivideo.com/upgcxcode/xx.m4s",
    "https://tieba.baidu.com/p/123",
]
BLOCKED = [
    "https://evil-douyin.com/x.mp4",          # domain giả mạo, không phải subdomain
    "https://douyin.com.evil.net/x.mp4",      # hậu tố lừa
    "http://127.0.0.1:8080/docs",             # SSRF nội bộ
    "http://localhost/admin",
    "http://169.254.169.254/latest/meta-data",  # metadata cloud
    "file:///C:/Windows/win.ini",             # scheme không phải http(s)
    "ftp://sns-v11.rednotecdn.com/a.mp4",
    "",
]


@pytest.mark.parametrize("url", ALLOWED)
def test_proxy_allows_platform_cdn(url):
    assert is_allowed_for_proxy(url) is True


@pytest.mark.parametrize("url", BLOCKED)
def test_proxy_blocks_non_platform(url):
    assert is_allowed_for_proxy(url) is False


def test_referer_theo_nen_tang():
    """CDN Bilibili/Douyin chặn request thiếu Referer đúng."""
    assert referer_for("https://cn-1.bilivideo.com/x.m4s") == "https://www.bilibili.com/"
    assert referer_for("https://v11-o.douyinvod.com/x.mp4") == "https://www.douyin.com/"
    assert referer_for("http://sns-v11.rednotecdn.com/a.mp4") == "https://www.rednote.com/"
    assert referer_for("http://x.xhscdn.com/a.mp4") == "https://www.xiaohongshu.com/"
    assert referer_for("https://unknown-host.example/a.mp4") is None


def test_guess_extension_tu_url_roi_fallback_content_type():
    assert guess_extension("http://a.cdn/x.mp4") == ".mp4"
    # Link không đuôi -> suy từ Content-Type
    assert guess_extension("https://www.douyin.com/aweme/v1/play/?id=1",
                           "video/mp4") == ".mp4"
    assert guess_extension("http://a.cdn/obj/abc", "audio/mpeg") == ".mp3"
    assert guess_extension("http://a.cdn/obj/abc", "image/jpeg") == ".jpg"


class TestSafeFilename:
    """Tên file tải về: không path traversal, không đuôi lặp, giữ được tiếng Việt/Trung."""

    def test_chan_path_traversal(self):
        name = safe_filename("http://a.cdn/x.mp4", "../../etc/passwd", "video/mp4")
        assert "/" not in name and "\\" not in name
        assert ".." not in name
        assert name.endswith(".mp4")

    def test_giu_unicode(self):
        assert safe_filename("http://a.cdn/x.mp4", "05_视频标题", "video/mp4") == "05_视频标题.mp4"
        assert safe_filename("http://a.cdn/x.mp4", "Bún bò Huế", "video/mp4") == "Bún_bò_Huế.mp4"

    def test_khong_lap_duoi(self):
        assert safe_filename("http://a.cdn/x.mp4", "video.mp4", "video/mp4") == "video.mp4"
        # Đuôi cũ khác đuôi thật -> thay, không cộng dồn
        assert safe_filename("http://a.cdn/x.mp4", "anh.jpg", "video/mp4") == "anh.mp4"

    def test_fallback_ten_tu_url_roi_den_media(self):
        assert safe_filename("http://a.cdn/path/clip.mp4", None, "video/mp4") == "clip.mp4"
        # Không suy được gì -> "media" + đuôi
        assert safe_filename("http://a.cdn/", "///", "video/mp4") == "media.mp4"
