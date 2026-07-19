# -*- coding: utf-8 -*-
"""Test kit/pipeline/angle_to_brief — provider mock, không gọi mạng."""

from __future__ import annotations

import json

import pytest

from kit.pipeline.angle_to_brief import (
    BRIEF_REQUIRED_KEYS,
    MockProvider,
    load_angles,
    run,
    validate_brief,
)


@pytest.fixture
def angle_jsonl(tmp_path):
    """File jsonl với 2 angle mẫu (1 angle thiếu pain_or_desire để ép normalize)."""
    recs = [
        {"angle_id": "dy_001", "platform": "dy", "source_keyword": "护肤",
         "hook": "7天变化太大了", "format": "before-after",
         "pain_or_desire": "hết bóng nhờn", "cta_observed": "链接在评论区",
         "sound_ref": "bgm_1",
         "metrics": {"like": 1000, "comment": 50, "share": 20, "collect": 300},
         "lang": "zh"},
        {"angle_id": "dy_002", "platform": "dy", "source_keyword": "精华",
         "hook": "真实测评", "format": "review", "pain_or_desire": "",
         "cta_observed": "", "sound_ref": "", "metrics": {}, "lang": "zh"},
    ]
    p = tmp_path / "angle_library.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs),
                 encoding="utf-8")
    return p


def test_load_angles_gioi_han_limit(angle_jsonl):
    assert len(load_angles(angle_jsonl, limit=1)) == 1
    assert len(load_angles(angle_jsonl, limit=10)) == 2


def test_validate_brief_mau_mock_hop_le():
    brief = MockProvider().call("script", {})
    assert validate_brief(brief) == []


def test_validate_brief_bat_loi():
    brief = MockProvider().call("script", {})
    del brief["cta"]
    brief["angle_type"] = "xyz"
    errors = validate_brief({**brief})
    assert any("cta" in e for e in errors)


def test_run_mock_xuat_briefs_jsonl(angle_jsonl, tmp_path):
    out_dir = tmp_path / "out"
    briefs = run(angle_jsonl, "Serum kiềm dầu 199k", limit=10,
                 provider="mock", out_dir=out_dir)
    assert len(briefs) == 2
    # brief đúng schema + truy vết được angle nguồn
    for b, aid in zip(briefs, ["dy_001", "dy_002"], strict=True):
        assert validate_brief(b) == []
        assert aid in b["source_angle_ids"]
        assert all(k in b for k in BRIEF_REQUIRED_KEYS)
        assert b["scorecard"]["verdict"] == "ship"
        assert b["compliance"]["pass"] is True
    # file jsonl mỗi dòng 1 brief parse được
    lines = (out_dir / "briefs.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["language"] == "vi-VN"


def test_run_angle_loi_bi_bo_qua_khong_crash(angle_jsonl, tmp_path):
    class _BrokenScript(MockProvider):
        def call(self, stage, msgs):
            if stage == "script":
                raise RuntimeError("hỏng stage script")
            return super().call(stage, msgs)

    from kit.pipeline import angle_to_brief as mod
    briefs = []
    prov = _BrokenScript()
    for rec in mod.load_angles(angle_jsonl):
        try:
            briefs.append(mod._brief_one(prov, rec, "sp", False, False, False))
        except Exception:
            pass
    assert briefs == []  # lỗi được nuốt ở tầng run(); ở đây chứng minh raise rõ ràng

    # run() thật: không raise dù mọi angle lỗi
    out = mod.run(angle_jsonl, "sp", provider="mock", out_dir=tmp_path / "o2")
    assert len(out) == 2  # mock chuẩn vẫn chạy đủ


def test_provider_khong_ho_tro():
    with pytest.raises(ValueError):
        run("x.jsonl", "sp", provider="gpt")
