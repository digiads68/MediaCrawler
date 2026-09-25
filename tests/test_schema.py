# -*- coding: utf-8 -*-
"""
Test tầng chuẩn hoá cột 7 nền tảng (kit/enrich/schema.py).

Trọng tâm là các chỗ đã từng gây lỗi thật:
  - mã nền tảng không trùng tên thư mục dữ liệu (`dy` vs `data/douyin/`)
  - Bilibili ghi vào 2 thư mục (`bili` cho JSON, `bilibili` cho Excel)
  - cột chỉ số đặt tên khác nhau -> `eng_total` bị hụt
  - XHS không có cột cover (cover nằm trong `image_list`)
  - dữ liệu xuất ra có dòng trùng -> mọi báo cáo phồng số
  - cùng 1 bản nhạc phục vụ từ nhiều host CDN
"""

from __future__ import annotations

import pandas as pd
import pytest

from kit.enrich.normalize import normalize
from kit.enrich.schema import (add_canonical, code_from_path, cover_of_row,
                               dedupe_posts, dirs_for, infer_platform,
                               music_id_of, resolve, split_hashtags,
                               sniff_platform_from_columns)


class TestPlatformDirs:
    """Mã nền tảng <-> thư mục dữ liệu. Sai chỗ này thì MCP không thấy file."""

    @pytest.mark.parametrize("code,expect_dir", [
        ("dy", "douyin"), ("douyin", "douyin"),
        ("ks", "kuaishou"), ("wb", "weibo"),
        ("xhs", "xhs"), ("tieba", "tieba"), ("zhihu", "zhihu"),
    ])
    def test_dirs_for(self, code, expect_dir):
        assert expect_dir in dirs_for(code)

    def test_bilibili_co_hai_thu_muc(self):
        """Excel -> data/bilibili/, JSON -> data/bili/ — phải nhận cả hai."""
        assert set(dirs_for("bili")) == {"bilibili", "bili"}
        assert set(dirs_for("bilibili")) == {"bilibili", "bili"}

    def test_resolve_alias(self):
        assert resolve("Xiaohongshu") == "xhs"
        assert resolve("RedNote") == "xhs"
        assert resolve("  DOUYIN ") == "dy"
        assert resolve("khong-biet") == "khong-biet"

    @pytest.mark.parametrize("path,code", [
        ("data/douyin/douyin_search_1.xlsx", "dy"),
        ("data/bili/json/search_contents_x.json", "bili"),
        ("data/bilibili/bilibili_search_x.xlsx", "bili"),
        ("data/xhs/xhs_search_x.xlsx", "xhs"),
        ("data/weibo/json/search_contents_x.json", "wb"),
        # Không có thư mục nền tảng -> suy từ tiền tố tên file
        ("/tmp/douyin_search_9.xlsx", "dy"),
        ("/tmp/khong-ro.xlsx", ""),
    ])
    def test_code_from_path(self, path, code):
        assert code_from_path(path) == code

    def test_sniff_tu_cot_dac_trung(self):
        assert sniff_platform_from_columns(pd.DataFrame({"xsec_token": ["a"]})) == "xhs"
        assert sniff_platform_from_columns(pd.DataFrame({"aweme_id": ["a"]})) == "dy"
        assert sniff_platform_from_columns(pd.DataFrame({"video_danmaku": [1]})) == "bili"
        assert sniff_platform_from_columns(pd.DataFrame({"voteup_count": [1]})) == "zhihu"
        assert sniff_platform_from_columns(pd.DataFrame({"abc": [1]})) == ""

    def test_infer_uu_tien_duong_dan_roi_moi_den_cot(self):
        df = pd.DataFrame({"aweme_id": ["a"]})
        assert infer_platform("data/xhs/x.xlsx", df) == "xhs"   # path thắng
        assert infer_platform("/tmp/la.xlsx", df) == "dy"       # fallback cột


class TestCanonical:
    """Map cột về tên chung — thiếu chỗ này thì eng_total sai trên 3 nền tảng."""

    def test_bilibili_gom_du_chi_so(self):
        """Bilibili đặt tên khác hoàn toàn: favorite/share/comment."""
        df = pd.DataFrame({
            "video_id": ["v1"], "title": ["t"], "desc": ["d"],
            "liked_count": [472430], "video_favorite_count": [744374],
            "video_share_count": [91625], "video_comment": [320316],
            "video_play_count": [18138011],
        })
        d = normalize(add_canonical(df, "bili"))
        assert d["m_save"].iloc[0] == 744374
        assert d["m_view"].iloc[0] == 18138011
        # eng_total phải cộng đủ 4 chỉ số, không chỉ like
        assert d["eng_total"].iloc[0] == 472430 + 744374 + 91625 + 320316
        assert d["save_rate"].iloc[0] > 0

    def test_weibo_ten_cot_so_nhieu(self):
        df = pd.DataFrame({"note_id": ["n1"], "content": ["c"],
                           "liked_count": [10], "comments_count": [4],
                           "shared_count": [2]})
        d = normalize(add_canonical(df, "wb"))
        assert d["m_comment"].iloc[0] == 4
        assert d["m_share"].iloc[0] == 2
        assert d["eng_total"].iloc[0] == 16

    def test_kuaishou_thieu_chi_so_thi_de_NaN_khong_phai_0(self):
        """
        Kuaishou không có comment/share/save. Phải VẮNG cột (NaN) chứ không được
        điền 0 — nếu điền 0 thì khi so sánh chéo nền tảng sẽ dìm Kuaishou.
        """
        df = pd.DataFrame({"video_id": ["v"], "title": ["t"],
                           "liked_count": [100], "viewd_count": [5000]})
        d = add_canonical(df, "ks")
        assert d["m_view"].iloc[0] == 5000
        assert "m_comment" not in d.columns
        assert "m_save" not in d.columns

    def test_khong_ghi_de_cot_goc(self):
        """Chỉ THÊM cột — analyzer/test cũ vẫn phải thấy nguyên dữ liệu."""
        df = pd.DataFrame({"aweme_id": ["a1"], "title": ["t"],
                           "cover_url": ["http://c/x.jpg"], "liked_count": [5]})
        d = add_canonical(df, "dy")
        assert d["cover_url"].iloc[0] == "http://c/x.jpg"   # nguyên vẹn
        assert set(df.columns) <= set(d.columns)

    def test_platform_duoc_bom_vao(self):
        """Dữ liệu thô không nền tảng nào có cột `platform`."""
        d = add_canonical(pd.DataFrame({"note_id": ["n"], "title": ["t"]}), "xhs")
        assert d["platform"].iloc[0] == "xhs"
        assert d["platform_label"].iloc[0] == "Xiaohongshu"

    def test_nickname_tu_user_nickname(self):
        d = add_canonical(pd.DataFrame({"note_id": ["n"], "title": ["t"],
                                        "user_nickname": ["a***b"]}), "tieba")
        assert d["nickname"].iloc[0] == "a***b"

    def test_like_cua_binh_luan_weibo_duoc_gop(self):
        """Weibo dùng `comment_like_count`, nền tảng khác dùng `like_count`."""
        d = add_canonical(pd.DataFrame({"comment_id": ["c"], "content": ["x"],
                                        "comment_like_count": [7]}), "")
        assert d["m_like"].iloc[0] == 7


class TestCover:
    """XHS không có cột cover -> báo cáo XHS từng không hiện ảnh nào."""

    def test_xhs_lay_anh_dau_trong_image_list(self):
        r = pd.Series({"image_list": "http://a/1.jpg,http://a/2.jpg"})
        assert cover_of_row(r) == "http://a/1.jpg"

    def test_uu_tien_cot_cover_co_san(self):
        r = pd.Series({"cover_url": "http://c.jpg", "image_list": "http://i.jpg"})
        assert cover_of_row(r) == "http://c.jpg"

    def test_bilibili_kuaishou_dung_video_cover_url(self):
        assert cover_of_row(pd.Series({"video_cover_url": "http://v.jpg"})) == "http://v.jpg"

    def test_khong_co_gi_tra_rong(self):
        assert cover_of_row(pd.Series({"title": "t"})) == ""
        assert cover_of_row(pd.Series({"image_list": None})) == ""


class TestMusicId:
    """Cùng 1 bản nhạc trên nhiều host CDN — gom theo URL sẽ đếm thiếu."""

    def test_gom_duoc_qua_nhieu_host(self):
        base = "/obj/ies-music-hj/7559775982211615547.mp3"
        hosts = ["lf3-music-east", "lf9-music-east", "lf26-music-east",
                 "sf6-cdn-tos", "sf11-cdn-tos"]
        ids = {music_id_of(f"https://{h}.douyinstatic.com{base}") for h in hosts}
        assert ids == {"7559775982211615547"}

    def test_chuoi_khong_phai_url_giu_nguyen(self):
        """Bảo vệ tests/test_analyzer.py — fixture dùng 'bgm_trend_1'."""
        assert music_id_of("bgm_trend_1") == "bgm_trend_1"

    def test_url_khong_co_duoi_file(self):
        u = "https://lf3-music.douyinstatic.com/obj/tos-cn-ve-2774/e1f9abc"
        assert music_id_of(u) == "e1f9abc"

    def test_rong(self):
        assert music_id_of(None) == ""
        assert music_id_of("") == ""


class TestDedupe:
    """Dữ liệu thật có dòng trùng: xhs 20%, bilibili 26%, douyin 29%."""

    def test_bo_dong_trung_theo_post_id(self, capsys):
        df = add_canonical(pd.DataFrame({
            "note_id": ["a", "b", "a", "c", "b"],
            "title": list("vwxyz"), "liked_count": [1, 2, 3, 4, 5],
        }), "xhs")
        out = dedupe_posts(df)
        assert len(out) == 3
        assert out["post_id"].tolist() == ["a", "b", "c"]
        assert "Bỏ 2 dòng trùng" in capsys.readouterr().out

    def test_giu_dong_dau_tien(self):
        df = add_canonical(pd.DataFrame({"note_id": ["a", "a"], "title": ["x", "y"],
                                         "liked_count": [1, 2]}), "xhs")
        assert dedupe_posts(df, verbose=False)["title"].tolist() == ["x"]

    def test_khong_nham_bai_cung_id_khac_nen_tang(self):
        df = pd.concat([
            add_canonical(pd.DataFrame({"note_id": ["1"], "title": ["a"]}), "xhs"),
            add_canonical(pd.DataFrame({"aweme_id": ["1"], "title": ["b"]}), "dy"),
        ], ignore_index=True)
        assert len(dedupe_posts(df, verbose=False)) == 2

    def test_no_op_khi_khong_co_post_id(self):
        """Bảo vệ tests/test_analyzer.py:155 — fixture không có cột id."""
        df = pd.DataFrame({"title": ["a", "a"], "liked_count": [1, 1]})
        assert len(dedupe_posts(df)) == 2

    def test_no_op_khi_post_id_toan_rong(self):
        df = pd.DataFrame({"post_id": [None, None], "title": ["a", "b"]})
        assert len(dedupe_posts(df)) == 2

    def test_df_rong(self):
        assert dedupe_posts(pd.DataFrame()).empty


class TestHashtags:
    def test_xhs_dung_tag_list_tach_san(self):
        df = pd.DataFrame({"tag_list": ["护肤,精华", ""], "title": ["a", "b"]})
        assert split_hashtags(df).tolist() == [["护肤", "精华"], []]

    def test_nen_tang_khac_boc_tu_title(self):
        df = pd.DataFrame({"title": ["hay #副业 #编程", "khong co tag"]})
        assert split_hashtags(df).tolist() == [["副业", "编程"], []]

    def test_khong_co_cot_van_ban(self):
        assert split_hashtags(pd.DataFrame({"x": [1, 2]})).tolist() == [[], []]
