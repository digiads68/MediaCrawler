# -*- coding: utf-8 -*-
"""
Test bộ luật nhận diện FORMAT (kit/enrich/normalize.py).

Vì sao cần test riêng: trước khi mở rộng luật, tỉ lệ bài rơi vào "khác" đo trên
dữ liệu thật là xhs 85% / douyin 75% / bilibili 56% -> phân loại gần như vô dụng
và Format Playbook (đạo diễn) sẽ không có gì để nói. File này BIẾN MỤC TIÊU
"< 40% khác" THÀNH RÀNG BUỘC CI, và ghim các nhãn cũ để mở rộng luật về sau
không âm thầm đổi kết quả.

Title dưới đây copy nguyên văn từ dữ liệu công khai đã cào trong `data/`.
"""

from __future__ import annotations

import pandas as pd
import pytest

from kit.enrich.normalize import (OTHER_FORMAT, tag_format, tag_format_stats,
                                  tag_one_format)

# --- Title thật, theo nền tảng (đã cắt gọn) ---------------------------------

XHS_TITLES = [
    "一人搞钱攻略💰26岁靠敲代码，月赚167万",
    "程序员接私活，一小时赚300，放假也不敢休息",
    "有什么副业可以增加收入？？？？求",
    "普通程序员，每天三份工作，副业已经超过主业",
    "程序员接单汇总｜收益马上突破10w啦！",
    "普通人都能做的python搞💰思路",
    "97年程序员，周末做副业，收入即将超过主业",
    "python代做深度学习机器学习接单图像处理",
    "加入我们 | 有vibe coding经验的人速来！",
    "可落地一人公司项目，AI + 鸿蒙应用",
    "打工人做副业都用什么app？",
]

DOUYIN_TITLES = [
    "4大收入神器，提前为失业做准备",
    "学爬虫就要去接单，一期视频告诉你Python副业兼职变现的全流程",
    "程序员副业干货分享，附渠道+教程",
    "别再被割韭菜了，这些副业根本不可行",
]

BILI_TITLES = [
    "不上班怎么赚钱？探访月入5k-40w元自由职业者，差别有多大？",
    "哪种副业真能挣到钱？9种副业真实测试，第5项结果令人意外！",
    "99%程序员做副业，都是浪费时间",
    "【程序员晚枫】学编程、学Python接单？根本不可行，别再被割韭菜了！",
    "不用上班的赚钱方法实力排行",
    "低成本单人切人可长期发展副业方向大盘点",
    "【全748集】目前B站最全最细的Python零基础全套教程，2026最新版",
    "采访4位靠Python做副业挣钱的人!甚至有高中生！",
    "【亲身经历】30+程序员折腾的11年，第一章：接单！",
    "爆肝2个月！90分钟拆解AI漫剧全流程（含选题+剧本+分镜+视频+配音+剪辑+变现）",
]

# Ngưỡng tối đa cho tỉ lệ "khác" (mục tiêu kế hoạch: < 40%)
MAX_OTHER_PCT = 0.40


def _other_pct(titles: list[str]) -> float:
    df = tag_format(pd.DataFrame({"title": titles, "desc": [""] * len(titles)}))
    return tag_format_stats(df)["other_pct"]


@pytest.mark.parametrize("name,titles", [
    ("xhs", XHS_TITLES), ("douyin", DOUYIN_TITLES), ("bilibili", BILI_TITLES),
])
def test_ti_le_khac_duoi_nguong(name, titles):
    """Ghim mục tiêu đo được — nới luật đến mức vô nghĩa sẽ bị test này chặn."""
    pct = _other_pct(titles)
    assert pct <= MAX_OTHER_PCT, f"{name}: {pct:.0%} bài không nhận ra format"


# --- Ghim nhãn cho từng title (đọc được, sửa được khi đổi luật) -------------

@pytest.mark.parametrize("title,expect", [
    # Nhóm mới: kể chuyện thu nhập/kết quả
    ("一人搞钱攻略💰26岁靠敲代码，月赚167万", "case/战绩"),
    ("4大收入神器，提前为失业做准备", "case/战绩"),
    # Nhóm mới: can/cảnh báo
    ("99%程序员做副业，都是浪费时间", "warning/劝退"),
    ("别再被割韭菜了，这些副业根本不可行", "warning/劝退"),
    # Nhóm mới: tài nguyên
    ("程序员副业干货分享，附渠道+教程", "resource/干货"),
    # Nhóm mới: tuyển người
    ("加入我们 | 有vibe coding经验的人速来！", "recruit/招募"),
    # Nhóm mới: hỏi đáp
    ("有什么副业可以增加收入？？？？求", "qna/问答"),
    # Nhóm cũ vẫn đúng
    ("不用上班的赚钱方法实力排行", "list/top"),
    ("低成本单人切人可长期发展副业方向大盘点", "list/top"),
    ("采访4位靠Python做副业挣钱的人!甚至有高中生！", "storytime"),
    ("【亲身经历】30+程序员折腾的11年，第一章：接单！", "storytime"),
    ("哪种副业真能挣到钱？9种副业真实测试，第5项结果令人意外！", "review/測評"),
])
def test_nhan_cua_title_that(title, expect):
    assert tag_one_format(title.lower()) == expect


class TestBaoVeNhanCu:
    """
    Các title trong test/fixture hiện có PHẢI giữ nguyên nhãn.

    Đây là hợp đồng với `tests/test_enrich.py:60` và fixture
    `synthetic_search_df` — mở rộng luật mà làm lệch chỗ này là hồi quy.
    """

    @pytest.mark.parametrize("text,expect", [
        # 4 mẫu của tests/test_enrich.py (title + desc đã ghép)
        ("7天变化太大了 前后对比", "before-after"),
        ("真实测评这款精华 亲测有效", "review/測評"),
        ("开箱新品 到货啦", "unboxing"),
        ("随便聊聊 ", OTHER_FORMAT),
        # 6 title của fixture synthetic_search_df
        ("7天前后对比太惊人 买一送一 限时秒杀 ¥99", "before-after"),
        ("真实测评这款精华 日常分享", "review/測評"),
        ("开箱新品好物 日常分享", "unboxing"),
        ("教你三步护肤教程 买一送一 限时秒杀 ¥99", "tutorial"),
        ("翻车经历分享故事 日常分享", "storytime"),
        ("当你熬夜后的皮肤pov 日常分享", "pov/skit"),
    ])
    def test_giu_nhan(self, text, expect):
        assert tag_one_format(text) == expect

    def test_ba_buoc_khong_bi_nham_thanh_danh_sach(self):
        """
        "三步" là CÁC BƯỚC (tutorial), không phải danh sách.

        Luật `list/top` cố ý chỉ nhận chữ số ASCII + lượng từ đồ vật, và không
        bao giờ nhận 步 — nếu nhận thì "教你三步...教程" sẽ ra `list/top`.
        """
        assert tag_one_format("教你三步护肤教程") == "tutorial"
        assert tag_one_format("3步搞定护肤") == "tutorial"
        # nhưng có số + lượng từ đồ vật thì đúng là danh sách
        assert tag_one_format("8个程序员兼职接单平台") == "list/top"


class TestScoring:
    """Chấm điểm thay cho 'khớp đầu tiên thắng'."""

    def test_nhieu_luat_khop_thi_luat_manh_hon_thang(self):
        # "前后对比" + "变化" = 3 điểm before-after, chỉ 1 điểm cho review
        assert tag_one_format("7天前后对比变化 真实") == "before-after"

    def test_khong_khop_gi_ra_khac(self):
        assert tag_one_format("hôm nay trời đẹp") == OTHER_FORMAT
        assert tag_one_format("") == OTHER_FORMAT
        assert tag_one_format("   ") == OTHER_FORMAT


class TestStats:
    def test_thong_ke_day_du(self):
        df = tag_format(pd.DataFrame({
            "title": ["开箱新品", "随便nói", "月赚100万"],
            "desc": ["", "", ""],
            "eng_total": [10, 500, 20],
        }))
        st = tag_format_stats(df)
        assert st["other_pct"] == pytest.approx(1 / 3)
        assert st["n_formats"] == 2          # unboxing + case, không tính "khác"
        assert st["per_format"]["unboxing"] == 1
        # Title "khác" xếp theo engagement giảm dần -> làm backlog mở luật
        assert st["top_other_titles"] == ["随便nói"]

    def test_df_rong(self):
        st = tag_format_stats(pd.DataFrame())
        assert st["other_pct"] == 1.0 and st["n_formats"] == 0
