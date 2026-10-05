"""手動執行：OCR 資料夾裡既有的頁面截圖（page_*.png），不需要遊戲視窗，直接輸出 Excel。

適用情境：run_scrape.py 失敗中止時，部分頁面截圖仍保留在 data/pages/<時間戳記>/；
或想拿舊截圖重新跑一次 OCR（例如調整過 ocr.py 的解析規則）時，用這支補做紀錄。
"""
import argparse
import glob
import os
import re
import sys
from datetime import datetime

import cv2
import pandas as pd

import capture
import catalog
import ocr
import store

PAGE_NUM_RE = re.compile(r"(\d+)")


def page_num(path):
    m = PAGE_NUM_RE.search(os.path.basename(path))
    return int(m.group(1)) if m else 0


def scrape_from_images(img_dir, cfg):
    """讀資料夾內所有 page_*.png（依檔名數字排序），OCR 解析後回傳 (DataFrame, 判定出的商品)。"""
    paths = sorted(glob.glob(os.path.join(img_dir, "page_*.png")), key=page_num)
    if not paths:
        sys.exit(f"資料夾內沒有 page_*.png：{img_dir}")

    rows = []
    for path in paths:
        img = cv2.imread(path)
        if img is None:
            print(f"⚠ 讀取失敗，略過：{os.path.basename(path)}")
            continue
        got = ocr.parse_rows(img, cfg["name_x"], cfg["unit_x"], cfg["time_x"])
        p = page_num(path)
        for r in got:
            r["頁碼"] = p
        rows += got
        print(f"{os.path.basename(path)}：{len(got)} 列，待確認 {sum(r['待確認'] for r in got)} 列")

    item = catalog.detect(cfg, [r["道具名稱"] for r in rows])
    if item is None:
        sys.exit("讀到的道具名稱無法判定成單一商品（可能一個都沒對到，或同時對到多個商品），"
                  "請確認截圖內容，或檢查 config.yaml 的 items 設定")
    print(f"判定商品：{item['name']}")

    df = pd.DataFrame(rows, columns=["日期時間", "單位價格", "頁碼", "道具名稱", "原始文字", "待確認"])
    return df, item


def pick_folder():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    d = filedialog.askdirectory(title="選擇截圖資料夾（內含 page_*.png）",
                                 initialdir=os.path.join(capture.ROOT, "data", "pages"))
    root.destroy()
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", nargs="?", help="截圖資料夾（內含 page_*.png）；不給就跳出選擇視窗")
    args = ap.parse_args()

    img_dir = args.folder or pick_folder()
    if not img_dir:
        sys.exit("未選擇資料夾")

    cfg = capture.load_config()
    df, item = scrape_from_images(img_dir, cfg)
    if df.empty:
        sys.exit("沒有辨識到任何資料")

    ok = df[~df["待確認"]].sort_values("日期時間", na_position="last")
    out = pd.concat([ok, df[df["待確認"]]])

    data_dir = os.path.join(capture.ROOT, cfg["data_dir"])
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    day_dir = os.path.join(data_dir, item["name"], store.today_trading_date())
    os.makedirs(day_dir, exist_ok=True)
    out_path = os.path.join(day_dir, f"scrape_fromimg_{stamp}.xlsx")
    out.to_excel(out_path, index=False)
    print(f"已輸出: {out_path}（可用 {len(ok)} 列，待確認 {len(df) - len(ok)} 列）")


if __name__ == "__main__":
    main()
