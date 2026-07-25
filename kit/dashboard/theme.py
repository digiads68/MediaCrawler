# -*- coding: utf-8 -*-
"""
Khung trang + CSS + JS dùng chung cho MỌI loại dashboard.

Một nơi duy nhất định nghĩa: bảng màu (đã kiểm định CVD sáng/tối), layout tab,
modal preview video, modal cấu hình n8n, và toàn bộ JS tương tác (lọc/sắp/chọn
nhiều/gửi n8n). Các profile (search/creator/video/overview) chỉ việc dựng nội
dung từng tab rồi gọi `page()`.
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from typing import Any

# Hành động nối n8n: (mã action, nhãn, mô tả tooltip).
N8N_ACTIONS: list[tuple[str, str, str]] = [
    ("download", "📥 Tải", "Tải video/ảnh gốc về kho"),
    ("transcribe", "🎙️ Voice→Text", "Bóc lời thoại (speech-to-text)"),
    ("analyze", "🧠 Phân tích ND", "Tóm tắt & phân tích nội dung bằng AI"),
    ("hook", "🪝 Phân tích Hook", "Mổ xẻ hook/mở đầu 3 giây"),
]

# Nhãn ngắn cho JS (modal preview dựng lại nút).
N8N_LABELS = {a: lbl for a, lbl, _ in N8N_ACTIONS}


def esc(v: object) -> str:
    """Escape an toàn để nhét vào HTML."""
    return html.escape(str(v), quote=True)


def page(*, title: str, eyebrow: str, subtitle: str,
         tabs: list[tuple[str, str]], panes: dict[str, str],
         meta: dict[str, Any] | None = None,
         nav_extra: str = "") -> str:
    """
    Dựng 1 trang dashboard tự chứa.

    tabs: [(mã_tab, nhãn)] theo thứ tự hiển thị; tab đầu là tab mặc định.
    panes: {mã_tab: html_nội_dung}.
    meta: {"generated", "sources": [...], "n8n_webhook", "note"}.
    nav_extra: HTML chèn thêm bên phải thanh tab (vd. bộ chọn kênh).
    """
    meta = meta or {}
    gen = meta.get("generated") or datetime.now().strftime("%d/%m/%Y %H:%M")
    sources = meta.get("sources", [])
    src_html = " · ".join(esc(s) for s in sources) if sources else "—"
    cfg = json.dumps({"webhook": meta.get("n8n_webhook", ""),
                      "labels": N8N_LABELS}, ensure_ascii=False)

    tab_btns = "".join(
        f'<button class="tab{" active" if i == 0 else ""}" data-tab="{esc(k)}">'
        f'{esc(lbl)}</button>' for i, (k, lbl) in enumerate(tabs))
    pane_html = "".join(
        f'<div class="tab-pane{" active" if i == 0 else ""}" data-pane="{esc(k)}">'
        f'{panes.get(k, "")}</div>' for i, (k, _) in enumerate(tabs))
    nav_right = f'<div class="tabs-extra">{nav_extra}</div>' if nav_extra else ""

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — DigiAds</title>
<style>{_CSS}</style></head>
<body><div class="wrap">
<header class="rpt-head">
  <div>
    <div class="eyebrow">{esc(eyebrow)}</div>
    <h1>{esc(title)}</h1>
    <div class="sub">{esc(subtitle)}</div>
  </div>
  <div class="head-right">
    <div class="meta">Tạo lúc <b>{esc(gen)}</b><br>{src_html}</div>
    <div class="head-tools">
      <button class="tool-btn" id="btn-n8n">⚙ Kết nối n8n</button>
      <button class="tool-btn" id="btn-theme" title="Sáng/Tối">◐</button>
    </div>
  </div>
</header>

<nav class="tabs" id="tabs">{tab_btns}{nav_right}</nav>
{pane_html}

<footer>Nguồn: MediaCrawler + DigiAds Kit · dữ liệu công khai, nghiên cứu nội bộ ·
creator ẩn danh theo Nghị định 13/2023. Hành động n8n chỉ chạy khi bạn tự cấu hình webhook.</footer>
</div>

<div class="modal" id="preview-modal"><div class="modal-box">
  <button class="modal-close" id="modal-close">✕</button>
  <div class="modal-media" id="modal-media"></div>
  <div class="modal-info" id="modal-info"></div>
  <div class="modal-acts" id="modal-acts"></div>
</div></div>

<div class="modal" id="n8n-modal"><div class="modal-box modal-box--sm">
  <button class="modal-close" id="n8n-close">✕</button>
  <h3>Kết nối n8n</h3>
  <p class="muted">Dán URL webhook n8n của bạn. Mỗi nút hành động sẽ POST JSON
  (action + thông tin video) tới webhook này. URL lưu tại trình duyệt.</p>
  <input type="url" id="n8n-url" class="n8n-input"
    placeholder="https://n8n.cua-ban.vn/webhook/mc-action">
  <div class="n8n-actions-cfg">
    <button class="tool-btn" id="n8n-save">Lưu</button>
    <button class="tool-btn" id="n8n-test">Gửi thử (ping)</button>
  </div>
  <p class="muted small">Workflow mẫu: <code>kit/n8n/WF_MC4_content_action.json</code></p>
</div></div>

<div class="toast" id="toast"></div>
<script>window.__MC_CFG__ = {cfg};</script>
<script>{_JS}</script>
</body></html>"""


# ===========================================================================
# CSS
# ===========================================================================
_CSS = """
:root{color-scheme:light;
 --page:#eceee7;--surface:#f7f8f3;--surface-2:#eef0ea;--ink:#16211f;--ink-2:#4b5850;
 --muted:#7c8880;--rule:#d7dbd1;--grid:#d7dbd1;--accent:#eb6834;--accent-ink:#1a0f08;
 --good:#0ca30c;--warn:#c98500;--bad:#c0392b;
 --c-1:#2a78d6;--c-2:#008300;--c-3:#e87ba4;--c-4:#eda100;--c-5:#1baf7a;--c-6:#4a3aa7;}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme=light])){
 --page:#0d1311;--surface:#121917;--surface-2:#17201d;--ink:#eef1ec;--ink-2:#c3ccc6;
 --muted:#85938c;--rule:#26332f;--grid:#26332f;--accent:#d95926;--accent-ink:#160d02;
 --good:#0ca30c;--warn:#c98500;--bad:#e05a4a;
 --c-1:#3987e5;--c-2:#008300;--c-3:#d55181;--c-4:#c98500;--c-5:#199e70;--c-6:#9085e9;}}
:root[data-theme=dark]{
 --page:#0d1311;--surface:#121917;--surface-2:#17201d;--ink:#eef1ec;--ink-2:#c3ccc6;
 --muted:#85938c;--rule:#26332f;--grid:#26332f;--accent:#d95926;--accent-ink:#160d02;
 --good:#0ca30c;--warn:#c98500;--bad:#e05a4a;
 --c-1:#3987e5;--c-2:#008300;--c-3:#d55181;--c-4:#c98500;--c-5:#199e70;--c-6:#9085e9;}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--page);color:var(--ink);
 font-family:"Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
 font-size:14px;line-height:1.45;padding:24px}
.wrap{max-width:1200px;margin:0 auto;display:flex;flex-direction:column;gap:16px}
.rpt-head{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;
 border-bottom:2px solid var(--accent);padding-bottom:12px;flex-wrap:wrap}
.eyebrow{font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--accent);font-weight:700}
.rpt-head h1{margin:4px 0 0;font-size:26px;font-weight:600;letter-spacing:-.01em;
 font-family:Charter,"Iowan Old Style","Palatino Linotype",Georgia,serif;text-wrap:balance}
.rpt-head .sub{margin-top:5px;color:var(--ink-2);font-size:13px;max-width:70ch}
.head-right{display:flex;flex-direction:column;align-items:flex-end;gap:8px}
.meta{text-align:right;color:var(--muted);font-size:12px}
.meta b{color:var(--ink-2)}
.head-tools{display:flex;gap:8px}
.tool-btn{background:var(--surface);border:1px solid var(--rule);border-radius:6px;
 padding:6px 12px;font-size:12px;color:var(--ink-2);cursor:pointer;font-family:inherit}
.tool-btn:hover{border-color:var(--accent);color:var(--accent)}
.tabs{display:flex;gap:4px;flex-wrap:wrap;align-items:center;position:sticky;top:0;z-index:20;
 background:var(--page);padding:6px 0;border-bottom:1px solid var(--rule)}
.tabs-extra{margin-left:auto;display:flex;gap:8px;align-items:center}
.tab{background:none;border:none;border-radius:6px 6px 0 0;padding:9px 15px;font-size:13px;
 color:var(--muted);cursor:pointer;font-family:inherit;font-weight:600;border-bottom:2px solid transparent}
.tab:hover{color:var(--ink)}
.tab.active{color:var(--accent);border-bottom-color:var(--accent);background:var(--surface)}
.tab-pane{display:none;flex-direction:column;gap:16px}
.tab-pane.active{display:flex}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.tiles--5{grid-template-columns:repeat(5,1fr)}
.tile{background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:13px 15px}
.t-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.t-value{font-size:22px;font-weight:600;margin-top:3px;font-family:Charter,Georgia,serif;text-wrap:balance}
.t-note{font-size:11.5px;color:var(--ink-2);margin-top:2px}
.panel{background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:16px 18px}
.panel h2{margin:0 0 4px;font-size:15px;font-weight:700}
.panel h3{margin:18px 0 8px;font-size:13px;font-weight:700;color:var(--ink-2)}
.panel-sub{font-size:12px;color:var(--muted);margin-bottom:14px;max-width:90ch}
.chart-grid-2{display:grid;grid-template-columns:1fr 1fr;gap:20px;align-items:start}
.chart-grid-3{display:grid;grid-template-columns:1fr 1fr 1.1fr;gap:20px;align-items:start}
.chart-title{font-size:12px;color:var(--ink-2);font-weight:600;margin-bottom:8px}
.chart-empty{display:flex;align-items:center;justify-content:center;color:var(--muted);
 font-size:12px;background:var(--surface-2);border-radius:6px;min-height:120px;padding:16px;text-align:center}
.donut-wrap{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.donut-total{font-size:20px;font-weight:700;fill:var(--ink);font-family:Charter,Georgia,serif}
.donut-unit{font-size:10px;fill:var(--muted)}
.donut-legend{display:flex;flex-direction:column;gap:5px;min-width:110px}
.lg-row{display:flex;align-items:center;gap:7px;font-size:12px}
.lg-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0}
.lg-label{color:var(--ink-2);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lg-val{font-weight:700;font-variant-numeric:tabular-nums}
.hb-row{display:grid;grid-template-columns:130px 1fr 62px;gap:8px;align-items:center;margin:7px 0}
.hb-label{font-size:12px;color:var(--ink-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hb-track{height:13px;background:var(--surface-2);border-radius:3px;overflow:hidden}
.hb-fill{display:block;height:100%;border-radius:3px}
.hb-val{font-size:12px;text-align:right;font-variant-numeric:tabular-nums;color:var(--ink)}
.ax{fill:var(--muted);font-size:10px}
.endlbl{font-size:10.5px;font-weight:700}
.tbl-wrap{overflow-x:auto;margin-top:14px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.03em;color:var(--muted);
 font-weight:600;padding:0 10px 6px 0;border-bottom:1px solid var(--rule);white-space:nowrap}
td{padding:7px 10px 7px 0;border-bottom:1px solid var(--rule);color:var(--ink-2);vertical-align:middle}
tr:last-child td{border-bottom:none}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.wide{max-width:380px}
a{color:var(--accent);text-decoration:none;font-weight:600}
a:hover{text-decoration:underline}
.muted{color:var(--muted)}
.small{font-size:11px}
.tbl-more{font-size:11.5px;margin:10px 0 0}
.chip{display:inline-block;padding:2px 9px;border-radius:11px;font-size:11px;font-weight:700}
.chip-good{background:var(--good);color:#fff}
.chip-warn{background:var(--warn);color:#160d02}
.chip-bad{background:var(--bad);color:#fff}
.chip-muted{background:var(--surface-2);color:var(--muted);border:1px solid var(--rule)}
.minibar{display:inline-block;width:56px;height:8px;background:var(--surface-2);border-radius:3px;
 overflow:hidden;vertical-align:middle}
.minibar>span{display:block;height:100%;background:var(--c-5)}
footer{border-top:1px solid var(--rule);padding-top:11px;font-size:11px;color:var(--muted)}
/* callout */
.callout{background:var(--surface-2);border-left:3px solid var(--accent);border-radius:0 6px 6px 0;
 padding:11px 14px;font-size:12.5px;color:var(--ink-2);margin:12px 0}
.callout b{color:var(--ink)}
.callout--warn{border-left-color:var(--warn)}
/* insight list */
.insights{display:flex;flex-direction:column;gap:8px;margin:0;padding:0;list-style:none}
.insights li{background:var(--surface-2);border:1px solid var(--rule);border-radius:6px;
 padding:9px 12px;font-size:12.5px;color:var(--ink-2)}
.insights li b{color:var(--ink)}
.ins-tag{display:inline-block;font-size:10px;font-weight:700;text-transform:uppercase;
 letter-spacing:.04em;color:var(--accent);margin-right:6px}
/* benchmark bullet */
.bullet-row{display:grid;grid-template-columns:120px 1fr 76px;gap:9px;align-items:center;margin:9px 0}
.bullet-track{position:relative;height:16px;background:var(--surface-2);border-radius:3px}
.bullet-fill{position:absolute;top:0;bottom:0;left:0;border-radius:3px;background:var(--c-1);opacity:.75}
.bullet-mark{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ink)}
.bullet-label{font-size:12px;color:var(--ink-2)}
.bullet-val{font-size:12px;text-align:right;font-variant-numeric:tabular-nums}
/* heatmap */
.hm{border-collapse:separate;border-spacing:2px;font-size:11px}
.hm td,.hm th{border:none;padding:0}
.hm th{font-size:9.5px;color:var(--muted);text-align:center;padding:0 0 3px}
.hm th.row{text-align:right;padding-right:6px;width:34px}
.hm-cell{width:26px;height:20px;border-radius:3px;text-align:center;color:var(--ink);
 font-variant-numeric:tabular-nums;font-size:10px}
.hm-legend{display:flex;gap:8px;align-items:center;font-size:11px;color:var(--muted);margin-top:10px}
.hm-sw{display:inline-block;width:14px;height:11px;border-radius:2px}
/* matrix */
.mx td.lbl{color:var(--ink-2);white-space:nowrap;font-weight:600}
.mx-cell{text-align:center;border-radius:3px;font-variant-numeric:tabular-nums;font-size:11.5px;
 padding:5px 7px;color:var(--ink)}
/* toolbar + media grid */
.grid-toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
.mg-search{flex:1;min-width:170px;background:var(--surface);border:1px solid var(--rule);
 border-radius:6px;padding:8px 11px;font-size:12.5px;color:var(--ink);font-family:inherit}
.mg-search::placeholder{color:var(--muted)}
.mg-sort,.mg-pick{background:var(--surface);border:1px solid var(--rule);border-radius:6px;
 padding:8px 11px;font-size:12.5px;color:var(--ink);font-family:inherit}
.chip-row{display:flex;gap:6px;flex-wrap:wrap}
.fchip{background:var(--surface);border:1px solid var(--rule);border-radius:12px;padding:5px 12px;
 font-size:11.5px;color:var(--ink-2);cursor:pointer;font-family:inherit;white-space:nowrap}
.fchip.active{background:var(--accent);color:var(--accent-ink);border-color:var(--accent);font-weight:700}
.bulk-bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;background:var(--surface);
 border:1px solid var(--rule);border-radius:8px;padding:8px 12px;margin-bottom:12px;font-size:12px}
.bulk-all{display:flex;gap:6px;align-items:center;color:var(--ink-2);cursor:pointer}
.bulk-count{color:var(--accent);font-weight:700}
.bulk-spacer{flex:1}
.bulk-label{color:var(--muted)}
.mcard-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
.mcard{background:var(--surface);border:1px solid var(--rule);border-radius:10px;overflow:hidden;
 display:flex;flex-direction:column}
.mcard.sel{outline:2px solid var(--accent)}
.mcard-thumb{position:relative;display:block;aspect-ratio:3/4;cursor:pointer;
 background:linear-gradient(135deg,var(--surface-2),var(--rule));overflow:hidden}
.mcard-thumb img{width:100%;height:100%;object-fit:cover;display:block}
.mcard-thumb--broken img{display:none}
.mcard-thumb--broken::before{content:"🎬";position:absolute;inset:0;display:flex;align-items:center;
 justify-content:center;font-size:34px;opacity:.35}
.mcard-play{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
 font-size:30px;color:#fff;background:rgba(0,0,0,0);opacity:0;transition:opacity .15s}
.mcard-thumb:hover .mcard-play{opacity:1;background:rgba(0,0,0,.32)}
.mcard-rank{position:absolute;top:6px;left:6px;background:rgba(0,0,0,.65);color:#fff;font-size:10.5px;
 font-weight:700;padding:2px 7px;border-radius:10px}
.mcard-score{position:absolute;top:6px;right:34px;background:var(--accent);color:var(--accent-ink);
 font-size:11px;font-weight:800;padding:2px 8px;border-radius:10px;font-variant-numeric:tabular-nums}
.mcard-badge{position:absolute;bottom:6px;left:6px;background:var(--good);color:#fff;font-size:10px;
 font-weight:800;padding:2px 8px;border-radius:10px}
.mcard-check{position:absolute;top:5px;right:6px;background:rgba(0,0,0,.5);border-radius:6px;
 padding:3px 4px;display:flex;cursor:pointer}
.mcard-check input{cursor:pointer;margin:0}
.mcard-body{padding:10px 12px 12px;display:flex;flex-direction:column;gap:7px;flex:1}
.mcard-tags{display:flex;gap:5px;flex-wrap:wrap}
.mcard-tags .tag{font-size:10px;border:1px solid var(--rule);border-radius:3px;padding:1px 6px;
 color:var(--ink-2);text-transform:uppercase;letter-spacing:.02em}
.mcard-tags .tag-kw{color:var(--accent);border-color:var(--accent)}
.mcard-tags .tag-plat{color:var(--c-1);border-color:var(--c-1);font-weight:700}
.mcard-hook{font-size:12.5px;color:var(--ink);margin:0;line-height:1.4;
 display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.mcard-stats{display:flex;gap:9px;flex-wrap:wrap;font-size:11.5px;color:var(--ink-2);
 font-variant-numeric:tabular-nums}
.mcard-rates{display:flex;gap:12px;font-size:11px;color:var(--muted);flex-wrap:wrap}
.mcard-rates b{color:var(--ink-2);font-variant-numeric:tabular-nums}
.mcard-meta{font-size:11px;color:var(--muted);display:flex;gap:4px;flex-wrap:wrap}
.mcard-meta a{color:var(--muted);font-weight:400}
.mcard-n8n{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-top:4px}
.n8n-btn{background:var(--surface-2);border:1px solid var(--rule);border-radius:6px;padding:5px 6px;
 font-size:10.5px;color:var(--ink-2);cursor:pointer;font-family:inherit;white-space:nowrap;
 overflow:hidden;text-overflow:ellipsis}
.n8n-btn:hover{border-color:var(--accent);color:var(--accent);background:var(--surface)}
.mcard-actions{display:flex;gap:8px;margin-top:auto;padding-top:4px;align-items:center}
.btn-copy{background:var(--surface-2);border:1px solid var(--rule);border-radius:6px;padding:5px 9px;
 font-size:11px;color:var(--ink-2);cursor:pointer;font-family:inherit}
.btn-copy:hover{border-color:var(--accent);color:var(--accent)}
.mcard-open{margin-left:auto;background:var(--accent);color:var(--accent-ink);border-radius:6px;
 padding:5px 11px;font-size:11px;font-weight:700;text-decoration:none}
.bulk-act{padding:6px 10px;font-size:11.5px}
/* hook / example cards */
.ex-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px;margin-top:16px}
.ex-card{background:var(--surface-2);border:1px solid var(--rule);border-radius:8px;padding:11px 13px}
.ex-name{font-size:11px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:.03em}
.ex-title{font-size:12.5px;color:var(--ink);margin:6px 0;line-height:1.4}
.ex-meta{font-size:11px;color:var(--muted)}
/* comment / VoC */
.cmt{background:var(--surface-2);border:1px solid var(--rule);border-radius:8px;padding:10px 12px;
 margin-bottom:8px}
.cmt-text{font-size:12.5px;color:var(--ink);margin:0 0 5px;line-height:1.45}
.cmt-meta{font-size:11px;color:var(--muted);display:flex;gap:10px;flex-wrap:wrap}
.cmt-list{max-height:520px;overflow-y:auto;padding-right:4px}
/* creator pane */
.cpane{display:none}
.cpane.active{display:block}
/* modal */
.modal{position:fixed;inset:0;background:rgba(0,0,0,.6);display:none;align-items:center;
 justify-content:center;z-index:100;padding:20px}
.modal.open{display:flex}
.modal-box{background:var(--surface);border-radius:12px;max-width:760px;width:100%;max-height:90vh;
 overflow:auto;padding:20px;position:relative}
.modal-box--sm{max-width:440px}
.modal-close{position:absolute;top:12px;right:12px;background:var(--surface-2);border:1px solid var(--rule);
 border-radius:50%;width:30px;height:30px;cursor:pointer;color:var(--ink-2);font-size:14px;z-index:2}
.modal-media{width:100%;border-radius:8px;overflow:hidden;background:#000;margin-bottom:14px}
.modal-media img,.modal-media video{width:100%;display:block;max-height:60vh;object-fit:contain;background:#000}
.modal-info h3{margin:0 0 6px;font-size:16px}
.modal-info p{margin:4px 0;color:var(--ink-2);font-size:13px}
.modal-acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
.n8n-input{width:100%;background:var(--surface-2);border:1px solid var(--rule);border-radius:6px;
 padding:9px 11px;font-size:13px;color:var(--ink);font-family:inherit;margin:10px 0}
.n8n-actions-cfg{display:flex;gap:8px;margin-bottom:10px}
code{background:var(--surface-2);padding:1px 5px;border-radius:4px;font-size:11px}
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(80px);
 background:var(--ink);color:var(--page);padding:11px 20px;border-radius:8px;font-size:13px;
 opacity:0;transition:all .25s;z-index:200;max-width:80vw;text-align:center}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.toast.err{background:#c0392b;color:#fff}
@media(max-width:820px){.tiles,.tiles--5{grid-template-columns:repeat(2,1fr)}
 .chart-grid-2,.chart-grid-3{grid-template-columns:1fr}
 .mcard-grid{grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}
 .tabs-extra{margin-left:0;width:100%}}
"""

# ===========================================================================
# JS — hỗ trợ NHIỀU lưới thẻ trên cùng trang (mỗi lưới 1 [data-mgrid])
# ===========================================================================
_JS = r"""
(function(){
  var CFG = window.__MC_CFG__ || {webhook:"", labels:{}};
  var LS_URL = "mc_n8n_webhook", LS_THEME = "mc_theme";
  function $(id){return document.getElementById(id);}
  function webhook(){return localStorage.getItem(LS_URL) || CFG.webhook || "";}

  var toastT;
  function toast(msg, err){
    var t = $("toast"); t.textContent = msg;
    t.className = "toast show" + (err ? " err" : "");
    clearTimeout(toastT);
    toastT = setTimeout(function(){t.className = "toast";}, 2600);
  }

  var savedTheme = localStorage.getItem(LS_THEME);
  if(savedTheme){document.documentElement.setAttribute("data-theme", savedTheme);}
  $("btn-theme").addEventListener("click", function(){
    var cur = document.documentElement.getAttribute("data-theme");
    var next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem(LS_THEME, next);
  });

  $("tabs").addEventListener("click", function(e){
    var tab = e.target.closest(".tab"); if(!tab) return;
    var name = tab.getAttribute("data-tab");
    document.querySelectorAll(".tab").forEach(function(t){t.classList.remove("active");});
    document.querySelectorAll(".tab-pane").forEach(function(p){p.classList.remove("active");});
    tab.classList.add("active");
    var pane = document.querySelector('.tab-pane[data-pane="'+name+'"]');
    if(pane) pane.classList.add("active");
    window.scrollTo({top:0, behavior:"smooth"});
  });

  function openModal(id){$(id).classList.add("open");}
  function closeModal(id){$(id).classList.remove("open");}
  $("btn-n8n").addEventListener("click", function(){
    $("n8n-url").value = webhook(); openModal("n8n-modal");
  });
  $("n8n-close").addEventListener("click", function(){closeModal("n8n-modal");});
  $("n8n-save").addEventListener("click", function(){
    localStorage.setItem(LS_URL, $("n8n-url").value.trim());
    closeModal("n8n-modal"); toast("Đã lưu webhook n8n");
  });
  $("n8n-test").addEventListener("click", function(){
    localStorage.setItem(LS_URL, $("n8n-url").value.trim());
    send("ping", {note:"ping từ dashboard DigiAds"});
  });

  function send(action, payload){
    var url = webhook();
    if(!url){toast("Chưa cấu hình webhook n8n — bấm ⚙ Kết nối n8n", true);
      openModal("n8n-modal"); return;}
    var body = {action:action, payload:payload, source:"digiads-dashboard",
                ts:new Date().toISOString()};
    toast("Đang gửi: " + action + "…");
    fetch(url, {method:"POST", headers:{"Content-Type":"application/json"},
      mode:"cors", body:JSON.stringify(body)})
      .then(function(r){ if(!r.ok) throw new Error("HTTP " + r.status);
        toast("✓ Đã gửi '" + action + "' sang n8n"); })
      .catch(function(err){
        toast("Lỗi gửi n8n: " + err.message + " (kiểm tra URL/CORS)", true); });
  }

  // ---- mỗi lưới thẻ tự khởi tạo độc lập ----
  document.querySelectorAll("[data-mgrid]").forEach(function(root){
    var grid = root.querySelector(".mcard-grid");
    if(!grid) return;
    var search = root.querySelector(".mg-search");
    var sortSel = root.querySelector(".mg-sort");
    var chipRow = root.querySelector(".chip-row");
    var selAll = root.querySelector(".mg-selall");
    var countEl = root.querySelector(".bulk-count");
    var field = root.getAttribute("data-filter-field") || "format";
    var activeVal = "__all__";

    function apply(){
      var q = search ? (search.value||"").toLowerCase() : "";
      Array.prototype.forEach.call(grid.children, function(card){
        var v = card.getAttribute("data-" + field) || "";
        var hook = card.getAttribute("data-hook-lc")||"";
        var show = (activeVal==="__all__"||v===activeVal) && (!q||hook.indexOf(q)!==-1);
        card.style.display = show ? "" : "none";
      });
    }
    function sortBy(key){
      var cards = Array.prototype.slice.call(grid.children);
      cards.sort(function(a,b){
        return parseFloat(b.getAttribute("data-"+key)||0) - parseFloat(a.getAttribute("data-"+key)||0);
      });
      cards.forEach(function(c){grid.appendChild(c);});
    }
    function updateCount(){
      if(!countEl) return;
      countEl.textContent = grid.querySelectorAll(".mc-sel:checked").length + " đã chọn";
    }
    if(chipRow) chipRow.addEventListener("click", function(e){
      var chip = e.target.closest(".fchip"); if(!chip) return;
      Array.prototype.forEach.call(chipRow.children, function(c){c.classList.remove("active");});
      chip.classList.add("active");
      activeVal = chip.getAttribute("data-val"); apply();
    });
    if(search) search.addEventListener("input", apply);
    if(sortSel) sortSel.addEventListener("change", function(){sortBy(sortSel.value);});
    if(selAll) selAll.addEventListener("change", function(e){
      grid.querySelectorAll(".mcard").forEach(function(card){
        if(card.style.display==="none") return;
        var cb = card.querySelector(".mc-sel");
        if(cb){cb.checked = e.target.checked; card.classList.toggle("sel", e.target.checked);}
      });
      updateCount();
    });
    grid.addEventListener("change", function(e){
      var cb = e.target.closest(".mc-sel"); if(!cb) return;
      cb.closest(".mcard").classList.toggle("sel", cb.checked); updateCount();
    });
    grid.addEventListener("click", function(e){
      var copyBtn = e.target.closest(".btn-copy");
      if(copyBtn){
        var text = copyBtn.getAttribute("data-copy")||"";
        if(navigator.clipboard){navigator.clipboard.writeText(text).then(function(){
          var old = copyBtn.textContent; copyBtn.textContent = "✓";
          setTimeout(function(){copyBtn.textContent = old;}, 1400);});}
        return;
      }
      var n8nBtn = e.target.closest(".n8n-btn");
      if(n8nBtn){
        var card = n8nBtn.closest(".mcard");
        send(n8nBtn.getAttribute("data-action"), JSON.parse(card.getAttribute("data-payload")));
        return;
      }
      var thumb = e.target.closest(".mcard-thumb");
      if(thumb){openPreview(JSON.parse(thumb.getAttribute("data-preview"))); return;}
    });
    root.querySelectorAll(".bulk-act").forEach(function(btn){
      btn.addEventListener("click", function(){
        var sel = grid.querySelectorAll(".mc-sel:checked");
        if(!sel.length){toast("Chưa chọn video nào", true); return;}
        var items = [];
        sel.forEach(function(cb){
          items.push(JSON.parse(cb.closest(".mcard").getAttribute("data-payload")));});
        send(btn.getAttribute("data-action"), {batch:true, count:items.length, items:items});
      });
    });
  });

  // ---- bộ chọn kênh (profile creator) ----
  var cpick = document.getElementById("creator-pick");
  if(cpick){
    cpick.addEventListener("change", function(){
      var v = cpick.value;
      document.querySelectorAll(".cpane").forEach(function(p){
        p.classList.toggle("active", p.getAttribute("data-creator") === v);});
    });
  }

  // ---- modal preview ----
  function openPreview(p){
    var media = $("modal-media"), info = $("modal-info"), acts = $("modal-acts");
    var isVideo = p.media_type === "video";
    var mediaHtml;
    if(isVideo && p.download_url && /douyin|aweme|\.mp4|xhscdn|redcdn/.test(p.download_url)){
      mediaHtml = '<video src="'+p.download_url+'" poster="'+(p.cover_url||"")+
        '" controls playsinline preload="none"></video>';
    } else if(p.cover_url){ mediaHtml = '<img src="'+p.cover_url+'" alt="">';
    } else { mediaHtml = '<div style="padding:60px;text-align:center;color:#888">Không có preview</div>'; }
    media.innerHTML = mediaHtml;
    info.innerHTML = '<h3>'+escapeHtml(p.title||"(không tiêu đề)")+'</h3>'+
      '<p>'+escapeHtml(p.nickname||"")+' · '+escapeHtml(p.source_keyword||"")+
      ' · điểm trend '+Math.round(p.trend_score||0)+'</p>'+
      (p.content_url ? '<p><a href="'+p.content_url+'" target="_blank" rel="noopener">Mở bài gốc ↗</a></p>' : "");
    var btns = Object.keys(CFG.labels).map(function(a){
      return '<button class="n8n-btn" data-pa="'+a+'">'+CFG.labels[a]+'</button>';}).join("");
    acts.innerHTML = btns;
    acts.querySelectorAll(".n8n-btn").forEach(function(b){
      b.addEventListener("click", function(){send(b.getAttribute("data-pa"), p);});});
    openModal("preview-modal");
  }
  $("modal-close").addEventListener("click", function(){
    closeModal("preview-modal"); $("modal-media").innerHTML = "";});
  document.querySelectorAll(".modal").forEach(function(m){
    m.addEventListener("click", function(e){if(e.target===m){m.classList.remove("open");
      if(m.id==="preview-modal") $("modal-media").innerHTML="";}});});
  document.addEventListener("keydown", function(e){
    if(e.key==="Escape"){document.querySelectorAll(".modal.open").forEach(function(m){
      m.classList.remove("open");}); $("modal-media").innerHTML="";}});

  function escapeHtml(s){var d=document.createElement("div");d.textContent=s;return d.innerHTML;}
})();
"""
