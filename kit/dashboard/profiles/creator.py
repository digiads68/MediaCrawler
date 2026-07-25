# -*- coding: utf-8 -*-
"""
Dashboard **CREATOR MODE** — "Channel Audit": soi kênh đối thủ.

Câu hỏi nó trả lời:
  1. Kênh này mạnh yếu ra sao? Đăng bao lâu 1 bài? Đang lên hay chững?
  2. Bài nào bứt phá so với CHÍNH kênh đó — công thức trúng là gì?
  3. Kênh thắng bằng format nào, hook kiểu nào?
  4. So với các kênh khác trong tệp dữ liệu thì đứng đâu?

Có bộ chọn kênh: mỗi kênh 1 khối phân tích riêng, chọn trên thanh tab.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from kit.dashboard import analysis as A
from kit.dashboard import components as C
from kit.dashboard.adapters import PLATFORM_LABELS
from kit.dashboard.theme import esc, page
from kit.report import charts

TABS = [("compare", "🏁 So sánh kênh"), ("deep", "🔎 Soi từng kênh"),
        ("posts", "🎬 Thư viện bài"), ("cadence", "🗓 Nhịp đăng")]

# Số kênh dựng khối phân tích sâu (tránh file HTML phình quá).
MAX_DEEP = 8


def build(bundle: dict[str, Any], *, meta: dict | None = None) -> str:
    """Dựng dashboard Channel Audit."""
    df = bundle["content"]
    # So sánh với chính kênh -> thấy bài bứt phá của riêng kênh đó.
    df = A.add_outlier_ratio(df, by="creator_hash")
    lb = A.creator_leaderboard(df)
    # Soi sâu ưu tiên kênh có NHIỀU bài nhất — nhiều dữ liệu thì kết luận mới chắc.
    deep_order = (lb.sort_values(["n_posts", "eng_total"], ascending=False)
                    ["creator_hash"].head(MAX_DEEP) if len(lb) else [])
    profiles = [A.creator_profile(df, ch) for ch in deep_order]
    profiles = [p for p in profiles if p]

    nav = ""
    if profiles:
        opts = "".join(
            f'<option value="{esc(p["creator_hash"])}">{esc(p["nickname"])} '
            f'({PLATFORM_LABELS.get(p["platform"], p["platform"])} · '
            f'{p["n_posts"]} bài)</option>' for p in profiles)
        nav = (f'<label class="bulk-label" for="creator-pick">Kênh:</label>'
               f'<select id="creator-pick" class="mg-pick">{opts}</select>')

    panes = {
        "compare": _pane_compare(df, lb),
        "deep": _pane_deep(profiles),
        "posts": _pane_posts(df),
        "cadence": _pane_cadence(df, profiles),
    }
    n_ch = int(df["creator_hash"].replace("", pd.NA).nunique())
    return page(title="Channel Audit — Soi kênh đối thủ",
                eyebrow="DigiAds Kit · CREATOR MODE",
                subtitle=f"{n_ch} creator trong dữ liệu · {len(lb)} kênh đủ dữ liệu "
                         f"để phân tích (≥2 bài) · nhịp đăng, đà tăng, bài bứt phá",
                tabs=TABS, panes=panes, meta=meta, nav_extra=nav)


# ---------------------------------------------------------------------------

def _pane_compare(df: pd.DataFrame, lb: pd.DataFrame) -> str:
    if lb.empty:
        return C.panel("So sánh kênh",
                       '<p class="muted">Cần ít nhất 1 kênh có ≥2 bài. '
                       'Hãy cào thêm bằng <code>--type creator</code>.</p>')
    n_ch = len(lb)
    rising = lb[lb["velocity"] >= 1.3]
    best = lb.iloc[0]
    kpis = [
        {"label": "Kênh phân tích", "value": f"{n_ch}",
         "note": "có ≥2 bài trong tệp"},
        {"label": "Kênh đang tăng", "value": f"{len(rising)}",
         "note": "velocity ≥ 1.3×"},
        {"label": "Dẫn đầu tương tác", "value": esc(str(best["nickname"])),
         "note": f'{C.human(best["eng_total"])} tổng tương tác'},
        {"label": "Bài bứt phá", "value": f'{int(lb["n_breakouts"].sum())}',
         "note": "≥2× trung vị của chính kênh"},
    ]

    bar = charts.hbar([(str(r["nickname"]), float(r["eng_median"]))
                       for _, r in lb.head(10).iterrows()],
                      title="Tương tác trung vị mỗi bài (bền hơn tổng)", color_idx=6)

    rows = []
    for _, r in lb.iterrows():
        vel = float(r["velocity"])
        vchip = ("chip-good" if vel >= 1.3 else
                 "chip-warn" if vel >= 1.0 else "chip-muted")
        vlabel = ("đang tăng" if vel >= 1.3 else
                  "ổn định" if vel >= 1.0 else "chững lại")
        cad = (f'{r["cadence_days"]:.1f} ngày'
               if pd.notna(r["cadence_days"]) else "—")
        deu = float(r["consistency"])
        rows.append([
            esc(str(r["nickname"])),
            esc(PLATFORM_LABELS.get(r["platform"], r["platform"])),
            f'{int(r["n_posts"])}', cad,
            C.human(r["eng_median"]), C.human(r["eng_total"]),
            f'<span class="minibar"><span style="width:{deu * 100:.0f}%"></span></span>',
            f'{vel:.2f}×', f'{int(r["n_breakouts"])}',
            f'<span class="chip {vchip}">{vlabel}</span>'])
    tbl = C.table([("Kênh", False), ("Nền tảng", False), ("Bài", True),
                   ("Nhịp đăng", True), ("Eng trung vị", True),
                   ("Eng tổng", True), ("Độ đều", True), ("Velocity", True),
                   ("Bứt phá", True), ("Nhịp độ", False)], rows)

    ins = []
    if len(rising):
        ins.append(("Theo dõi sát", "Kênh đang tăng: <b>"
                    + "</b>, <b>".join(esc(str(x)) for x in rising["nickname"].head(3))
                    + "</b> — soi công thức mới của họ trước khi thị trường bắt kịp."))
    steady = lb[(lb["consistency"] >= 0.5) & (lb["n_posts"] >= 3)]
    if len(steady):
        ins.append(("Đáng học", f'<b>{esc(str(steady.iloc[0]["nickname"]))}</b> đều tay '
                    f'nhất (độ đều {steady.iloc[0]["consistency"]:.2f}) — quy trình sản '
                    f'xuất ổn định, đáng mô phỏng cách làm.'))
    fast = lb[lb["cadence_days"].notna()].sort_values("cadence_days")
    if len(fast):
        f0 = fast.iloc[0]
        ins.append(("Tần suất", f'<b>{esc(str(f0["nickname"]))}</b> đăng dày nhất '
                    f'(~{f0["cadence_days"]:.1f} ngày/bài) — nếu muốn cạnh tranh trực '
                    f'tiếp, cần năng lực sản xuất tương đương.'))

    return (C.tiles(kpis)
            + C.panel("Bảng so sánh kênh", bar + tbl,
                      sub="Độ đều = mức nhất quán tương tác. Velocity = tương tác "
                          "nửa sau kỳ / nửa đầu kỳ. Bứt phá = số bài vượt 2× trung "
                          "vị của chính kênh đó.")
            + C.panel("Việc nên làm ngay", C.insights(ins)))


def _pane_deep(profiles: list[dict]) -> str:
    if not profiles:
        return C.panel("Soi từng kênh",
                       '<p class="muted">Chưa có kênh nào đủ dữ liệu (cần ≥2 bài).</p>')
    blocks = []
    for i, p in enumerate(profiles):
        blocks.append(
            f'<div class="cpane{" active" if i == 0 else ""}" '
            f'data-creator="{esc(p["creator_hash"])}">{_deep_block(p)}</div>')
    hint = C.callout("Dùng ô <b>Kênh</b> ở thanh tab phía trên để đổi kênh cần soi.")
    return hint + "".join(blocks)


def _deep_block(p: dict) -> str:
    cad = f'{p["cadence_days"]:.1f} ngày' if p["cadence_days"] else "—"
    vel = p["velocity"]
    vlabel = ("đang tăng" if vel >= 1.3 else "ổn định" if vel >= 1.0 else "chững lại")
    kpis = [
        {"label": "Số bài", "value": f'{p["n_posts"]}', "note": p["span"]},
        {"label": "Eng trung vị/bài", "value": C.human(p["eng_median"]),
         "note": f'TB {C.human(p["eng_mean"])}'},
        {"label": "Nhịp đăng", "value": cad, "note": "trung vị giữa 2 bài"},
        {"label": "Đà tăng", "value": f"{vel:.2f}×", "note": vlabel},
        {"label": "Độ đều", "value": f'{p["consistency"]:.2f}',
         "note": "1.0 = rất nhất quán"},
    ]

    tl = C.timeline_posts(p["points"], baseline=p["eng_median"],
                          title="Tương tác từng bài theo thời gian "
                                "(điểm xanh lá = bứt phá ≥2× trung vị)")

    fmt_charts = (
        f'<div class="chart-grid-2">'
        f'<div>{charts.donut(p["format_mix"], title="Format kênh hay dùng", unit=" bài")}</div>'
        f'<div>{charts.hbar(p["format_perf"], title="Tương tác TB theo format", color_idx=5)}</div>'
        f'</div>')

    # Bài bứt phá — "công thức trúng"
    if p["breakouts"]:
        rows = [[f'<span class="chip chip-good">{b["ratio"]:.1f}×</span>',
                 esc(b["title"]), esc(b["format"]), esc(b["date"]),
                 C.human(b["eng"]),
                 (f'<a href="{esc(b["url"])}" target="_blank" rel="noopener">Mở ↗</a>'
                  if b["url"] else "—")] for b in p["breakouts"]]
        bo = C.table([("So kênh", False), ("Tiêu đề", False), ("Format", False),
                      ("Ngày", False), ("Eng", True), ("Link", False)], rows)
        bo_sub = ("Đây là những bài kênh này 'ăn' hơn hẳn mặt bằng của chính họ — "
                  "mổ 3 bài này là ra công thức trúng của kênh.")
    else:
        bo = ('<p class="muted">Kênh này không có bài nào vượt 2× trung vị của '
              'chính nó — hiệu suất khá đồng đều, không có cú viral riêng lẻ.</p>')
        bo_sub = ""

    # Bài tốt nhất / kém nhất
    cmp_rows = []
    for lbl, b in [("Tốt nhất", p["best_post"]), ("Kém nhất", p["worst_post"])]:
        if not b:
            continue
        cmp_rows.append([f'<b>{esc(lbl)}</b>', esc(b["title"]), esc(b["format"]),
                         C.human(b["like"]), C.human(b["save"]),
                         C.human(b["share"]), C.human(b["eng"])])
    cmp_tbl = C.table([("", False), ("Tiêu đề", False), ("Format", False),
                       ("Like", True), ("Save", True), ("Share", True),
                       ("Eng", True)], cmp_rows)

    # Hook style của kênh
    hooks = A.hook_performance(p["posts"])
    if hooks:
        hrows = [[esc(h["name"]), f'{h["n"]}', C.human(h["eng_median"]),
                  C.pct(h["win_rate"], 0)] for h in hooks[:6]]
        htbl = C.table([("Công thức hook", False), ("Số bài", True),
                        ("Eng trung vị", True), ("Tỷ lệ thắng", True)], hrows)
    else:
        htbl = '<p class="muted">Chưa nhận diện được công thức hook.</p>'

    ins = []
    if p["breakouts"]:
        b0 = p["breakouts"][0]
        ins.append(("Công thức trúng", f'Bài mạnh nhất của kênh là format '
                    f'<b>{esc(b0["format"])}</b> ({b0["ratio"]:.1f}× trung vị) — '
                    f'thử tái tạo cấu trúc này cho sản phẩm của mình.'))
    if p["format_perf"]:
        f0 = p["format_perf"][0]
        ins.append(("Format mạnh", f'Kênh hiệu quả nhất ở format <b>{esc(f0[0])}</b> '
                    f'({C.human(f0[1])} tương tác TB).'))
    if p["cadence_days"] and p["cadence_days"] > 14:
        ins.append(("Điểm yếu", f'Kênh đăng thưa (~{p["cadence_days"]:.0f} ngày/bài) — '
                    f'khe hở để mình chiếm sóng bằng tần suất cao hơn.'))
    if vel < 1.0:
        ins.append(("Cơ hội", "Kênh đang chững lại — khán giả của họ là tệp có thể "
                    "giành được nếu mình làm cùng chủ đề nhưng tươi hơn."))

    head = (f'<h2 style="margin:0 0 2px">{esc(p["nickname"])} '
            f'<span class="muted small">· '
            f'{esc(PLATFORM_LABELS.get(p["platform"], p["platform"]))}</span></h2>')
    thin = ""
    if p["n_posts"] < 4:
        thin = C.callout(
            f'Kênh này chỉ có <b>{p["n_posts"]} bài</b> trong dữ liệu — nhịp đăng, '
            f'độ đều và đà tăng chỉ mang tính tham khảo. Muốn kết luận chắc, cào '
            f'riêng kênh bằng <code>--type creator</code> để lấy đủ bài.', warn=True)

    return (f'<section class="panel">{head}'
            f'<div class="panel-sub">Chân dung kênh · {esc(p["span"])}</div>'
            f'{thin}{C.tiles(kpis, cols=5)}</section>'
            + C.panel("Diễn biến tương tác từng bài", tl,
                      sub="Chấm càng to = càng nhiều save. Chấm xanh lá là bài bứt phá.")
            + C.panel("Bài bứt phá — công thức trúng của kênh", bo, sub=bo_sub)
            + C.panel("Format & hook kênh dùng", fmt_charts + htbl)
            + C.panel("Bài tốt nhất vs kém nhất", cmp_tbl,
                      sub="So 2 đầu để thấy yếu tố tạo khác biệt.")
            + C.panel("Việc nên làm ngay", C.insights(ins)))


def _pane_posts(df: pd.DataFrame) -> str:
    top = df.sort_values("eng_total", ascending=False).head(60)
    note = C.callout(
        "Lọc theo <b>tên kênh</b> bằng hàng chip bên dưới. Nhãn <b>🚀 Bứt phá</b> "
        "so với trung vị của chính kênh đó. Chọn nhiều rồi gửi loạt sang n8n để "
        "tải + bóc lời + phân tích.")
    return C.panel("Thư viện bài của các kênh",
                   note + C.media_grid(top, grid_id="creator-posts",
                                       filter_field="nickname",
                                       badge_col="breakout", max_cards=60),
                   sub="Toàn bộ bài đã cào, sắp theo tương tác.")


def _pane_cadence(df: pd.DataFrame, profiles: list[dict]) -> str:
    heat = A.posting_heatmap(df, metric="count")
    hm = (C.heatmap(heat["matrix"], row_labels=heat["rows"], col_labels=heat["cols"],
                    title="Số bài theo khung giờ × thứ (toàn bộ kênh)", color_idx=6)
          if heat["matrix"] else
          '<div class="chart-empty">Không đủ dữ liệu thời gian</div>')

    rows = []
    for p in profiles:
        cad = f'{p["cadence_days"]:.1f}' if p["cadence_days"] else "—"
        per_week = (f'{7 / p["cadence_days"]:.1f}'
                    if p["cadence_days"] and p["cadence_days"] > 0 else "—")
        rows.append([esc(p["nickname"]), f'{p["n_posts"]}', esc(p["span"]),
                     cad, per_week])
    tbl = C.table([("Kênh", False), ("Số bài", True), ("Khoảng thời gian", False),
                   ("Ngày/bài", True), ("Bài/tuần", True)], rows)

    ins = []
    if heat.get("best"):
        b = heat["best"]
        caveat = (" (mẫu còn nhỏ, chỉ tham khảo)" if b.get("low_confidence") else "")
        ins.append(("Giờ đối thủ đăng", f'Khung <b>{esc(b["hour"])} {esc(b["dow"])}</b> '
                    f'là lúc đối thủ đăng nhiều nhất ({int(b["value"])} bài)'
                    f'{caveat} — có thể tránh giờ này để không bị chìm, hoặc đăng '
                    f'cùng giờ nếu đó là lúc khán giả online.'))
    ins.append(("Cách dùng", "Đối chiếu ngày/bài của đối thủ với năng lực sản xuất "
                "của team để đặt KPI tần suất thực tế."))

    return (C.panel("Đối thủ đăng vào lúc nào", hm + C.insights(ins))
            + C.panel("Tần suất xuất bản từng kênh", tbl,
                      sub="Nhịp đăng tính bằng trung vị số ngày giữa 2 bài liên tiếp "
                          "trong dữ liệu đã cào."))
