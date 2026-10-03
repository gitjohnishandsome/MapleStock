"""產生假資料 Excel（放在 假資料/ 資料夾，不會進入真實資料庫）並輸出示範 K 線圖。"""
import os
import random
from datetime import datetime, timedelta

import pandas as pd

import chart
import store

random.seed(7)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "假資料")
os.makedirs(OUT, exist_ok=True)

LO, HI = 2_000_000, 4_000_000
days = [datetime(2026, 6, 1) + timedelta(days=3 * i) for i in range(20)]  # 6/1 ~ 7/28，共 20 天
price = 3_000_000
files = []
for day in days:
    for hour in (9, 23):  # 每天 2 份（早上、深夜）→ 共 40 份
        end = day.replace(hour=hour, minute=random.randint(0, 40))
        rows = []
        for i in range(140):  # 20 頁 × 7 列
            t = end - timedelta(minutes=i * 2 + random.randint(0, 1))
            price = int(min(HI, max(LO, price * random.uniform(0.985, 1.015) + (3_000_000 - price) * 0.01)))
            rows.append({"日期時間": t, "單位價格": price, "頁碼": i // 7 + 1, "道具名稱": "突襲額外獎勵票券",
                         "原始文字": "", "待確認": False})
        path = os.path.join(OUT, f"scrape_{end:%Y%m%d_%H%M}.xlsx")
        pd.DataFrame(rows).sort_values("日期時間").to_excel(path, index=False)
        files.append(path)

df = store.load_files(files)
c = store.candles(df, "day")
html = os.path.join(OUT, "假資料_kline.html")
chart.build(c, "突襲卷 K 線（假資料示範）").write_html(html)
print(f"{len(files)} 份 Excel，{len(df)} 筆，{len(c)} 根 K 棒")
print(c[["date", "open", "close", "high", "low"]].to_string(index=False))
print(html)
