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


def heatmap(rows: Sequence[str], cols: Sequence[str],
            values: Sequence[Sequence[float | None]], *,
            title: str = "", unit: str = "", cell: int = 34,
            color_idx: int = 1, row_label_w: int = 116) -> str:
    """
    Bản đồ nhiệt hàng × cột — trả SVG inline.

    Dùng cho câu hỏi kiểu "format nào ghép hook nào thì ăn" (Format Playbook) và
    "từ khoá nào mạnh ở nền tảng nào" (Cross-platform).

    Sắc độ thể hiện bằng `opacity` trên `var(--c-{color_idx})` thay vì một thang
    màu rời: nhờ đó tự chạy đúng ở cả theme sáng và tối mà KHÔNG phải thêm biến
    màu mới (biến màu đang khai 3 lần trong `_CSS`, thêm 1 biến là phải sửa cả 3).

    `None` (không phải 0) = KHÔNG ĐO ĐƯỢC -> ô xám kèm "—". Phân biệt này là bắt
    buộc: khi so sánh chéo nền tảng, Kuaishou không có comment/share, vẽ thành 0
    sẽ nói sai rằng nó bằng 0.

    Args:
        rows: nhãn hàng. cols: nhãn cột.
        values: values[i][j] ứng với rows[i] × cols[j]; None = n/a.
        unit: hậu tố trong tooltip (vd "%", "bài").
        cell: cạnh 1 ô (px). color_idx: 1..6 theo var(--c-N).
    """
    if not rows or not cols:
        return _empty(cell * 6, "Không đủ dữ liệu")

    nums = [v for row in values for v in row
            if v is not None and not _is_nan(v)]
    vmax = max(nums) if nums else 0.0
    if vmax <= 0:
        return _empty(cell * 6, "Không đủ dữ liệu")

    top_h = 34                      # chỗ cho nhãn cột (xoay chéo)
    w = row_label_w + len(cols) * cell + 8
    h = top_h + len(rows) * cell + 6
    parts: list[str] = []

    # Nhãn cột — xoay 35 độ để nhãn dài không chồng nhau
    for j, c in enumerate(cols):
        cx = row_label_w + j * cell + cell / 2
        parts.append(
            f'<text x="{cx:.1f}" y="{top_h - 8}" class="hm-lbl" '
            f'text-anchor="end" transform="rotate(-35 {cx:.1f} {top_h - 8})">'
            f'{_esc(str(c)[:14])}</text>')

    for i, r in enumerate(rows):
        y = top_h + i * cell
        parts.append(
            f'<text x="{row_label_w - 8}" y="{y + cell / 2 + 4:.1f}" '
            f'class="hm-lbl" text-anchor="end">{_esc(str(r)[:16])}</text>')
        for j in range(len(cols)):
            x = row_label_w + j * cell
            v = values[i][j] if j < len(values[i]) else None
            if v is None or _is_nan(v):
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{cell - 2}" height="{cell - 2}" '
                    f'rx="3" fill="var(--surface-2)"/>'
                    f'<title>{_esc(r)} × {_esc(c := cols[j])}: không đo được</title>'
                    f'<text x="{x + (cell - 2) / 2:.1f}" y="{y + cell / 2 + 3:.1f}" '
                    f'class="hm-cell-txt" text-anchor="middle" '
                    f'fill="var(--muted)">—</text>')
                continue
            frac = float(v) / vmax if vmax else 0.0
            op = 0.08 + 0.92 * max(0.0, min(1.0, frac))
            # Ô đậm -> chữ dùng màu nền để đủ tương phản
            fill = "var(--surface)" if op > 0.6 else "var(--ink-2)"
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell - 2}" height="{cell - 2}" '
                f'rx="3" fill="var(--c-{color_idx})" opacity="{op:.2f}">'
                f'<title>{_esc(r)} × {_esc(cols[j])}: {_fmt(float(v))}{_esc(unit)}'
                f'</title></rect>'
                f'<text x="{x + (cell - 2) / 2:.1f}" y="{y + cell / 2 + 3:.1f}" '
                f'class="hm-cell-txt" text-anchor="middle" fill="{fill}">'
                f'{_fmt(float(v))}</text>')

    ttl = f'<div class="chart-title">{_esc(title)}</div>' if title else ""
    return (f'<div class="chart-heatmap">{ttl}'
            f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" '
            f'aria-label="{_esc(title or "ban do nhiet")}">'
            f'{"".join(parts)}</svg></div>')


def _is_nan(v: object) -> bool:
    """True nếu là NaN (float('nan') != chính nó)."""
    try:
        return v != v  # type: ignore[comparison-overlap]
    except Exception:  # noqa: BLE001
        return False


def _empty(size: int, msg: str) -> str:
    """Khối trống khi thiếu dữ liệu — vẫn giữ layout."""
    return (f'<div class="chart-empty" style="min-height:{size // 2}px">'
            f'{_esc(msg)}</div>')
