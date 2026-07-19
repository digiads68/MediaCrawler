# -*- coding: utf-8 -*-
"""
MCP server cho MediaCrawler (bản fork có REST API).

Mục đích: bọc một lớp MCP mỏng lên REST API sẵn có của MediaCrawler
(http://127.0.0.1:8080) để AI agent (Claude / Paperclip) tự gọi được:
  "quét trend Douyin ngành X" -> nhận dữ liệu (đã ẩn danh) -> tự viết brief.

⚠ NGUYÊN TẮC (đọc kỹ):
  - Chỉ dùng cho NGHIÊN CỨU NỘI BỘ dữ liệu công khai. Không tái xuất bản.
  - Giữ concurrency = 1, tôn trọng nghỉ giữa request. Không quét quy mô lớn.
  - Tuân thủ ToS nền tảng + Nghị định 13/2023 (dữ liệu cá nhân).

Chạy độc lập:  uv run python mcp_mediacrawler.py
Cần: pip install "mcp[cli]" httpx   (hoặc thêm vào uv)
Yêu cầu: API MediaCrawler đang chạy  ->  uvicorn api.main:app --port 8080
"""

import asyncio
import os

import httpx
from mcp.server.fastmcp import FastMCP

# ---- Cấu hình ----------------------------------------------------------------
API_BASE = os.environ.get("MEDIACRAWLER_API", "http://127.0.0.1:8080")
POLL_INTERVAL_SEC = 5          # nhịp hỏi trạng thái
POLL_TIMEOUT_SEC = 20 * 60     # trần thời gian chờ 1 lần crawl
DEFAULT_MAX_NOTES = 50         # trần mặc định an toàn, tránh quét nặng

mcp = FastMCP("mediacrawler")

# Bảng mã nền tảng cho agent dễ đọc
PLATFORMS = {
    "douyin": "dy", "dy": "dy",
    "xiaohongshu": "xhs", "xhs": "xhs", "red": "xhs",
    "kuaishou": "ks", "ks": "ks",
    "bilibili": "bili", "bili": "bili",
    "weibo": "wb", "wb": "wb",
    "tieba": "tieba", "zhihu": "zhihu",
}


def _norm_platform(p: str) -> str:
    key = p.strip().lower()
    if key not in PLATFORMS:
        raise ValueError(f"Nền tảng không hỗ trợ: {p}. Chọn: {sorted(set(PLATFORMS.values()))}")
    return PLATFORMS[key]


async def _start(payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{API_BASE}/api/crawler/start", json=payload)
        r.raise_for_status()
        return r.json()


async def _status() -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{API_BASE}/api/crawler/status")
        r.raise_for_status()
        return r.json()


async def _wait_until_done() -> dict:
    """Chờ crawl chạy xong (status quay về idle) hoặc lỗi."""
    waited = 0
    while waited < POLL_TIMEOUT_SEC:
        st = await _status()
        if st.get("status") in ("idle", "error"):
            return st
        await asyncio.sleep(POLL_INTERVAL_SEC)
        waited += POLL_INTERVAL_SEC
    return {"status": "timeout", "error_message": "Vượt trần thời gian chờ."}


async def _newest_file(platform: str) -> dict | None:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{API_BASE}/api/data/files", params={"platform": platform})
        r.raise_for_status()
        files = r.json().get("files", [])
    if not files:
        return None
    return sorted(files, key=lambda f: f.get("modified_at", ""), reverse=True)[0]


async def _read_file(path: str, limit: int = 50) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{API_BASE}/api/data/files/{path}",
                        params={"preview": True, "limit": limit})
        r.raise_for_status()
        return r.json()


async def _run(payload: dict, platform: str, preview: int) -> dict:
    """Khởi động crawl -> chờ xong -> trả về file mới nhất + preview."""
    try:
        await _start(payload)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            return {"ok": False, "error": "Đang có một tiến trình crawl khác chạy. Hãy chờ hoặc gọi stop."}
        return {"ok": False, "error": f"Không khởi động được: {e}"}

    done = await _wait_until_done()
    if done.get("status") == "error":
        return {"ok": False, "error": done.get("error_message", "Crawl lỗi.")}

    newest = await _newest_file(platform)
    if not newest:
        return {"ok": True, "note": "Crawl xong nhưng chưa thấy file kết quả.", "status": done}

    data = await _read_file(newest["path"], limit=preview)
    return {
        "ok": True,
        "file": newest,
        "preview": data,
        "reminder": "Dữ liệu đã ẩn danh nickname. Chỉ dùng để nghiên cứu, không tái xuất bản.",
    }


# ---- TOOLS phơi ra cho agent -------------------------------------------------

@mcp.tool()
async def crawl_search(
    platform: str,
    keywords: str,
    max_notes: int = DEFAULT_MAX_NOTES,
    with_comments: bool = True,
    with_sub_comments: bool = False,
    save_option: str = "excel",
    preview_rows: int = 50,
) -> dict:
    """
    Quét nội dung theo TỪ KHOÁ (chế độ search) — dùng cho radar trend & product research.
    platform: douyin | xiaohongshu | kuaishou | bilibili | weibo | tieba | zhihu
    keywords: các cụm từ, ngăn cách bằng dấu phẩy, ví dụ "护肤教程,穿搭".
    """
    p = _norm_platform(platform)
    payload = {
        "platform": p, "crawler_type": "search", "keywords": keywords,
        "enable_comments": with_comments, "enable_sub_comments": with_sub_comments,
        "save_option": save_option, "max_notes_count": max(1, min(max_notes, 500)),
        "headless": True,
    }
    return await _run(payload, p, preview_rows)


@mcp.tool()
async def crawl_detail(
    platform: str,
    post_ids: str,
    with_comments: bool = True,
    with_sub_comments: bool = True,
    max_comments: int = 500,
    save_option: str = "jsonl",
    preview_rows: int = 50,
) -> dict:
    """
    Bóc sâu 1 hoặc nhiều POST/VIDEO viral theo ID (chế độ detail) — dùng cho voice-of-customer.
    post_ids: danh sách ID, ngăn cách bằng dấu phẩy.
    Lưu jsonl để MediaCrawler tự sinh word cloud từ comment.
    """
    p = _norm_platform(platform)
    payload = {
        "platform": p, "crawler_type": "detail", "specified_ids": post_ids,
        "enable_comments": with_comments, "enable_sub_comments": with_sub_comments,
        "save_option": save_option, "max_comments_count": max(1, min(max_comments, 2000)),
        "headless": True,
    }
    return await _run(payload, p, preview_rows)


@mcp.tool()
async def crawl_creator(
    platform: str,
    creator_ids: str,
    with_comments: bool = False,
    save_option: str = "excel",
    preview_rows: int = 50,
) -> dict:
    """
    Quét trang NHÀ SÁNG TẠO theo ID (chế độ creator) — dùng để thẩm định KOC / soi đối thủ.
    creator_ids: danh sách ID creator, ngăn cách bằng dấu phẩy.
    """
    p = _norm_platform(platform)
    payload = {
        "platform": p, "crawler_type": "creator", "creator_ids": creator_ids,
        "enable_comments": with_comments, "save_option": save_option,
        "headless": True,
    }
    return await _run(payload, p, preview_rows)


@mcp.tool()
async def get_status() -> dict:
    """Kiểm tra trạng thái tiến trình crawl (idle / running / stopping / error)."""
    return await _status()


@mcp.tool()
async def list_results(platform: str | None = None) -> dict:
    """Liệt kê các file dữ liệu đã xuất, lọc theo nền tảng nếu cần."""
    params = {}
    if platform:
        params["platform"] = _norm_platform(platform)
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{API_BASE}/api/data/files", params=params)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def read_result(file_path: str, limit: int = 100) -> dict:
    """Đọc nội dung (preview) một file kết quả đã ẩn danh để agent phân tích."""
    return await _read_file(file_path, limit=limit)


if __name__ == "__main__":
    # Giao tiếp qua stdio để cắm vào Claude Desktop / Paperclip.
    mcp.run(transport="stdio")
