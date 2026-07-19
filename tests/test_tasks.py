# -*- coding: utf-8 -*-
"""Test kit/queue/tasks — mock REST API + analyzer, không mạng/Redis thật."""

from __future__ import annotations

import json

import httpx
import pandas as pd
import pytest

from kit.queue import tasks as qt


def _mock_api(status_seq: list[str], files: list[dict]):
    """AsyncClient giả lập REST MediaCrawler: start → status* → files."""
    state = {"status_idx": 0, "requests": []}

    def handler(req: httpx.Request) -> httpx.Response:
        state["requests"].append((req.method, req.url.path, req.content))
        if req.url.path == "/api/crawler/start":
            return httpx.Response(200, json={"message": "ok"})
        if req.url.path == "/api/crawler/status":
            i = min(state["status_idx"], len(status_seq) - 1)
            state["status_idx"] += 1
            return httpx.Response(200, json={"status": status_seq[i]})
        if req.url.path == "/api/data/files":
            return httpx.Response(200, json={"files": files})
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler),
                               base_url="http://test")
    return client, state


@pytest.fixture
def fake_analyzer(monkeypatch):
    """Thay _run_analyzer bằng bản ghi lại lời gọi (không đụng pandas/excel)."""
    calls: list[dict] = []

    def spy(command, file_path, to_supabase=False, dry_run=False,
            notify=False, brand_map=None, incremental=False,
            checkpoint_db=None, platform="", keyword=""):
        calls.append({"command": command, "file": file_path,
                      "to_supabase": to_supabase, "notify": notify})
        return {"command": command, "rows": 7, "file": file_path}

    monkeypatch.setattr(qt, "_run_analyzer", spy)
    return calls


@pytest.mark.asyncio
async def test_luong_du_job_chay_het(fake_analyzer):
    client, state = _mock_api(
        status_seq=["running", "running", "idle"],
        files=[{"path": "data/dy/old.xlsx", "modified_at": "2026-07-01T00:00:00"},
               {"path": "data/dy/new.xlsx", "modified_at": "2026-07-19T00:00:00"}])
    async with client:
        res = await qt.crawl_and_analyze(
            {"http_client": client}, "dy", "search", "护肤",
            {"analyze": "trend", "to_supabase": True, "notify": True,
             "poll_interval": 0.01, "timeout": 5})
    assert res["status"] == "ok" and res["rows"] == 7
    # chọn file MỚI nhất
    assert fake_analyzer[0]["file"] == "data/dy/new.xlsx"
    assert fake_analyzer[0]["to_supabase"] is True
    # payload start đúng
    method, path, content = state["requests"][0]
    assert (method, path) == ("POST", "/api/crawler/start")
    body = json.loads(content)
    assert body["platform"] == "dy" and body["keywords"] == "护肤"
    assert body["save_option"] == "excel"


@pytest.mark.asyncio
async def test_crawler_error_khong_chay_analyzer(fake_analyzer):
    client, _ = _mock_api(status_seq=["running", "error"], files=[])
    async with client:
        res = await qt.crawl_and_analyze({"http_client": client}, "dy", "search", "x",
                                         {"poll_interval": 0.01, "timeout": 5})
    assert res["status"] == "error"
    assert fake_analyzer == []


@pytest.mark.asyncio
async def test_khong_co_file_du_lieu(fake_analyzer):
    client, _ = _mock_api(status_seq=["idle"], files=[])
    async with client:
        res = await qt.crawl_and_analyze({"http_client": client}, "dy", "search", "x",
                                         {"poll_interval": 0.01, "timeout": 5})
    assert res["status"] == "no_data"
    assert fake_analyzer == []


@pytest.mark.asyncio
async def test_timeout_poll(fake_analyzer):
    client, _ = _mock_api(status_seq=["running"], files=[])
    async with client:
        res = await qt.crawl_and_analyze({"http_client": client}, "dy", "search", "x",
                                         {"poll_interval": 0.01, "timeout": 0.03})
    assert res["status"] == "timeout"


def test_run_analyzer_lenh_khong_hop_le():
    with pytest.raises(ValueError):
        qt._run_analyzer("hack", "x.xlsx")


def test_run_analyzer_goi_that_voi_file_synthetic(tmp_path, monkeypatch):
    """_run_analyzer chạy thật lệnh trend trên xlsx synthetic (không mạng)."""
    df = pd.DataFrame({
        "title": ["7天变化", "开箱"], "desc": ["前后", "到货"],
        "liked_count": ["100", "50"], "comment_count": ["5", "2"],
        "share_count": ["1", "0"], "collected_count": ["20", "3"],
        "create_time": [1767600000, 1767700000],
        "source_keyword": ["a", "b"],
    })
    f = tmp_path / "search_t.xlsx"
    df.to_excel(f, index=False)
    monkeypatch.chdir(tmp_path)          # reports/ ghi vào tmp
    res = qt._run_analyzer("trend", str(f))
    assert res["rows"] == 2 and res["command"] == "trend"


def test_worker_settings_tuan_tu():
    """Ranh giới: worker phải max_jobs=1, không retry dồn."""
    from kit.queue.worker import WorkerSettings
    assert WorkerSettings.max_jobs == 1
    assert WorkerSettings.max_tries == 1
    assert qt.crawl_and_analyze in WorkerSettings.functions


def test_enqueue_parse_args():
    from kit.queue.enqueue import _parse
    platform, ctype, kw, opts = _parse(
        ["dy", "search", "护肤", "--analyze", "koc", "--to", "supabase",
         "--notify", "--max-notes", "50"])
    assert (platform, ctype, kw) == ("dy", "search", "护肤")
    assert opts == {"analyze": "koc", "to_supabase": True, "notify": True,
                    "max_notes_count": 50}
