# -*- coding: utf-8 -*-
"""
Dashboard **SEARCH MODE** — "Trend Radar": săn trend & lên ý tưởng content.

Câu hỏi nó trả lời:
  1. Ngách này đang ở mức nào? Bao nhiêu mới gọi là "bài tốt"? (benchmark P25→P90)
  2. Bài nào đáng bản địa hoá ngay? (vượt trội mấy lần trung vị ngách)
  3. Format nào thắng ở từ khoá nào — và còn khe trống nào chưa ai làm?
  4. Công thức hook nào THỰC SỰ hiệu quả (không chỉ nhiều người dùng)?
  5. Nên đăng vào giờ/thứ nào? Từ khoá nào là ngách vàng?
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from kit.dashboard import analysis as A
from kit.dashboard import components as C
from kit.dashboard.adapters import PLATFORM_LABELS
from kit.dashboard.metrics import mix, opportunity_map, timeline
from kit.dashboard.theme import esc, page
from kit.report import charts

TABS = [("bench", "📐 Ngách & Chuẩn"), ("top", "🔥 Video đáng clone"),
        ("matrix", "🧩 Format × Từ khoá"), ("hook", "🪝 Hook Lab"),
        ("time", "🧭 Thời điểm & Cơ hội")]

_BM_LABELS = {"liked_count": "Like", "collected_count": "Save",
              "share_count": "Share", "comment_count": "Bình luận",
              "eng_total": "Tổng tương tác"}


def build(bundle: dict[str, Any], *, meta: dict | None = None) -> str:
    """Dựng dashboard Trend Radar từ bundle đã nạp."""
    # So sánh TRONG từng nền tảng — thang tương tác giữa các nền tảng lệch xa nhau.
    df = A.add_outlier_ratio(bundle["content"], by="platform")
    bm = A.benchmark(df)
    fmx = A.format_matrix(df)
    hooks = A.hook_performance(df)
    heat = A.posting_heatmap(df, metric="eng")
    opp = opportunity_map(df)

    panes = {
        "bench": _pane_bench(df, bm, opp),
        "top": _pane_top(df, bm),
        "matrix": _pane_matrix(df, fmx),
        "hook": _pane_hook(hooks),
        "time": _pane_time(df, heat, opp),
    }
    kws = [k for k in df["source_keyword"].replace("", pd.NA).dropna().unique()]
    subtitle = ("Săn trend & lên ý tưởng content · từ khoá: "
                + ", ".join(str(k) for k in kws[:6]) if kws
                else "Săn trend & lên ý tưởng content")
    return page(title="Trend Radar — Săn trend & ý tưởng content",
                eyebrow="DigiAds Kit · SEARCH MODE",
                subtitle=subtitle, tabs=TABS, panes=panes, meta=meta)


# ---------------------------------------------------------------------------

def _pane_bench(df: pd.DataFrame, bm: dict, opp: list[dict]) -> str:
    n = len(df)
    creators = int(df["creator_hash"].replace("", pd.NA).nunique())
    eng_med = float(df["eng_total"].median())
    top10 = df.nlargest(max(1, n // 10), "eng_total")["eng_total"].sum()
    concentration = top10 / df["eng_total"].sum() if df["eng_total"].sum() else 0

    kpis = [
        {"label": "Bài trong ngách", "value": f"{n:,}",
         "note": f"{creators} creator khác nhau"},
        {"label": "Trung vị tương tác", "value": C.human(eng_med),
         "note": "toàn tệp (xem bảng theo nền tảng)"},
        {"label": "Top 10% giữ", "value": C.pct(concentration, 0),
         "note": "tổng tương tác — độ tập trung"},
        {"label": "Bài bứt phá", "value": f"{int(df['breakout'].sum())}",
         "note": f"≥ {A.BREAKOUT_X:.0f}× trung vị NỀN TẢNG của nó"},
    ]

    # Bảng benchmark
    rows = []
    for col, lb in _BM_LABELS.items():
        if col not in bm:
            continue
        q = bm[col]
        rows.append([esc(lb), C.human(q["p25"]), C.human(q["p50"]),
                     C.human(q["p75"]), C.human(q["p90"])])
    bench_tbl = C.table([("Chỉ số", False), ("P25 (yếu)", True), ("P50 (trung vị)", True),
                         ("P75 (tốt)", True), ("P90 (xuất sắc)", True)], rows)

    rate_rows = []
    for col, lb in [("save_rate", "Save/Like"), ("share_rate", "Share/Like")]:
        if col in bm:
            rate_rows.append([esc(lb), C.pct(bm[col]["p25"]), C.pct(bm[col]["p50"]),
                              C.pct(bm[col]["p75"]), C.pct(bm[col]["p90"])])
    rate_tbl = C.table([("Tỷ lệ", False), ("P25", True), ("P50", True),
                        ("P75", True), ("P90", True)], rate_rows) if rate_rows else ""

    # Mốc riêng từng nền tảng — thang tương tác lệch xa nhau nên phải tách.
    bmp = A.benchmark_by_platform(df)
    plat_tbl = ""
    if len(bmp) > 1:
        prows = [[esc(PLATFORM_LABELS.get(p, p)), f'{int(q["n"])}',
                  C.human(q["p50"]), C.human(q["p75"]), C.human(q["p90"])]
                 for p, q in sorted(bmp.items(), key=lambda x: -x[1]["p50"])]
        plat_tbl = ('<h3>Mốc riêng theo nền tảng (dùng cái này khi đặt KPI)</h3>'
                    + C.table([("Nền tảng", False), ("Số bài", True),
                               ("P50", True), ("P75", True), ("P90", True)], prows))

    ins = []
    if "eng_total" in bm:
        ins.append(("Mục tiêu", f"Bài mới nên nhắm <b>≥ {C.human(bm['eng_total']['p75'])}"
                    f"</b> tương tác để vào top 25% ngách; "
                    f"<b>{C.human(bm['eng_total']['p90'])}</b> là mức xuất sắc."))
    if "save_rate" in bm and bm["save_rate"]["p75"]:
        ins.append(("Save-rate", f"Ngách này save/like trung vị "
                    f"<b>{C.pct(bm['save_rate']['p50'])}</b> — dưới mức này nghĩa là "
                    f"nội dung chưa đủ 'đáng lưu', nên thêm giá trị tra cứu lại "
                    f"(checklist, bảng giá, tổng hợp)."))
    if concentration > 0.6:
        ins.append(("Cảnh báo", f"Top 10% bài đang giữ <b>{C.pct(concentration, 0)}</b> "
                    f"tổng tương tác — ngách phân hoá mạnh, bám công thức của nhóm "
                    f"dẫn đầu thay vì làm dàn trải."))
    gold = [o for o in opp if o["verdict"] == "ngách vàng"]
    if gold:
        ins.append(("Ngách vàng", "Ưu tiên từ khoá: <b>"
                    + "</b>, <b>".join(esc(g["keyword"]) for g in gold[:3])
                    + "</b> — ít bài mà tương tác trên trung vị."))

    charts_row = (f'<div class="chart-grid-2">'
                  f'<div>{charts.donut(mix(df, "platform", label_map=PLATFORM_LABELS), title="Nền tảng", unit=" bài")}</div>'
                  f'<div>{charts.hbar(mix(df, "source_keyword"), title="Số bài theo từ khoá", color_idx=4)}</div>'
                  f'</div>')

    return (C.tiles(kpis)
            + C.panel("Chuẩn của ngách — thế nào là 'bài tốt'?",
                      bench_tbl + rate_tbl + plat_tbl,
                      sub="Phân vị tính trên toàn bộ dữ liệu đã cào. Dùng P75 làm "
                          "KPI cho bài mới, P90 làm mốc 'ăn'. Khi trộn nhiều nền "
                          "tảng, hãy đặt KPI theo bảng riêng từng nền tảng bên dưới.")
            + C.panel("Việc nên làm ngay", C.insights(ins))
            + C.panel("Cơ cấu nguồn dữ liệu", charts_row))


def _pane_top(df: pd.DataFrame, bm: dict) -> str:
    top = df.sort_values("out_ratio", ascending=False).head(48)
    note = C.callout(
        "Thẻ có nhãn <b>🚀 Bứt phá</b> là bài vượt ≥ 2× trung vị của <b>chính nền "
        "tảng đó</b> — nhóm đáng bản địa hoá trước. Chỉ số <b>So ngách</b> trên mỗi "
        "thẻ cho biết bài hơn trung vị bao nhiêu lần. Chọn nhiều thẻ rồi bấm "
        "<b>Gửi loạt sang n8n</b> để tải + bóc lời + phân tích hook hàng loạt.")
    return C.panel("Video đáng nghiên cứu / bản địa hoá",
                   note + C.media_grid(top, grid_id="search-top",
                                       filter_field="format",
                                       badge_col="breakout"),
                   sub="Sắp theo mức vượt trội so với trung vị nền tảng, không phải "
                       "theo like tuyệt đối — tránh bị các kênh khủng át hết.")


def _pane_matrix(df: pd.DataFrame, fmx: dict) -> str:
    mx = C.matrix(fmx["cells"], rows=fmx["rows"], cols=fmx["cols"],
                  counts=fmx["counts"],
                  title="Tương tác TB theo Format × Từ khoá",
                  note="Ô càng đậm = format đó càng ăn ở từ khoá đó. Ô ít bài "
                       "(1–2) chỉ mang tính tham khảo.")
    # Hiệu quả từng format (TB + trung vị)
    rows = []
    if "format" in df.columns:
        g = (df.groupby("format")["eng_total"]
               .agg(["size", "mean", "median"])
               .sort_values("median", ascending=False))
        for f, r in g.iterrows():
            rows.append([esc(f), f'{int(r["size"])}', C.human(r["mean"]),
                         C.human(r["median"])])
    fmt_tbl = C.table([("Format", False), ("Số bài", True), ("Eng TB", True),
                       ("Eng trung vị", True)], rows)

    gap_items = []
    for g in fmx["gaps"]:
        gap_items.append(("Khe trống",
                          f'Format <b>{esc(g["format"])}</b> ở từ khoá '
                          f'<b>{esc(g["keyword"])}</b> đạt {C.human(g["eng"])} '
                          f'tương tác TB nhưng chỉ có <b>{g["n"]} bài</b> — '
                          f'cầu cao, cung thấp, nên thử ngay.'))
    if not gap_items:
        gap_items = [("Nhận xét", "Chưa thấy khe trống rõ rệt — các format đã "
                      "được khai thác khá đều ở mọi từ khoá.")]

    return (C.panel("Format nào thắng ở từ khoá nào", mx,
                    sub="Đây là bản đồ để chọn format khi làm content cho từng "
                        "từ khoá, thay vì đoán.")
            + C.panel("Khe trống nội dung — cơ hội làm trước đối thủ",
                      C.insights(gap_items))
            + C.panel("Xếp hạng format theo hiệu quả", fmt_tbl,
                      sub="Trung vị đáng tin hơn trung bình vì không bị 1 bài "
                          "viral kéo lệch."))


def _pane_hook(hooks: list[dict]) -> str:
    if not hooks:
        return C.panel("Hook Lab", '<p class="muted">Không đủ dữ liệu.</p>')
    rows = []
    for h in hooks:
        wr = h["win_rate"]
        chip = ("chip-good" if wr >= 0.35 else
                "chip-warn" if wr >= 0.2 else "chip-muted")
        rows.append([esc(h["name"]), f'{h["n"]}', C.human(h["eng_median"]),
                     C.human(h["eng_mean"]), C.pct(h["save_rate"]),
                     f'<span class="chip {chip}">{C.pct(wr, 0)}</span>'])
    tbl = C.table([("Công thức hook", False), ("Số bài", True),
                   ("Eng trung vị", True), ("Eng TB", True),
                   ("Save/Like TB", True), ("Tỷ lệ thắng", False)], rows)

    bar = charts.hbar([(h["name"], h["eng_median"]) for h in hooks],
                      title="Tương tác trung vị theo công thức hook", color_idx=1)

    best = hooks[0]
    ins = [("Ưu tiên", f'Công thức <b>{esc(best["name"])}</b> cho tương tác trung vị '
            f'cao nhất ({C.human(best["eng_median"])}) — dùng làm khung mặc định '
            f'cho batch content tới.')]
    win = max(hooks, key=lambda h: h["win_rate"])
    if win["name"] != best["name"]:
        ins.append(("Tỷ lệ thắng", f'<b>{esc(win["name"])}</b> có tỷ lệ vào top 25% '
                    f'cao nhất ({C.pct(win["win_rate"], 0)}) — ổn định nhất, ít rủi ro.'))
    weak = hooks[-1]
    if weak["n"] >= 5:
        ins.append(("Tránh", f'<b>{esc(weak["name"])}</b> đang kém nhất '
                    f'({C.human(weak["eng_median"])} trung vị) dù có {weak["n"]} bài — '
                    f'cân nhắc bỏ hoặc làm lại cách thể hiện.'))

    ex_cards = []
    for h in hooks[:6]:
        for e in h["examples"][:1]:
            link = (f'<a href="{esc(e["url"])}" target="_blank" rel="noopener">'
                    f'Mở ↗</a>' if e["url"] else "")
            ex_cards.append(
                f'<div class="ex-card"><div class="ex-name">{esc(h["name"])}</div>'
                f'<div class="ex-title">“{esc(e["title"])}”</div>'
                f'<div class="ex-meta">{C.human(e["eng"])} tương tác · {link}</div></div>')
    exs = f'<div class="ex-grid">{"".join(ex_cards)}</div>' if ex_cards else ""

    return (C.panel("Công thức hook nào thực sự hiệu quả", bar + tbl,
                    sub="Tỷ lệ thắng = % bài của công thức đó vào top 25% ngách. "
                        "Một công thức nhiều người dùng chưa chắc là công thức tốt.")
            + C.panel("Việc nên làm ngay", C.insights(ins))
            + C.panel("Hook mẫu tốt nhất mỗi nhóm", exs,
                      sub="Copy khung, đổi sản phẩm/bối cảnh sang tiếng Việt. "
                          "Bấm 🪝 trên thẻ video để AI mổ hook chi tiết."))


def _pane_time(df: pd.DataFrame, heat: dict, opp: list[dict]) -> str:
    hm = (C.heatmap(heat["matrix"], row_labels=heat["rows"],
                    col_labels=heat["cols"],
                    title="Tương tác TB theo khung giờ × thứ", color_idx=1)
          if heat["matrix"] else
          '<div class="chart-empty">Không đủ dữ liệu thời gian</div>')
    ins = []
    if heat.get("best"):
        b = heat["best"]
        if b.get("low_confidence"):
            ins.append(("Chưa đủ mẫu",
                        f'Khung cao nhất là <b>{esc(b["hour"])} {esc(b["dow"])}</b> '
                        f'({C.human(b["value"])}) nhưng chỉ dựa trên {b["n"]} bài — '
                        f'chưa đủ để kết luận giờ vàng, cần cào thêm dữ liệu.'))
        else:
            ins.append(("Giờ vàng", f'Khung <b>{esc(b["hour"])} {esc(b["dow"])}</b> cho '
                        f'tương tác TB cao nhất ({C.human(b["value"])}, {b["n"]} bài) — '
                        f'ưu tiên xếp lịch đăng vào đây.'))
    ins.append(("Lưu ý", "Giờ ở đây là giờ đăng gốc của nền tảng nguồn (Trung Quốc). "
                "Khi áp cho thị trường Việt, dịch múi giờ và kiểm chứng lại bằng "
                "chính dữ liệu kênh mình."))

    tl = timeline(df)
    line = (charts.line(tl["series"], tl["x_labels"],
                        title="Số bài mới theo tuần (12 tuần gần nhất)")
            if tl["series"] else
            '<div class="chart-empty">Không đủ dữ liệu thời gian</div>')

    verdict_cls = {"ngách vàng": "chip-good", "đông nhưng hot": "chip-warn",
                   "thử nghiệm": "chip-muted", "bão hoà": "chip-muted"}
    rows = [[esc(o["keyword"]), f'{o["volume"]}', C.human(o["eng"]),
             C.human(o["save"]),
             f'<span class="chip {verdict_cls.get(o["verdict"], "chip-muted")}">'
             f'{esc(o["verdict"])}</span>'] for o in opp]
    opp_tbl = C.table([("Từ khoá", False), ("Số bài", True), ("Eng TB", True),
                       ("Save TB", True), ("Đánh giá", False)], rows)

    return (C.panel("Nên đăng khi nào", hm + C.insights(ins))
            + C.panel("Nhịp ra bài của ngách", line,
                      sub="Ngách đang nóng lên hay nguội đi — quyết định có nên "
                          "dốc nguồn lực vào bây giờ.")
            + C.panel("Bản đồ cơ hội ngách",
                      C.scatter_opportunity(opp) + opp_tbl,
                      sub="Góc trên-trái = ít bài mà tương tác cao: vào trước, "
                          "ăn trước."))
