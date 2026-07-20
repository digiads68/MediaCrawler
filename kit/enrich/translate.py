# -*- coding: utf-8 -*-
"""
Dịch tiêu đề/hook ZH -> VI theo batch (tiết kiệm token).

Mặc định gọi Claude (claude-sonnet-4-6) qua Anthropic Messages API; đặt
provider="none" để trả nguyên văn (chạy offline/test). Test inject client giả
qua tham số `client` — KHÔNG gọi mạng trong test.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Any

logger = logging.getLogger(__name__)

MODEL_DEFAULT = "claude-sonnet-4-6"
BATCH_SIZE_DEFAULT = 40

_SYSTEM = (
    "Bạn là biên dịch viên marketing. Dịch các câu tiếng Trung sang tiếng Việt "
    "tự nhiên, giữ giọng hook video ngắn. Chỉ trả về JSON: mảng chuỗi cùng độ dài "
    "và thứ tự với đầu vào, không thêm lời dẫn hay dấu ```."
)


def _batch_prompt(texts: Sequence[str]) -> str:
    return ("Dịch mảng câu sau sang tiếng Việt, trả JSON mảng chuỗi cùng thứ tự:\n"
            + json.dumps(list(texts), ensure_ascii=False))


def translate_zh_vi(texts: list[str], provider: str = "claude",
                    client: Any | None = None, model: str = MODEL_DEFAULT,
                    batch_size: int = BATCH_SIZE_DEFAULT) -> list[str]:
    """
    Dịch danh sách câu ZH -> VI, gom batch `batch_size` câu/lần gọi.

    - provider="claude": gọi Anthropic Messages API (client tự tạo nếu không inject).
    - provider="none": trả nguyên văn (offline/test).
    - Batch lỗi (mạng/JSON sai) -> giữ nguyên văn batch đó, log cảnh báo, không raise.
    """
    if provider == "none" or not texts:
        return list(texts)
    if provider != "claude":
        raise ValueError(f"Provider chưa hỗ trợ: {provider}")
    if client is None:
        import anthropic  # import trễ: chỉ cần khi gọi thật
        client = anthropic.Anthropic()

    out: list[str] = []
    for i in range(0, len(texts), batch_size):
        batch = list(texts[i:i + batch_size])
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=4096,
                system=_SYSTEM,
                messages=[{"role": "user", "content": _batch_prompt(batch)}],
            )
            translated = json.loads(resp.content[0].text)
            if not isinstance(translated, list) or len(translated) != len(batch):
                raise ValueError("JSON trả về sai độ dài")
            out.extend(str(t) for t in translated)
        except Exception as exc:  # noqa: BLE001 — không làm hỏng job chính
            logger.warning("Dịch batch %s lỗi (%s) — giữ nguyên văn.", i // batch_size, exc)
            out.extend(batch)
    return out
