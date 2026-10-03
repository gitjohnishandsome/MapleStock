"""比較「官方管道（台幣買 WC）」與「拍賣行（楓幣）」哪個取得突襲卷比較划算。

官方：OFFICIAL_TWD 元買 OFFICIAL_TICKETS 張（預設 1990 元 77 張）。
DC 行情：1 億楓幣 = P 台幣（手動貼上訊息，取換算成每 1 億後最高的價格）。
  m = 官方總價 / P        → 官方總價相當於 m 億楓幣
  官方每張楓幣成本 = m × 1e8 / 張數
  拍賣行每張成本   = 拍賣單價（楓幣），換成台幣 = 單價 / 1e8 × P
"""
import re

import capture

CFG = capture.load_config()
OFFICIAL_TWD = CFG.get("official_price_twd", 1990)
OFFICIAL_TICKETS = CFG.get("official_tickets", 77)
E8 = 100_000_000

# 例：「1e：750」「2e 1500」「1億=750」；數量(e/億)＋分隔＋台幣價
LINE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[eE億]\s*[:：=＝\-]?\s*(\d+(?:\.\d+)?)")


def parse_messages(text, limit=10):
    """解析貼上的訊息（取前 limit 個非空行）。回傳 [(原文, 每1億的台幣價 or None)]。"""
    out = []
    for line in [l for l in text.splitlines() if l.strip()][:limit]:
        m = LINE_RE.search(line)
        price = None
        if m and float(m.group(1)) > 0:
            price = float(m.group(2)) / float(m.group(1))  # 換算成每 1e
        out.append((line.strip(), price))
    return out


def best_rate(parsed):
    prices = [p for _, p in parsed if p]
    return max(prices) if prices else None


def latest_close_price():
    """資料庫中最新一天的收盤價。回傳 (價格, 日期字串) 或 (None, None)。"""
    import db
    df = db.load_daily()
    if df.empty:
        return None, None
    last = df.iloc[-1]
    return int(last["close"]), str(last["date"])


def compare(rate_per_e, auction_unit):
    """rate_per_e：1 億楓幣 = 幾元台幣；auction_unit：拍賣單價（楓幣）。"""
    m = OFFICIAL_TWD / rate_per_e
    official_mesos_total = m * E8
    official_mesos_each = official_mesos_total / OFFICIAL_TICKETS
    official_twd_each = OFFICIAL_TWD / OFFICIAL_TICKETS
    auction_twd_each = auction_unit / E8 * rate_per_e
    diff = (auction_unit - official_mesos_each) / official_mesos_each  # 負＝拍賣行較便宜
    return {
        "m": m, "official_mesos_total": official_mesos_total, "official_mesos_each": official_mesos_each,
        "official_twd_each": official_twd_each, "auction_twd_each": auction_twd_each,
        "auction_total_mesos": auction_unit * OFFICIAL_TICKETS, "diff": diff,
        "winner": "拍賣行（楓幣）" if diff < 0 else ("官方管道（WC）" if diff > 0 else "兩者相同"),
    }
