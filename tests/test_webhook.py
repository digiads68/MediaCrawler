# -*- coding: utf-8 -*-
"""Test kit/webhook/emit — mock httpx, không gọi mạng."""

from __future__ import annotations

import httpx
import pytest

from kit.webhook import (
    emit,
    notify_rising_koc,
    notify_sov_updated,
    notify_trend_brief,
)

URL = "https://n8n.test/webhook/x"


def _client(handler) -> httpx.Client:
    """httpx.Client với MockTransport — bắt request thay vì gọi mạng."""
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_emit_payload_dung_va_thanh_cong():
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200)

    ok = emit("trend_brief", {"text": "xin chào"}, url=URL, client=_client(handler))
    assert ok is True
    assert len(seen) == 1
    import json
    body = json.loads(seen[0].content)
    assert body["event"] == "trend_brief"
    assert body["payload"] == {"text": "xin chào"}
    assert "ts" in body


def test_emit_loi_mang_khong_raise_va_retry_2_lan():
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("mạng rớt")

    ok = emit("sov_updated", {}, url=URL, client=_client(handler))
    assert ok is False          # không raise
    assert calls["n"] == 3      # 1 lần + retry 2 lần


def test_emit_http_5xx_khong_raise():
    ok = emit("x", {}, url=URL,
              client=_client(lambda r: httpx.Response(500)))
    assert ok is False


def test_emit_thieu_url_tra_false(monkeypatch):
    monkeypatch.delenv("NOTIFY_WEBHOOK_URL", raising=False)
    assert emit("x", {}) is False


@pytest.mark.parametrize("fn,event", [
    (lambda c: notify_trend_brief("tóm tắt", url=URL, client=c), "trend_brief"),
    (lambda c: notify_rising_koc([{"creator": "h1"}], url=URL, client=c), "rising_koc"),
    (lambda c: notify_sov_updated(url=URL, client=c), "sov_updated"),
])
def test_cac_ham_tien_ich_gui_dung_event(fn, event):
    import json
    seen: list[dict] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(json.loads(req.content))
        return httpx.Response(200)

    assert fn(_client(handler)) is True
    assert seen[0]["event"] == event


def test_rising_koc_kem_count():
    import json
    seen: list[dict] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(json.loads(req.content))
        return httpx.Response(200)

    notify_rising_koc([{"creator": "a"}, {"creator": "b"}], url=URL,
                      client=_client(handler))
    assert seen[0]["payload"]["count"] == 2
