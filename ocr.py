"""OCR：從表格截圖解析每一列的「日期時間」與「單位價格」。"""
import re
from datetime import datetime

import cv2
import numpy as np

_engine = None

DT_PATTERNS = [
    # 2026-10-03 09:15[:30]
    re.compile(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})日?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?"),
    # 10-03 09:15 （無年份）
    re.compile(r"()(\d{1,2})[-/.月](\d{1,2})日?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?"),
]
PRICE_RE = re.compile(r"\d[\d,]*(?:\.\d+)?\s*[萬万]?")


def engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


def preprocess(img):
    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    return img


def read_lines(img):
    """回傳 [(y中心, x中心, 文字)]，OCR 文字框（座標已換回原圖尺度）。"""
    res, _ = engine()(preprocess(img))
    items = []
    for box, text, _conf in res or []:
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append(((min(ys) + max(ys)) / 4, (min(xs) + max(xs)) / 4, text))
    return items


def group_rows(items, tol=30):
    """依 y 分列（表格每列約 60px 高，一列內有 2 行文字，故容差 30）。"""
    items = sorted(items, key=lambda i: i[0])
    rows, cur, anchor = [], [], None
    for it in items:
        if anchor is None or it[0] - anchor <= tol:
            cur.append(it)
            anchor = it[0] if anchor is None else anchor
        else:
            rows.append(cur)
            cur, anchor = [it], it[0]
    if cur:
        rows.append(cur)
    return rows


def parse_datetime(text):
    for pat in DT_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        y, mo, d, h, mi, s = m.groups()
        now = datetime.now()
        try:
            dt = datetime(int(y) if y else now.year, int(mo), int(d), int(h), int(mi), int(s or 0))
        except ValueError:
            continue
        if not y and dt > now:  # 無年份且在未來 -> 去年
            dt = dt.replace(year=now.year - 1)
        return dt, m.span()
    return None, None


def parse_price(text):
    nums = PRICE_RE.findall(text)
    if not nums:
        return None
    raw = nums[-1]
    mult = 10000 if re.search(r"[萬万]", raw) else 1
    try:
        return int(float(re.sub(r"[^\d.]", "", raw)) * mult)
    except ValueError:
        return None


def parse_rows(img, name_x, unit_x, time_x):
    """依欄位 x 範圍解析。回傳 list[dict(日期時間, 單位價格, 道具名稱, 原始文字, 待確認)]。"""
    out = []
    for row in group_rows(read_lines(img)):
        inc = lambda xr: [(y, t) for y, x, t in sorted(row) if xr[0] <= x < xr[1]]
        name = "".join(t for _, t in inc(name_x))
        unit_txt = " ".join(t for _, t in inc(unit_x))
        time_txt = " ".join(t for _, t in inc(time_x))
        # 單價欄第一行是數字(不含括號)；括號內為「萬」換算，略過
        first = re.sub(r"[（(].*", "", unit_txt)
        price = None
        m = re.search(r"\d[\d,]*", first)
        if m:
            price = int(m.group().replace(",", ""))
        dt, _ = parse_datetime(time_txt)
        out.append({
            "日期時間": dt,
            "單位價格": price,
            "道具名稱": name,
            "原始文字": f"{name} | {unit_txt} | {time_txt}",
            "待確認": price is None,
        })
    return out


if __name__ == "__main__":
    import sys
    import capture
    cfg = capture.load_config()
    for r in parse_rows(cv2.imread(sys.argv[1]), cfg["name_x"], cfg["unit_x"], cfg["time_x"]):
        print(r)
