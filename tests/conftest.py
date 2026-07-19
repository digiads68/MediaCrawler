# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/tests/conftest.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

"""
Pytest configuration and shared fixtures
"""

import pytest
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def project_root_path():
    """Return project root path"""
    return project_root


@pytest.fixture
def sample_xhs_note():
    """Sample Xiaohongshu note data for testing"""
    return {
        "note_id": "test_note_123",
        "type": "normal",
        "title": "Test Title",
        "desc": "This is a test description",
        "video_url": "",
        "time": 1700000000,
        "last_update_time": 1700000000,
        "user_id": "user_123",
        "nickname": "Test User",
        "avatar": "https://example.com/avatar.jpg",
        "liked_count": 100,
        "collected_count": 50,
        "comment_count": 25,
        "share_count": 10,
        "ip_location": "Shanghai",
        "image_list": "https://example.com/img1.jpg,https://example.com/img2.jpg",
        "tag_list": "test,programming,Python",
        "note_url": "https://www.xiaohongshu.com/explore/test_note_123",
        "source_keyword": "test keyword",
        "xsec_token": "test_token_123"
    }


@pytest.fixture
def sample_xhs_comment():
    """Sample Xiaohongshu comment data for testing"""
    return {
        "comment_id": "comment_123",
        "create_time": 1700000000,
        "ip_location": "Beijing",
        "note_id": "test_note_123",
        "content": "This is a test comment",
        "user_id": "user_456",
        "nickname": "Comment User",
        "avatar": "https://example.com/avatar2.jpg",
        "sub_comment_count": 5,
        "pictures": "",
        "parent_comment_id": 0,
        "like_count": 15
    }


@pytest.fixture
def synthetic_search_df():
    """DataFrame synthetic giống output MediaCrawler --type search (DigiAds Kit).

    Đặc điểm mô phỏng dữ liệu thật: title/desc tiếng Trung, count dạng Text,
    create_time epoch giây, creator_hash đã ẩn danh, trải 8 tuần cho seasonal.
    """
    import pandas as pd

    base_ts = 1_762_000_000  # 2025-11 (epoch giây)
    week = 7 * 24 * 3600
    rows = []
    # 3 creator × 6 video, 2 keyword, format đa dạng, engagement tăng dần cho c_a
    titles = ["7天前后对比太惊人", "真实测评这款精华", "开箱新品好物",
              "教你三步护肤教程", "翻车经历分享故事", "当你熬夜后的皮肤POV"]
    for ci, creator in enumerate(["c_a", "c_b", "c_c"]):
        for vi in range(6):
            growth = (vi + 1) if creator == "c_a" else 1
            rows.append({
                "title": titles[vi],
                "desc": "买一送一 限时秒杀 ¥99" if vi % 3 == 0 else "日常分享",
                "liked_count": str(100 * growth + ci * 10),
                "comment_count": f"{10 * growth}",
                "share_count": str(5 * growth),
                "collected_count": f"{30 * growth}",
                "create_time": base_ts + vi * week + ci * 3600,
                "source_keyword": "护肤" if ci < 2 else "精华",
                "creator_hash": creator,
                "nickname": f"用户***{ci}",
                "music_download_url": "bgm_trend_1" if vi % 2 == 0 else "",
                "aweme_url": f"https://v.douyin.com/{creator}_{vi}",
            })
    return pd.DataFrame(rows)


@pytest.fixture
def synthetic_comment_df():
    """DataFrame synthetic giống output comment MediaCrawler (CS2)."""
    import pandas as pd

    return pd.DataFrame({
        "content": ["用了一周真的有效果", "价格有点贵但值得", "求链接！！",
                    "用了一周真的有效果",     # trùng — phải dedupe
                    "😀😀😀",                  # toàn emoji — phải lọc
                    "ab",                      # quá ngắn — phải lọc
                    "客服态度很好物流也快"],
        "like_count": [50, 30, 10, 50, 99, 5, 8],
        "sub_comment_count": [5, 2, 0, 5, 0, 0, 1],
    })


@pytest.fixture
def sample_xhs_creator():
    """Sample Xiaohongshu creator data for testing"""
    return {
        "user_id": "creator_123",
        "nickname": "Creator Name",
        "gender": "Female",
        "avatar": "https://example.com/creator_avatar.jpg",
        "desc": "This is the creator bio",
        "ip_location": "Guangzhou",
        "follows": 500,
        "fans": 10000,
        "interaction": 50000,
        "tag_list": '{"profession": "Designer", "interest": "Photography"}'
    }
