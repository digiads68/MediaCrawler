# -*- coding: utf-8 -*-
"""
Dashboard **OVERVIEW** — bức tranh chéo nền tảng.

Dùng khi trộn nhiều mode/nền tảng và cần 1 trang duy nhất để họp: nền tảng nào
đang mạnh, từ khoá nào nhiều, ai đang lên, hashtag gì đang chạy. Cần đi sâu thì
mở dashboard chuyên: search (Trend Radar) · creator (Channel Audit) ·
video (Teardown).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from kit.dashboard import analysis as A
from kit.dashboard import components as C
from kit.dashboard.adapters import PLATFORM_LABELS
from kit.dashboard.metrics import compute_sections
from kit.dashboard.theme import esc, page
from kit.report import charts

TABS = [("sum", "📊 Tổng quan"), ("trend", "🔥 Trend & Video"),
        ("creators", "🎯 Đối thủ"), ("hooks", "🪝 Hook Lab"),
        ("opp", "🧭 Cơ hội")]


def build(bundle: dict[str, Any], *, meta: dict | None = None) -> str:
    """Dựng dashboard tổng quan chéo nền tảng."""
    df = A.add_outlier_ratio(bundle["content"])
    sec = compute_sections(df)
    panes = {
        "sum": _pane_sum(df, sec),
        "trend": _pane_trend(df),
        "creators": _pane_creators(sec["creators"]),
        "hooks": _pane_hooks(df, sec["hooks"]),
        "opp": _pane_opp(sec["opportunity"]),
    }
    return page(title="Tổng quan đa nền tảng",
                eyebrow="DigiAds Kit · OVERVIEW",
                subtitle="Bức tranh chéo nền tảng · mở dashboard chuyên "
                         "(search/creator/video) để đi sâu",
                tabs=TABS, panes=panes, meta=meta)


def _pane_sum(df: pd.DataFrame, sec: dict) -> str:
    top = (f'<div class="chart-grid-3">'
           f'<div>{charts.donut(sec["platform_mix"], title="Nền tảng", unit=" bài")}</div>'
           f'<div>{charts.donut(sec["format_mix"], title="Format nội dung", unit=" bài")}</div>'
           f'<div>{charts.hbar(sec["keyword_mix"], title="Từ khoá thu thập", color_idx=4)}</div>'
           f'</div>')
    tl = sec["timeline"]
    line = (charts.line(tl["series"], tl["x_labels"],
                        title="Số bài đăng theo tuần (12 tuần gần nhất)")
            if tl["series"] else
            '<div class="chart-empty">Chưa đủ dữ liệu thời gian</div>')
    # So sánh nền tảng theo hiệu quả, không chỉ theo số lượng
    rows = []
    for plat, g in df.groupby("platform"):
        rows.append([esc(PLATFORM_LABELS.get(plat, plat)), f"{len(g)}",
                     C.human(g["eng_total"].median()),
                     C.human(g["eng_total"].mean()),
                     C.pct(pd.to_numeric(g.get("save_rate"), errors="coerce").median())])
    plat_tbl = C.table([("Nền tảng", False), ("Số bài", True),
                        ("Eng trung vị", True), ("Eng TB", True),
                        ("Save/Like trung vị", True)], rows)
    return (C.tiles(sec["kpis"])
            + C.panel("Cơ cấu dữ liệu", top)
            + C.panel("So sánh hiệu quả giữa nền tảng", plat_tbl,
                      sub="Nhiều bài chưa chắc hiệu quả — nhìn cột trung vị.")
            + C.panel("Nhịp đăng theo thời gian", line))


def _pane_trend(df: pd.DataFrame) -> str:
    top = df.sort_values("trend_score", ascending=False).head(48)
    return C.panel("Video nổi bật",
                   C.media_grid(top, grid_id="ov-trend", filter_field="platform",
                                badge_col="breakout"),
                   sub="Điểm trend chuẩn hoá theo từng nền tảng để so công bằng.")


def _pane_creators(lb: pd.DataFrame) -> str:
    if lb is None or lb.empty:
        return C.panel("Đối thủ", '<p class="muted">Chưa đủ dữ liệu creator '
                       '(cần ≥2 bài/creator).</p>')
    bar = charts.hbar([(str(r["nickname"]), float(r["eng_tong"]))
                       for _, r in lb.head(10).iterrows()],
                      title="Top creator theo tổng tương tác", color_idx=6)
    rows = []
    for _, r in lb.iterrows():
        vel = float(r.get("velocity", 1) or 1)
        vchip = ("chip-good" if vel >= 1.3 else
                 "chip-warn" if vel >= 1.0 else "chip-muted")
        vlabel = ("đang tăng" if vel >= 1.3 else
                  "ổn định" if vel >= 1.0 else "chững lại")
        deu = float(r.get("do_deu", 0) or 0)
        rows.append([esc(str(r["nickname"])), esc(str(r["platform"])),
                     f'{int(r["so_video"])}', C.human(r["eng_tb"]),
                     C.human(r["eng_tong"]), f'{float(r["trend_tb"]):.0f}',
                     f'<span class="minibar"><span style="width:{deu * 100:.0f}%">'
                     f'</span></span>', f'{vel:.2f}×',
                     f'<span class="chip {vchip}">{vlabel}</span>'])
    tbl = C.table([("Creator", False), ("Nền tảng", False), ("Video", True),
                   ("Eng TB", True), ("Eng tổng", True), ("Điểm trend", True),
                   ("Độ đều", True), ("Velocity", True), ("Nhịp độ", False)], rows)
    return C.panel("Bảng xếp hạng creator / đối thủ", bar + tbl,
                   sub="Cần soi sâu 1 kênh (nhịp đăng, bài bứt phá, công thức "
                       "trúng) → dùng dashboard Channel Audit.")


def _pane_hooks(df: pd.DataFrame, hooks: dict) -> str:
    tags = (charts.hbar(hooks["top_tags"], title="Hashtag / thẻ xuất hiện nhiều",
                        color_idx=3) if hooks["top_tags"] else
            '<div class="chart-empty">Không thấy hashtag</div>')
    perf = A.hook_performance(df)
    if perf:
        rows = [[esc(h["name"]), f'{h["n"]}', C.human(h["eng_median"]),
                 C.pct(h["win_rate"], 0)] for h in perf]
        tbl = C.table([("Công thức hook", False), ("Số bài", True),
                       ("Eng trung vị", True), ("Tỷ lệ thắng", True)], rows)
    else:
        tbl = '<p class="muted">Chưa nhận diện được công thức.</p>'
    return C.panel("Hook & hashtag đang chạy", tags + tbl,
                   sub="Tỷ lệ thắng = % bài của công thức đó vào top 25%.")


def _pane_opp(items: list[dict]) -> str:
    if not items:
        return C.panel("Cơ hội", '<p class="muted">Không đủ dữ liệu.</p>')
    verdict_cls = {"ngách vàng": "chip-good", "đông nhưng hot": "chip-warn",
                   "thử nghiệm": "chip-muted", "bão hoà": "chip-muted"}
    rows = [[esc(o["keyword"]), f'{o["volume"]}', C.human(o["eng"]),
             C.human(o["save"]),
             f'<span class="chip {verdict_cls.get(o["verdict"], "chip-muted")}">'
             f'{esc(o["verdict"])}</span>'] for o in items]
    tbl = C.table([("Từ khoá", False), ("Số bài", True), ("Eng TB", True),
                   ("Save TB", True), ("Đánh giá", False)], rows)
    return C.panel("Bản đồ cơ hội ngách",
                   C.scatter_opportunity(items) + tbl,
                   sub="Góc trên-trái = ngách vàng: ít bài, tương tác cao.")
