# -*- coding: utf-8 -*-
"""Test router /kit — TestClient, mock lớp nặng (analyzer/pipeline)."""

from __future__ import annotations

import json

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import kit as kit_router_mod


@pytest.fixture
def client() -> TestClient:
    """App tối giản chỉ mount router kit (không kéo cả api.main nặng)."""
    app = FastAPI()
    app.include_router(kit_router_mod.router)
    return TestClient(app)


@pytest.fixture
def project_files(tmp_path, monkeypatch):
    """Trỏ PROJECT_ROOT/REPORTS_DIR về thư mục tạm có sẵn dữ liệu synthetic."""
    monkeypatch.setattr(kit_router_mod, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(kit_router_mod, "REPORTS_DIR", tmp_path / "reports")
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "CS1_trend_top_posts.xlsx").write_bytes(b"PK\x03\x04demo")

    df = pd.DataFrame({
        "title": ["7天变化", "开箱"], "desc": ["前后", "到货"],
        "liked_count": ["100", "50"], "comment_count": ["5", "2"],
        "share_count": ["1", "0"], "collected_count": ["20", "3"],
        "create_time": [1767600000, 1767700000],
        "source_keyword": ["kw", "kw"],
    })
    df.to_excel(tmp_path / "search_kw.xlsx", index=False)

    angle = {"angle_id": "a1", "platform": "dy", "source_keyword": "kw",
             "hook": "h", "format": "review", "pain_or_desire": "x",
             "cta_observed": "", "sound_ref": "", "metrics": {}, "lang": "zh"}
    (tmp_path / "angles.jsonl").write_text(json.dumps(angle, ensure_ascii=False),
                                           encoding="utf-8")
    return tmp_path


def test_analyze_tra_ket_qua(client, project_files, monkeypatch):
    monkeypatch.chdir(project_files)  # reports/ của analyzer ghi vào tmp
    resp = client.post("/kit/analyze",
                       json={"command": "trend", "file": "search_kw.xlsx"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok" and body["rows"] == 2


def test_analyze_file_khong_ton_tai(client, project_files):
    resp = client.post("/kit/analyze",
                       json={"command": "trend", "file": "khong_co.xlsx"})
    assert resp.status_code == 404


def test_analyze_command_sai_bi_validate(client, project_files):
    resp = client.post("/kit/analyze",
                       json={"command": "hack", "file": "search_kw.xlsx"})
    assert resp.status_code == 422        # pydantic Literal chặn


def test_analyze_chan_path_traversal(client, project_files):
    resp = client.post("/kit/analyze",
                       json={"command": "trend", "file": "../../etc/passwd"})
    assert resp.status_code in (400, 404)


def test_sov_thieu_brand_map(client, project_files):
    resp = client.post("/kit/analyze",
                       json={"command": "sov", "file": "search_kw.xlsx"})
    assert resp.status_code == 400
    assert "brand_map" in resp.json()["detail"]


def test_reports_liet_ke(client, project_files):
    (project_files / "reports" / "trend_report.html").write_text("<h1>x</h1>",
                                                                 encoding="utf-8")
    resp = client.get("/kit/reports")
    assert resp.status_code == 200
    names = {r["name"] for r in resp.json()["reports"]}
    assert "CS1_trend_top_posts.xlsx" in names
    assert "trend_report.html" in names


def test_report_html_tra_inline(client, project_files):
    (project_files / "reports" / "trend_report.html").write_text("<h1>x</h1>",
                                                                 encoding="utf-8")
    resp = client.get("/kit/reports/trend_report.html")
    assert resp.status_code == 200
    # HTML phải inline (render), KHÔNG phải attachment (tải)
    assert "attachment" not in resp.headers.get("content-disposition", "")
    assert "text/html" in resp.headers.get("content-type", "")


def test_report_tai_file(client, project_files):
    resp = client.get("/kit/reports/CS1_trend_top_posts.xlsx")
    assert resp.status_code == 200
    assert resp.content.startswith(b"PK")
    # xlsx phải là attachment (tải về)
    assert "attachment" in resp.headers.get("content-disposition", "")


def test_report_khong_co(client, project_files):
    assert client.get("/kit/reports/khong_co.xlsx").status_code == 404


def test_report_chan_ten_file_ban(client, project_files):
    assert client.get("/kit/reports/..%2Fsecret.txt").status_code in (400, 404)


def test_angle_brief_provider_mock(client, project_files):
    resp = client.post("/kit/angle-brief",
                       json={"angle_jsonl": "angles.jsonl",
                             "product": "Serum kiềm dầu 199k",
                             "provider": "mock"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["briefs"][0]["language"] == "vi-VN"
    assert "a1" in body["briefs"][0]["source_angle_ids"]


def test_angle_brief_validate_product_ngan(client, project_files):
    resp = client.post("/kit/angle-brief",
                       json={"angle_jsonl": "angles.jsonl", "product": "x"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /kit/dashboard
# ---------------------------------------------------------------------------

@pytest.fixture
def dashboard_file(project_files):
    """File raw đúng chữ ký Douyin (search mode) trong PROJECT_ROOT tạm."""
    df = pd.DataFrame({
        "aweme_id": ["a1", "a2"],
        "title": ["4 招 kiếm tiền #副业", "教程 mới #AI"],
        "desc": ["", ""],
        "create_time": [1760000000, 1761000000],
        "nickname": ["a***a", "b***b"],
        "creator_hash": ["h1", "h2"],
        "liked_count": [1000, 2000], "collected_count": [500, 400],
        "comment_count": [50, 80], "share_count": [20, 30],
        "aweme_url": ["https://douyin.com/video/1", "https://douyin.com/video/2"],
        "cover_url": ["https://c/1.jpg", "https://c/2.jpg"],
        "video_download_url": ["https://dl/1.mp4", "https://dl/2.mp4"],
        "music_download_url": ["", ""],
        "source_keyword": ["kw", "kw"],
    })
    df.to_excel(project_files / "douyin_search_kw.xlsx", index=False)
    return project_files


def test_dashboard_auto_sinh_html(client, dashboard_file):
    resp = client.post("/kit/dashboard",
                       json={"files": ["douyin_search_kw.xlsx"],
                             "out": "reports/d.html"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok" and body["report"] == "d.html"
    html = (dashboard_file / "reports" / "d.html").read_text(encoding="utf-8")
    assert "SEARCH MODE" in html          # auto chọn đúng loại theo mode cào


def test_dashboard_profile_chi_dinh(client, dashboard_file):
    resp = client.post("/kit/dashboard",
                       json={"files": ["douyin_search_kw.xlsx"],
                             "profile": "creator", "out": "reports/c.html"})
    assert resp.status_code == 200
    html = (dashboard_file / "reports" / "c.html").read_text(encoding="utf-8")
    assert "CREATOR MODE" in html


def test_dashboard_all_tra_index(client, dashboard_file):
    resp = client.post("/kit/dashboard",
                       json={"files": ["douyin_search_kw.xlsx"],
                             "profile": "all", "out_dir": "reports"})
    assert resp.status_code == 200
    body = resp.json()
    assert "index_url" in body
    assert {"search", "overview", "index"} <= set(body["reports"])


def test_dashboard_profile_sai_bi_validate(client, dashboard_file):
    resp = client.post("/kit/dashboard",
                       json={"files": ["douyin_search_kw.xlsx"],
                             "profile": "khong-ton-tai"})
    assert resp.status_code == 422


def test_dashboard_file_khong_ton_tai(client, dashboard_file):
    resp = client.post("/kit/dashboard", json={"files": ["khong_co.xlsx"]})
    assert resp.status_code == 404


def test_dashboard_chan_path_traversal(client, dashboard_file):
    resp = client.post("/kit/dashboard",
                       json={"files": ["douyin_search_kw.xlsx"],
                             "out": "../escape.html"})
    assert resp.status_code == 400
