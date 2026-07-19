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


def test_report_tai_file(client, project_files):
    resp = client.get("/kit/reports/CS1_trend_top_posts.xlsx")
    assert resp.status_code == 200
    assert resp.content.startswith(b"PK")


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
