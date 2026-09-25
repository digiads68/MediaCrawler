# -*- coding: utf-8 -*-
"""
Test soi file dữ liệu -> dashboard nào chạy được (kit/analyzer/capabilities.py).

Mục đích của module này: WebUI chỉ bật dashboard mà dữ liệu thực sự đỡ được.
Nên test tập trung vào "khoá đúng cái đáng khoá, mở đúng cái đủ dữ liệu", và
điều kiện phải khớp với yêu cầu thật của analyzer.
"""

from __future__ import annotations

import pandas as pd
import pytest

from kit.analyzer.capabilities import inspect_data_file

# 6 tuần, 2 từ khoá, 1 creator đủ 5+ video -> đỡ được gần hết dashboard
WEEK_MS = 7 * 24 * 3600 * 1000
BASE_MS = 1_733_000_000_000


def _posts_rows(n: int = 12) -> list[dict]:
    rows = []
    for i in range(n):
        rows.append({
            "note_id": f"n{i}",
            "title": f"Bài {i} review sản phẩm 199k giảm giá",
            "desc": "mô tả có 299 元 và voucher",
            "liked_count": 100 + i * 10,
            "collected_count": 50 + i,
            "share_count": 10 + i,
            "comment_count": 5 + i,
            "creator_hash": "creator_a" if i < 6 else "creator_b",
            "nickname": "a***a" if i < 6 else "b***b",
            "source_keyword": "kw1" if i % 2 == 0 else "kw2",
            # xhs dùng cột `time` (ms) thay cho `create_time`
            "time": BASE_MS + (i % 6) * WEEK_MS,
        })
    return rows


def _write_xlsx(rows: list[dict], path) -> str:
    pd.DataFrame(rows).to_excel(path, index=False)
    return str(path)


@pytest.fixture
def posts_file(tmp_path):
    return _write_xlsx(_posts_rows(), tmp_path / "xhs_search_synthetic.xlsx")


@pytest.fixture
def comments_file(tmp_path):
    rows = [{"comment_id": f"c{i}", "content": f"Bình luận số {i} rất hữu ích",
             "like_count": 20 - i, "sub_comment_count": i}
            for i in range(10)]
    return _write_xlsx(rows, tmp_path / "xhs_comments_synthetic.xlsx")


def _caps(path) -> dict:
    return inspect_data_file(path)["capabilities"]


class TestFileBaiDang:
    def test_nhan_dien_la_posts(self, posts_file):
        r = inspect_data_file(posts_file)
        assert r["kind"] == "posts"
        assert r["rows"] == 12

    def test_mo_dashboard_du_dieu_kien(self, posts_file):
        caps = _caps(posts_file)
        for cmd in ("trend", "opportunity", "price", "angle", "seasonal", "sov", "koc"):
            assert caps[cmd]["supported"] is True, f"{cmd}: {caps[cmd]['reason']}"

    def test_khoa_insight_vi_khong_phai_file_comment(self, posts_file):
        cap = _caps(posts_file)["insight"]
        assert cap["supported"] is False
        assert "BÌNH LUẬN" in cap["reason"]

    def test_cot_time_cua_xhs_duoc_hieu_la_thoi_gian_dang(self, posts_file):
        """xhs xuất cột `time`, không phải `create_time` — vẫn phải mở được seasonal."""
        caps = _caps(posts_file)
        assert caps["seasonal"]["supported"] is True
        assert "tuần" in caps["seasonal"]["reason"]


class TestFileBinhLuan:
    def test_nhan_dien_la_comments(self, comments_file):
        assert inspect_data_file(comments_file)["kind"] == "comments"

    def test_chi_mo_insight(self, comments_file):
        caps = _caps(comments_file)
        assert caps["insight"]["supported"] is True
        # Không có chỉ số tương tác bài / từ khoá / thời gian -> phải khoá
        for cmd in ("trend", "koc", "opportunity", "seasonal", "sov", "angle"):
            assert caps[cmd]["supported"] is False, f"{cmd} lẽ ra phải khoá"

    def test_khong_crash_khi_thieu_title_desc(self, comments_file):
        """File comment không có title/desc — normalize từng nổ AttributeError ở đây."""
        r = inspect_data_file(comments_file)
        assert r["rows"] == 10


class TestThieuDuLieu:
    def test_thieu_thoi_gian_thi_khoa_seasonal_koc_sov(self, tmp_path):
        rows = [{k: v for k, v in r.items() if k != "time"} for r in _posts_rows()]
        caps = _caps(_write_xlsx(rows, tmp_path / "no_time.xlsx"))
        for cmd in ("seasonal", "koc", "sov"):
            assert caps[cmd]["supported"] is False
            assert "create_time" in caps[cmd]["reason"]
        # Nhưng trend/price vẫn chạy được vì không cần trục thời gian
        assert caps["trend"]["supported"] is True

    def test_mot_tu_khoa_thi_khoa_opportunity(self, tmp_path):
        rows = _posts_rows()
        for r in rows:
            r["source_keyword"] = "kw_duy_nhat"
        caps = _caps(_write_xlsx(rows, tmp_path / "one_kw.xlsx"))
        assert caps["opportunity"]["supported"] is False
        assert "1 từ khoá" in caps["opportunity"]["reason"]

    def test_tuong_tac_toan_bo_bang_0_thi_khoa_trend(self, tmp_path):
        rows = _posts_rows()
        for r in rows:
            for c in ("liked_count", "collected_count", "share_count", "comment_count"):
                r[c] = 0
        caps = _caps(_write_xlsx(rows, tmp_path / "zero_eng.xlsx"))
        assert caps["trend"]["supported"] is False

    def test_it_creator_du_video_thi_khoa_koc(self, tmp_path):
        rows = _posts_rows(4)  # mỗi creator < 5 video
        caps = _caps(_write_xlsx(rows, tmp_path / "few_videos.xlsx"))
        assert caps["koc"]["supported"] is False
        assert "5 video" in caps["koc"]["reason"]

    def test_dinh_dang_khong_ho_tro(self, tmp_path):
        p = tmp_path / "data.txt"
        p.write_text("khong phai bang", encoding="utf-8")
        with pytest.raises(ValueError, match="chưa hỗ trợ"):
            inspect_data_file(p)


def test_moi_dashboard_deu_co_ket_luan(posts_file):
    """Không được thiếu lệnh nào — WebUI dựa vào đây để render danh sách."""
    caps = _caps(posts_file)
    assert set(caps) == {"trend", "insight", "koc", "opportunity",
                         "seasonal", "price", "sov", "angle"}
    for cmd, cap in caps.items():
        assert isinstance(cap["supported"], bool)
        # Bị khoá thì buộc phải nói lý do để người dùng biết cách sửa
        if not cap["supported"]:
            assert cap["reason"].strip(), f"{cmd} khoá mà không có lý do"
