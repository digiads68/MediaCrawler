# -*- coding: utf-8 -*-
"""
Router /kit — cầu nối REST cho DigiAds Kit (analyzer, reports, angle-brief).

Không đụng các endpoint gốc; mọi logic nặng nằm trong kit/, router chỉ
validate + điều phối. Lỗi trả JSON rõ ràng (detail tiếng Việt).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
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
