# -*- coding: utf-8 -*-
"""
Router /kit — cầu nối REST cho DigiAds Kit (analyzer, reports, angle-brief).

Không đụng các endpoint gốc; mọi logic nặng nằm trong kit/, router chỉ
validate + điều phối. Lỗi trả JSON rõ ràng (detail tiếng Việt).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/kit", tags=["kit"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = PROJECT_ROOT / "reports"

AnalyzeCommand = Literal["trend", "insight", "koc", "opportunity", "seasonal",
                         "price", "sov", "angle"]


class AnalyzeRequest(BaseModel):
    """Yêu cầu chạy 1 lệnh analyzer trên file dữ liệu đã cào."""

    command: AnalyzeCommand
    file: str = Field(..., description="Đường dẫn file dữ liệu (xlsx/jsonl/csv), "
                                       "tương đối so với gốc repo")
    to_supabase: bool = False
    dry_run: bool = False
    notify: bool = False
    brand_map: str | None = Field(default=None,
                                     description="Đường dẫn brand_map.json (cho sov)")


class AngleBriefRequest(BaseModel):
    """Yêu cầu chạy pipeline angle_library.jsonl -> Video Brief."""

    angle_jsonl: str = Field(..., description="Đường dẫn angle_library.jsonl")
    product: str = Field(..., min_length=3, description="Mô tả sản phẩm cần bán")
    provider: Literal["claude", "mock"] = "mock"
    limit: int = Field(default=10, ge=1, le=100)


def _resolve_in_project(rel_path: str) -> Path:
    """Ép đường dẫn nằm TRONG gốc repo (chặn path traversal)."""
    p = (PROJECT_ROOT / rel_path).resolve()
    if not str(p).startswith(str(PROJECT_ROOT)):
        raise HTTPException(status_code=400,
                            detail="Đường dẫn nằm ngoài thư mục dự án.")
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Không thấy file: {rel_path}")
    return p


@router.post("/analyze")
def kit_analyze(req: AnalyzeRequest) -> dict:
    """Chạy analyzer (11 case) — trả số dòng & file output."""
    from kit.queue.tasks import _run_analyzer

    data_file = _resolve_in_project(req.file)
    brand_map = str(_resolve_in_project(req.brand_map)) if req.brand_map else None
    if req.command == "sov" and not brand_map:
        raise HTTPException(status_code=400,
                            detail="Lệnh sov cần brand_map (đường dẫn brand_map.json).")
    try:
        result = _run_analyzer(req.command, str(data_file),
                               to_supabase=req.to_supabase, dry_run=req.dry_run,
                               notify=req.notify, brand_map=brand_map)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422,
                            detail=f"Phân tích lỗi: {exc}") from exc
    return {"status": "ok", **result}


@router.get("/reports")
def kit_reports_list() -> dict:
    """Liệt kê các file báo cáo trong thư mục reports/ (Excel + HTML), mới nhất trước."""
    if not REPORTS_DIR.exists():
        return {"reports": []}
    items = []
    for p in REPORTS_DIR.iterdir():
        if p.is_file() and p.suffix.lower() in (".html", ".xlsx", ".jsonl", ".csv"):
            st = p.stat()
            items.append({"name": p.name, "type": p.suffix[1:].lower(),
                          "size": st.st_size, "modified_at": st.st_mtime,
                          "url": f"/kit/reports/{p.name}"})
    items.sort(key=lambda x: x["modified_at"], reverse=True)
    return {"reports": items}


@router.get("/reports/{name}")
def kit_report(name: str) -> FileResponse:
    """Phục vụ báo cáo do analyzer xuất (thư mục reports/).

    - .html: trả inline (mở/xem ngay trong trình duyệt).
    - .xlsx/.jsonl/.csv: trả kèm tên file để tải xuống.
    """
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ.")
    path = REPORTS_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Không thấy báo cáo: {name}")
    if path.suffix.lower() == ".html":
        # Không đặt filename -> Content-Disposition inline -> trình duyệt render
        return FileResponse(path, media_type="text/html; charset=utf-8")
    return FileResponse(path, filename=name)


@router.get("/media/download")
async def kit_media_download(
    url: str = Query(..., description="Link media gốc trên CDN nền tảng"),
    name: str | None = Query(default=None, description="Tên file mong muốn"),
) -> StreamingResponse:
    """
    Tải file media về máy qua proxy — buộc trình duyệt tải xuống thay vì phát inline.

    Vì sao cần: CDN nền tảng trả `Content-Type: video/mp4` mà không kèm
    `Content-Disposition: attachment`, nên bấm link trực tiếp trong HTML thì
    trình duyệt phát video inline; thuộc tính `download` của thẻ <a> bị bỏ qua
    do khác origin. Endpoint này gắn Referer đúng nền tảng (CDN Bilibili/Douyin
    đòi Referer) rồi stream lại kèm header attachment.

    An toàn: chỉ nhận URL thuộc whitelist CDN/host của 7 nền tảng (chặn SSRF).
    """
    import httpx

    from kit.media_urls import (BROWSER_UA, is_allowed_for_proxy, referer_for,
                                safe_filename)
    from tools.httpx_util import make_async_client

    if not is_allowed_for_proxy(url):
        raise HTTPException(
            status_code=400,
            detail="Link không thuộc CDN của các nền tảng được hỗ trợ "
                   "(chỉ tải media từ Douyin/Xiaohongshu-rednote/Bilibili/"
                   "Kuaishou/Weibo/Zhihu/Tieba).")

    headers = {"User-Agent": BROWSER_UA}
    referer = referer_for(url)
    if referer:
        headers["Referer"] = referer

    client = make_async_client(timeout=httpx.Timeout(30.0, read=300.0),
                               follow_redirects=True)
    try:
        req = client.build_request("GET", url, headers=headers)
        upstream = await client.send(req, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(status_code=502,
                            detail=f"Không tải được từ CDN: {exc}") from exc

    if upstream.status_code >= 400:
        code = upstream.status_code
        await upstream.aclose()
        await client.aclose()
        raise HTTPException(
            status_code=502,
            detail=f"CDN trả lỗi {code} — link có thể đã hết hạn, "
                   f"cần cào lại để lấy link mới.")

    content_type = upstream.headers.get("content-type", "application/octet-stream")
    filename = safe_filename(url, name, content_type)

    async def _body():
        try:
            async for chunk in upstream.aiter_bytes(65536):
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    out_headers = {
        # filename* (RFC 5987) để tên tiếng Việt/Trung không vỡ
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
    }
    if "content-length" in upstream.headers:
        out_headers["Content-Length"] = upstream.headers["content-length"]

    return StreamingResponse(_body(), media_type=content_type,
                             headers=out_headers)


@router.get("/analyze/capabilities")
def kit_analyze_capabilities(file: str = Query(..., description="File dữ liệu")) -> dict:
    """
    Soi 1 file dữ liệu -> cho biết dashboard nào chạy được, cái nào không & vì sao.

    WebUI dùng để chỉ bật những dashboard mà dữ liệu thực sự đỡ được, tránh
    người dùng chọn rồi mới báo lỗi (vd Voice of Customer cần file comment,
    Seasonal cần create_time).
    """
    from kit.analyzer.capabilities import inspect_data_file

    data_file = _resolve_in_project(file)
    try:
        return inspect_data_file(str(data_file))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422,
                            detail=f"Không đọc được file: {exc}") from exc


@router.post("/angle-brief")
def kit_angle_brief(req: AngleBriefRequest) -> dict:
    """Chạy pipeline Angle -> Video Brief, trả danh sách brief JSON."""
    from kit.pipeline.angle_to_brief import run

    angle_file = _resolve_in_project(req.angle_jsonl)
    try:
        briefs = run(str(angle_file), req.product, limit=req.limit,
                     provider=req.provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422,
                            detail=f"Pipeline lỗi: {exc}") from exc
    return {"status": "ok", "count": len(briefs), "briefs": briefs}
