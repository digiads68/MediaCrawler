# -*- coding: utf-8 -*-
"""
Biến angle_library.jsonl thành Video Brief JSON (chuỗi 6 prompt).

Luồng mỗi angle: normalize (nếu thiếu pain/desire) → concept → script
→ (tuỳ chọn) variation / compliance / scorecard. Bản ghi lỗi chỉ log & bỏ qua.

CLI:
    python kit/pipeline/angle_to_brief.py <angle.jsonl> --product "..." \
        [--provider mock] [--limit 10]

Provider:
    claude  gọi Anthropic Messages API (claude-sonnet-4-6), cần ANTHROPIC_API_KEY.
    mock    không gọi mạng — trả brief mẫu hợp lệ (test/demo offline).
"""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from kit.prompts.angle_to_video_prompts import (  # noqa: E402
    MODEL_DEFAULT,
    Angle,
    build_compliance_prompt,
    build_concept_prompt,
    build_normalize_prompt,
    build_scorecard_prompt,
    build_script_prompt,
    build_variation_prompt,
)

logger = logging.getLogger(__name__)

OUT_DIR_DEFAULT = Path(__file__).resolve().parent / "out"

# Khoá bắt buộc của Video Brief (khớp VIDEO_BRIEF_SCHEMA trong kit/prompts)
BRIEF_REQUIRED_KEYS = [
    "concept_id", "product_focus", "angle_type", "hook_line", "duration_sec",
    "aspect_ratio", "language", "scenes", "cta", "sound_ref", "hashtags",
    "source_angle_ids", "compliance_flags",
]
SCENE_REQUIRED_KEYS = ["t_start", "t_end", "visual", "onscreen_text", "voiceover"]
ANGLE_TYPES = {"pain", "desire", "proof", "curiosity", "comparison", "trend"}


def validate_brief(brief: dict) -> list[str]:
    """Kiểm tra Video Brief theo schema — trả danh sách lỗi (rỗng = hợp lệ)."""
    errors: list[str] = []
    for k in BRIEF_REQUIRED_KEYS:
        if k not in brief:
            errors.append(f"thiếu khoá: {k}")
    if errors:
        return errors
    if brief["angle_type"] not in ANGLE_TYPES:
        errors.append(f"angle_type không hợp lệ: {brief['angle_type']}")
    try:
        dur = int(brief["duration_sec"])
        if not 10 <= dur <= 30:
            errors.append(f"duration_sec ngoài khoảng hợp lý: {dur}")
    except (TypeError, ValueError):
        errors.append("duration_sec không phải số")
    scenes = brief["scenes"]
    if not isinstance(scenes, list) or not scenes:
        errors.append("scenes phải là mảng không rỗng")
    else:
        for i, sc in enumerate(scenes):
            for k in SCENE_REQUIRED_KEYS:
                if k not in sc:
                    errors.append(f"scene[{i}] thiếu khoá: {k}")
    for k in ["hashtags", "source_angle_ids", "compliance_flags"]:
        if not isinstance(brief[k], list):
            errors.append(f"{k} phải là mảng")
    return errors


# ----------------------------------------------------------------------------
# Providers
# ----------------------------------------------------------------------------

def _strip_fence(text: str) -> str:
    """Bỏ rào ```json ... ``` nếu model lỡ thêm."""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


class ClaudeProvider:
    """Gọi Anthropic Messages API, parse JSON thuần từ câu trả lời."""

    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        self.client = client

    def call(self, stage: str, msgs: dict) -> Any:
        """Gửi 1 prompt stage, trả object JSON đã parse."""
        resp = self.client.messages.create(
            model=msgs.get("model", MODEL_DEFAULT),
            max_tokens=4096,
            system=msgs["system"],
            messages=[{"role": "user", "content": msgs["user"]}],
        )
        return json.loads(_strip_fence(resp.content[0].text))


class MockProvider:
    """Trả JSON mẫu hợp lệ cho từng stage — không gọi mạng (test/demo)."""

    def call(self, stage: str, msgs: dict) -> Any:
        if stage == "normalize":
            return {"angle_id": "mock", "platform": "dy", "source_keyword": "mock",
                    "hook": "hook mẫu", "format": "review",
                    "pain_or_desire": "da dầu bóng nhờn", "cta_observed": "",
                    "sound_ref": "", "metrics": {}, "lang": "zh"}
        if stage == "concept":
            return [{"concept_id": "c_mock", "angle_type": "pain",
                     "big_idea": "Vạch trần thói quen sai", "hook_line":
                     "Bạn càng rửa mặt, da càng đổ dầu — vì sao?",
                     "why_it_sells": "Đánh trúng nỗi bực hằng ngày.",
                     "source_angle_ids": []}]
        if stage == "script":
            return {
                "concept_id": "c_mock", "product_focus": "sản phẩm demo",
                "angle_type": "pain",
                "hook_line": "Bạn càng rửa mặt, da càng đổ dầu — vì sao?",
                "duration_sec": 18, "aspect_ratio": "9:16", "language": "vi-VN",
                "scenes": [
                    {"t_start": 0.0, "t_end": 3.0,
                     "visual": "Cận mặt bóng dầu dưới đèn",
                     "onscreen_text": "Càng rửa càng dầu?",
                     "voiceover": "Da bạn đổ dầu vì rửa sai cách."},
                    {"t_start": 3.0, "t_end": 12.0,
                     "visual": "Demo thoa serum, texture thấm nhanh",
                     "onscreen_text": "Kiềm dầu 8 tiếng",
                     "voiceover": "Một lớp mỏng, khô thoáng cả ngày."},
                    {"t_start": 12.0, "t_end": 18.0,
                     "visual": "Before-after chia đôi màn hình",
                     "onscreen_text": "199k | Giỏ vàng",
                     "voiceover": "Nhấn giỏ vàng đặt ngay hôm nay."},
                ],
                "cta": "Nhấn giỏ vàng đặt ngay", "sound_ref": "nhạc thư viện hợp lệ",
                "hashtags": ["#skincare", "#kiemdau"], "source_angle_ids": [],
                "compliance_flags": [],
            }
        if stage == "variation":
            return [{"variant_id": f"v{i}", "mechanism": m,
                     "hook_line": f"Hook biến thể {i}", "cta": "Nhấn giỏ vàng"}
                    for i, m in enumerate(["khan hiếm", "tò mò"], 1)]
        if stage == "compliance":
            return {"pass": True, "issues": [], "safe_rewrite": ""}
        if stage == "scorecard":
            return {"hook_strength": 8, "clarity": 8, "desire": 7,
                    "cta_strength": 8, "scroll_stop_prob": "high",
                    "top_fix": "Không", "verdict": "ship"}
        raise ValueError(f"Stage không hỗ trợ: {stage}")


def _make_provider(name: str, client: Any | None = None):
    """Khởi tạo provider theo tên (claude | mock)."""
    if name == "mock":
        return MockProvider()
    if name == "claude":
        return ClaudeProvider(client=client)
    raise ValueError(f"Provider chưa hỗ trợ: {name}")


# ----------------------------------------------------------------------------
# Pipeline
# ----------------------------------------------------------------------------

def load_angles(angle_jsonl: str | Path, limit: int = 10) -> list[dict]:
    """Đọc tối đa `limit` angle từ file jsonl."""
    records: list[dict] = []
    with open(angle_jsonl, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
            if len(records) >= limit:
                break
    return records


def _brief_one(provider: Any, rec: dict, product_brief: str,
               with_variation: bool, with_compliance: bool,
               with_scorecard: bool) -> dict:
    """Chạy chuỗi stage cho 1 angle, trả Video Brief kèm phụ lục."""
    # Stage 0 — normalize nếu thiếu pain/desire
    if not rec.get("pain_or_desire"):
        norm = provider.call("normalize", build_normalize_prompt(rec))
        # Chỉ điền trường còn trống — không đè angle_id/hook... gốc
        rec = {**rec, **{k: v for k, v in norm.items() if v and not rec.get(k)}}
    angle = Angle(**{k: rec.get(k, "") for k in
                     ["angle_id", "platform", "source_keyword", "hook", "format",
                      "pain_or_desire", "cta_observed", "sound_ref"]},
                  metrics=rec.get("metrics") or {}, lang=rec.get("lang", "zh"))

    # Stage 1 — concept (lấy concept đầu tiên)
    concepts = provider.call("concept", build_concept_prompt([angle], product_brief, n=1))
    concept = concepts[0] if isinstance(concepts, list) else concepts

    # Stage 2 — script -> Video Brief
    brief = provider.call("script", build_script_prompt(concept, product_brief))
    brief.setdefault("source_angle_ids", [])
    if angle.angle_id not in brief["source_angle_ids"]:
        brief["source_angle_ids"].append(angle.angle_id)
    errors = validate_brief(brief)
    if errors:
        raise ValueError("Video Brief sai schema: " + "; ".join(errors))

    # Stage 3-5 — tuỳ chọn
    if with_variation:
        brief["variations"] = provider.call("variation", build_variation_prompt(brief))
    if with_compliance:
        brief["compliance"] = provider.call("compliance", build_compliance_prompt(brief))
    if with_scorecard:
        brief["scorecard"] = provider.call("scorecard", build_scorecard_prompt(brief))
    return brief


def run(angle_jsonl: str | Path, product_brief: str, limit: int = 10,
        provider: str = "claude", client: Any | None = None,
        with_variation: bool = False, with_compliance: bool = True,
        with_scorecard: bool = True, out_dir: str | Path | None = None) -> list[dict]:
    """
    Chạy pipeline trên tối đa `limit` angle; xuất out/briefs.jsonl.

    Trả danh sách Video Brief hợp lệ (angle lỗi bị bỏ qua, có log).
    """
    prov = _make_provider(provider, client=client)
    records = load_angles(angle_jsonl, limit=limit)
    print(f"Nạp {len(records)} angle từ {angle_jsonl} (provider={provider})")

    briefs: list[dict] = []
    for rec in records:
        try:
            briefs.append(_brief_one(prov, rec, product_brief,
                                     with_variation, with_compliance, with_scorecard))
        except Exception as exc:  # noqa: BLE001 — 1 angle lỗi không crash cả lô
            logger.warning("Bỏ qua angle %s: %s", rec.get("angle_id", "?"), exc)

    out = Path(out_dir) if out_dir else OUT_DIR_DEFAULT
    out.mkdir(parents=True, exist_ok=True)
    path = out / "briefs.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for b in briefs:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")
    print(f"[✓] Xuất {len(briefs)}/{len(records)} brief -> {path}")

    # Tóm tắt scorecard
    scored = [b for b in briefs if isinstance(b.get("scorecard"), dict)]
    if scored:
        ship = sum(1 for b in scored if b["scorecard"].get("verdict") == "ship")
        hook_tb = sum(b["scorecard"].get("hook_strength", 0) for b in scored) / len(scored)
        print(f"Scorecard: {ship}/{len(scored)} verdict=ship | hook trung bình {hook_tb:.1f}/10")
    return briefs


def main() -> None:
    """CLI: <angle.jsonl> --product "..." [--provider mock] [--limit 10]."""
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)
    angle_jsonl = args[0]
    product, provider, limit = "", "claude", 10
    i = 1
    while i < len(args):
        if args[i] == "--product":
            product = args[i + 1]; i += 2
        elif args[i] == "--provider":
            provider = args[i + 1]; i += 2
        elif args[i] == "--limit":
            limit = int(args[i + 1]); i += 2
        else:
            print(f"Đối số không hợp lệ: {args[i]}"); sys.exit(1)
    if not product:
        print("Thiếu --product \"mô tả sản phẩm\""); sys.exit(1)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(angle_jsonl, product, limit=limit, provider=provider)


if __name__ == "__main__":
    main()
