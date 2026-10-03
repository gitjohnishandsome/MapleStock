"""K 線圖頁面：K 線（價格以「萬」顯示、缺漏日期留空、資料不完整標警告、可加官方等值線）＋ 每日數據表。
漲紅跌綠。
"""
import html

import pandas as pd
import plotly.graph_objects as go

import compare

UP, DOWN = "#e53935", "#2e7d32"
LATE_OPEN_HOUR = 12    # 開盤時間晚於此 → 可能漏了早上的資料
EARLY_CLOSE_HOUR = 18  # 收盤時間早於此 → 可能漏了晚上的資料


def wan(v, digits=2):
    """3300000 → '330萬'；328.9999 萬 → '329萬'；去掉多餘的 0。"""
    s = f"{v / 10000:,.{digits}f}".rstrip("0").rstrip(".")
    return s + "萬"


def _hm(v):
    return "" if v is None or pd.isna(v) else f"{pd.Timestamp(v):%H:%M}"


def prepare(c):
    """加上日期型別、前收、漲跌、振幅、資料不完整標記。"""
    d = c.copy()
    d["d"] = pd.to_datetime(d["date"])
    d = d.sort_values("d").reset_index(drop=True)
    d["prev_close"] = d["close"].shift(1)
    base = d["prev_close"].fillna(d["open"])
    d["chg"] = d["close"] - d["prev_close"]
    d["chg_pct"] = d["chg"] / d["prev_close"] * 100
    d["amp_pct"] = (d["high"] - d["low"]) / base * 100

    def flag(r):
        notes = []
        if pd.notna(r.open_time) and r.open_time.hour >= LATE_OPEN_HOUR:
            notes.append(f"開盤時間 {_hm(r.open_time)} 偏晚")
        if pd.notna(r.close_time) and r.close_time.hour < EARLY_CLOSE_HOUR:
            notes.append(f"收盤時間 {_hm(r.close_time)} 偏早")
        return "、".join(notes)

    d["warn"] = [flag(r) for r in d.itertuples()]
    return d


def missing_dates(d):
    if len(d) < 2:
        return []
    full = pd.date_range(d["d"].min(), d["d"].max(), freq="D")
    return [x for x in full if x not in set(d["d"])]


def build_fig(d, title, rate=None):
    div = 10000.0
    hover = []
    for r in d.itertuples():
        t = (f"{r.d:%Y-%m-%d}<br>開 {wan(r.open)}"
             + (f"（{_hm(r.open_time)}）" if _hm(r.open_time) else "")
             + f"<br>高 {wan(r.high)}<br>低 {wan(r.low)}<br>收 {wan(r.close)}"
             + (f"（{_hm(r.close_time)}）" if _hm(r.close_time) else ""))
        if pd.notna(r.chg):
            t += f"<br>漲跌 {'+' if r.chg >= 0 else ''}{wan(r.chg)}（{r.chg_pct:+.2f}%）"
        if r.warn:
            t += f"<br>⚠ 資料可能不完整：{r.warn}"
        hover.append(t)

    fig = go.Figure(go.Candlestick(
        x=d["d"], open=d["open"] / div, high=d["high"] / div, low=d["low"] / div, close=d["close"] / div,
        increasing_line_color=UP, decreasing_line_color=DOWN,
        increasing_fillcolor=UP, decreasing_fillcolor=DOWN,
        hoverinfo="text", text=hover, name="K 線"))

    bad = d[d["warn"] != ""]
    if len(bad):
        fig.add_trace(go.Scatter(
            x=bad["d"], y=bad["high"] / div, mode="text", text="⚠", textposition="top center",
            textfont=dict(size=16, color="#f9a825"), hoverinfo="skip", name="資料可能不完整"))

    if rate:
        each = compare.compare(rate, 1)["official_mesos_each"]
        fig.add_hline(y=each / div, line_dash="dash", line_color="#1e88e5",
                      annotation_text=f"官方管道等值 {wan(each)}／張（1億＝NT${rate:g}）",
                      annotation_position="top left", annotation_font_color="#1e88e5")

    span = (d["d"].max() - d["d"].min()).days
    fig.update_layout(title=title, xaxis_rangeslider_visible=False, height=620, showlegend=bool(len(bad)),
                      margin=dict(l=60, r=30, t=60, b=40), hovermode="closest")
    fig.update_yaxes(title_text="單價", ticksuffix="萬", tickformat=",.2~f")
    fig.update_xaxes(type="date", tickformat="%m/%d", dtick=86400000 if span <= 31 else None)
    return fig


def _td(text, v=None, cls="", title=""):
    attrs = f' data-v="{v}"' if v is not None else ""
    if cls:
        attrs += f' class="{cls}"'
    if title:
        attrs += f' title="{html.escape(title)}"'
    return f"<td{attrs}>{html.escape(str(text))}</td>"


def build_table(d):
    heads = [("日期", "s"), ("開", "n"), ("高", "n"), ("低", "n"), ("收", "n"),
             ("漲跌", "n"), ("漲跌 %", "n"), ("振幅 %", "n"), ("開盤時間", "s"), ("收盤時間", "s"), ("備註", "s")]
    th = "".join(f'<th data-t="{t}">{h}</th>' for h, t in heads)
    rows = []
    for r in d.sort_values("d", ascending=False).itertuples():
        cls = "" if pd.isna(r.chg) else ("up" if r.chg > 0 else "down" if r.chg < 0 else "")
        full = lambda v: f"{v:,.0f}"
        tds = [
            _td(f"{r.d:%Y-%m-%d}", f"{r.d:%Y-%m-%d}"),
            _td(wan(r.open), r.open, title=full(r.open)),
            _td(wan(r.high), r.high, title=full(r.high)),
            _td(wan(r.low), r.low, title=full(r.low)),
            _td(wan(r.close), r.close, cls, title=full(r.close)),
            _td("-" if pd.isna(r.chg) else f"{'+' if r.chg >= 0 else ''}{wan(r.chg)}", "" if pd.isna(r.chg) else r.chg, cls),
            _td("-" if pd.isna(r.chg_pct) else f"{r.chg_pct:+.2f}%", "" if pd.isna(r.chg_pct) else r.chg_pct, cls),
            _td(f"{r.amp_pct:.2f}%", r.amp_pct),
            _td(_hm(r.open_time) or "-", _hm(r.open_time)),
            _td(_hm(r.close_time) or "-", _hm(r.close_time)),
            _td(("⚠ " + r.warn) if r.warn else "", "", "warn" if r.warn else ""),
        ]
        rows.append("<tr>" + "".join(tds) + "</tr>")
    return f'<table id="t"><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


CSS = f"""
body{{font-family:-apple-system,"Microsoft JhengHei",sans-serif;margin:16px auto;max-width:1100px;color:#222;background:#fff}}
h2{{margin:8px 0}} .note{{color:#555;font-size:13px;margin:4px 0}} .gap{{color:#c62828;font-size:13px;margin:4px 0}}
table{{border-collapse:collapse;width:100%;font-size:14px;margin-top:8px}}
th,td{{border-bottom:1px solid #e0e0e0;padding:6px 10px;text-align:right;white-space:nowrap}}
th{{background:#f5f5f5;cursor:pointer;position:sticky;top:0}} th:hover{{background:#e8e8e8}}
td:first-child,th:first-child{{text-align:left}} td:last-child,th:last-child{{text-align:left}}
.up{{color:{UP}}} .down{{color:{DOWN}}} .warn{{color:#e65100}}
@media (prefers-color-scheme: dark){{
 body{{background:#1b1b1b;color:#e6e6e6}} .note{{color:#aaa}} th{{background:#2a2a2a}} th:hover{{background:#333}}
 th,td{{border-bottom-color:#3a3a3a}} }}
"""

JS = """
const tb=document.querySelector('#t tbody');
document.querySelectorAll('#t th').forEach((th,i)=>{let asc=false;th.addEventListener('click',()=>{
 asc=!asc;const num=th.dataset.t==='n';
 [...tb.rows].sort((a,b)=>{let x=a.cells[i].dataset.v??'',y=b.cells[i].dataset.v??'';
  if(num){x=x===''?-Infinity:+x;y=y===''?-Infinity:+y;return asc?x-y:y-x}
  return asc?x.localeCompare(y):y.localeCompare(x)}).forEach(r=>tb.appendChild(r));});});
"""


def build_html(c, title="突襲卷 K 線", rate=None):
    d = prepare(c)
    fig = build_fig(d, title, rate)
    gaps = missing_dates(d)
    gap_html = ""
    if gaps:
        shown = "、".join(f"{g:%m/%d}" for g in gaps[:20]) + (f" …共 {len(gaps)} 天" if len(gaps) > 20 else "")
        gap_html = f'<p class="gap">⚠ 以下日期沒有資料（圖上留空）：{shown}</p>'
    return (f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
            f"<style>{CSS}</style></head><body>"
            f'{gap_html}{fig.to_html(full_html=False, include_plotlyjs=True)}'
            f'<h2>每日數據</h2><p class="note">價格以「萬」顯示（滑鼠停在數字上看完整數字）。'
            f'漲跌＝收盤相較前一個有資料日的收盤；振幅＝（高−低）÷前收。點欄位標題可排序。'
            f'⚠＝開盤晚於 {LATE_OPEN_HOUR}:00 或收盤早於 {EARLY_CLOSE_HOUR}:00，當天資料可能不完整。</p>'
            f"{build_table(d)}<script>{JS}</script></body></html>")
