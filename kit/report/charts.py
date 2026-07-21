# -*- coding: utf-8 -*-
"""
Sinh biểu đồ SVG server-side (không thư viện, không CDN, tự chứa trong HTML).

Mọi biểu đồ tham chiếu màu qua CSS custom property (--c-1..--c-6, --ink,
--muted, --grid, --surface-2) do html_report.py định nghĩa — nhờ vậy 1 nơi
đổi màu, tự động theme sáng/tối. Định danh (identity) không chỉ dựa vào màu:
donut/line luôn kèm nhãn chữ (chuẩn khả dụng CVD của dataviz skill).
"""

from __future__ import annotations

import html
import math
from collections.abc import Sequence

# Số slot màu (khớp palette đã validate trong html_report.py)
N_COLORS = 6


def _esc(s: object) -> str:
    """Escape chuỗi để nhét an toàn vào SVG/HTML."""
    return html.escape(str(s), quote=True)


def _fmt(v: float) -> str:
    """Định dạng số gọn: 12.3K, 1.2M — cho nhãn biểu đồ."""
    v = float(v)
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"{v / 1_000:.1f}K"
    if v == int(v):
        return str(int(v))
    return f"{v:.1f}"


def _arc_path(cx: float, cy: float, r: float, a0: float, a1: float) -> str:
    """Đường path cung tròn từ góc a0->a1 (radian) — để stroke thành lát donut."""
    x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
    x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
    large = 1 if (a1 - a0) > math.pi else 0
    return f"M {x0:.2f} {y0:.2f} A {r:.2f} {r:.2f} 0 {large} 1 {x1:.2f} {y1:.2f}"


def donut(slices: Sequence[tuple[str, float]], *, size: int = 190,
          title: str = "", unit: str = "") -> str:
    """
    Biểu đồ donut 'cơ cấu' + chú giải có nhãn & %.

    slices: [(nhãn, giá_trị)] — giá trị âm/0 bị bỏ. Tối đa N_COLORS lát
    (dư gộp thành 'Khác').
    """
    data = [(str(lb), float(v)) for lb, v in slices if v and v > 0]
    if not data:
        return _empty(size, "Không đủ dữ liệu")
    data.sort(key=lambda x: x[1], reverse=True)
    if len(data) > N_COLORS:
        head = data[: N_COLORS - 1]
        rest = sum(v for _, v in data[N_COLORS - 1:])
        data = [*head, ("Khác", rest)]
    total = sum(v for _, v in data)

    cx = cy = size / 2
    r = size / 2 - 16
    sw = 26
    a = -math.pi / 2  # bắt đầu từ đỉnh
    gap = 0.03        # khe 2px giữa các lát
    arcs: list[str] = []
    for i, (_, v) in enumerate(data):
        frac = v / total
        a1 = a + frac * 2 * math.pi
        arcs.append(
            f'<path d="{_arc_path(cx, cy, r, a + gap, max(a + gap, a1 - gap))}" '
            f'fill="none" stroke="var(--c-{i % N_COLORS + 1})" '
            f'stroke-width="{sw}" stroke-linecap="butt"/>'
        )
        a = a1

    center = (f'<text x="{cx}" y="{cy - 4}" text-anchor="middle" '
              f'class="donut-total">{_fmt(total)}</text>'
              f'<text x="{cx}" y="{cy + 14}" text-anchor="middle" '
              f'class="donut-unit">{_esc(unit or "tổng")}</text>')

    legend_rows = []
    for i, (label, v) in enumerate(data):
        pct = v / total * 100
        legend_rows.append(
            f'<div class="lg-row"><span class="lg-dot" '
            f'style="background:var(--c-{i % N_COLORS + 1})"></span>'
            f'<span class="lg-label">{_esc(label)}</span>'
            f'<span class="lg-val">{pct:.0f}%</span></div>'
        )

    ttl = f'<div class="chart-title">{_esc(title)}</div>' if title else ""
    return (
        f'<div class="chart-donut">{ttl}'
        f'<div class="donut-wrap">'
        f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" '
        f'role="img" aria-label="{_esc(title or "bieu do co cau")}">'
        f'{"".join(arcs)}{center}</svg>'
        f'<div class="donut-legend">{"".join(legend_rows)}</div>'
        f"</div></div>"
    )


def hbar(rows: Sequence[tuple[str, float]], *, title: str = "",
         color_idx: int = 1, unit: str = "") -> str:
    """Thanh ngang xếp hạng — nhãn trái, thanh, giá trị phải."""
    data = [(str(lb), float(v)) for lb, v in rows]
    if not data:
        return _empty(160, "Không đủ dữ liệu")
    vmax = max((v for _, v in data), default=0) or 1
    bars = []
    for label, v in data:
        w = max(2.0, v / vmax * 100)
        bars.append(
            f'<div class="hb-row">'
            f'<span class="hb-label" title="{_esc(label)}">{_esc(label)}</span>'
            f'<span class="hb-track"><span class="hb-fill" '
            f'style="width:{w:.1f}%;background:var(--c-{color_idx})"></span></span>'
            f'<span class="hb-val">{_fmt(v)}{_esc(unit)}</span></div>'
        )
    ttl = f'<div class="chart-title">{_esc(title)}</div>' if title else ""
    return f'<div class="chart-hbar">{ttl}{"".join(bars)}</div>'


def line(series: Sequence[dict], x_labels: Sequence[str], *,
         title: str = "", unit: str = "", height: int = 210) -> str:
    """
    Biểu đồ đường đa chuỗi (chỉ số theo keyword / theo tuần).

    series: [{"name": str, "points": [float,...]}] — mỗi chuỗi 1 màu theo thứ tự.
    x_labels: nhãn trục X (cùng độ dài points).
    """
    series = [s for s in series if s.get("points")]
    if not series or not x_labels:
        return _empty(height, "Không đủ dữ liệu")

    w, h = 560, height
    pad_l, pad_r, pad_t, pad_b = 46, 60, 16, 30
    plot_w, plot_h = w - pad_l - pad_r, h - pad_t - pad_b
    all_y = [y for s in series for y in s["points"]]
    ymax = max(all_y) or 1
    n = len(x_labels)
    xstep = plot_w / max(1, n - 1) if n > 1 else 0

    def px(i: int) -> float:
        return pad_l + (i * xstep if n > 1 else plot_w / 2)

    def py(v: float) -> float:
        return pad_t + plot_h - (v / ymax) * plot_h

    # lưới ngang + nhãn Y (4 mức)
    grid, yaxis = [], []
    for k in range(5):
        gy = pad_t + plot_h * k / 4
        grid.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l + plot_w}" '
                    f'y2="{gy:.1f}" stroke="var(--grid)" stroke-width="1"/>')
        yaxis.append(f'<text x="{pad_l - 8}" y="{gy + 4:.1f}" text-anchor="end" '
                     f'class="ax">{_fmt(ymax * (4 - k) / 4)}</text>')

    xaxis = []
    for i, lb in enumerate(x_labels):
        xaxis.append(f'<text x="{px(i):.1f}" y="{h - 8}" text-anchor="middle" '
                     f'class="ax">{_esc(lb)}</text>')

    lines, dots, endlbl = [], [], []
    for si, s in enumerate(series):
        ci = si % N_COLORS + 1
        pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(s["points"]))
        lines.append(f'<polyline points="{pts}" fill="none" '
                     f'stroke="var(--c-{ci})" stroke-width="2.5"/>')
        for i, v in enumerate(s["points"]):
            dots.append(f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="3.5" '
                        f'fill="var(--c-{ci})" stroke="var(--surface-2)" '
                        f'stroke-width="1.5"><title>{_esc(s["name"])}: '
                        f'{_fmt(v)}{_esc(unit)}</title></circle>')
        last = len(s["points"]) - 1
        endlbl.append(f'<text x="{px(last) + 6:.1f}" y="{py(s["points"][last]) + 4:.1f}" '
                      f'class="endlbl" fill="var(--c-{ci})">{_esc(s["name"])}</text>')

    ttl = f'<div class="chart-title">{_esc(title)}</div>' if title else ""
    return (
        f'<div class="chart-line">{ttl}'
        f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" '
        f'aria-label="{_esc(title or "bieu do duong")}">'
        f'{"".join(grid)}{"".join(yaxis)}{"".join(xaxis)}'
        f'{"".join(lines)}{"".join(dots)}{"".join(endlbl)}</svg></div>'
    )


def _empty(size: int, msg: str) -> str:
    """Khối trống khi thiếu dữ liệu — vẫn giữ layout."""
    return (f'<div class="chart-empty" style="min-height:{size // 2}px">'
            f'{_esc(msg)}</div>')
