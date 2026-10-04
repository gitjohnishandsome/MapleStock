"""手動執行：更新頁面後自動翻頁擷取價格並輸出 Excel（當下的紀錄）。

防呆（任何一項不通過就立刻停止，不產生 Excel，只保留頁面截圖供檢查）：
  1. 頁碼驗證：更新後必須是第 1 頁；每次翻頁後頁碼必須 +1；總頁數不足則只抓到最後一頁
  2. 分頁驗證：第 1 頁必須讀得到日期時間（查詢分頁顯示「47小時」，不是市價分頁）
  3. 內容驗證：每頁畫面必須和上一頁不同
  4. 商品驗證：讀到的道具名稱必須比對到 config.yaml 的 items 清單，否則不知道要存成哪個商品

依比對到的商品，輸出到 data/<商品名稱>/<日期>/scrape_*.xlsx。
"""
import argparse
import os
import re
import sys
import time
from datetime import datetime

import cv2
import numpy as np
import pandas as pd
import pyautogui
import win32api

import capture
import catalog
import ocr

ESC = 0x1B
PAGE_RE = re.compile(r"(\d+)\s*[/／]\s*(\d+)")


class ScrapeError(Exception):
    pass


def esc_pressed():
    return bool(win32api.GetAsyncKeyState(ESC) & 0x8000)


def read_indicator(hwnd, cfg, expected=None, total=None):
    """OCR 讀頁碼「N / M」，回傳 (N, M)；讀不到回傳 None。

    頁碼常被 OCR 拆成兩個文字框（例如「5」被拆成單獨的「5」和誤讀的「6/20」）。
    若 expected 給定，且某個文字框單獨讀到的數字恰好等於 expected，優先採用它，
    避免只因另一個框誤讀了同一個數字就被判定成跳頁。
    """
    img = capture.grab(hwnd, cfg["page_roi"])
    texts = [t for _, _, t in ocr.read_lines(img)]
    found = []
    for text in texts:
        m = PAGE_RE.search(text)
        if m:
            found.append((int(m.group(1)), int(m.group(2))))
    if expected is not None:
        for text in texts:
            t = text.strip()
            if t.isdigit() and int(t) == expected:
                return expected, found[0][1] if found else total
    return found[0] if found else None


def same_image(a, b):
    return a.shape == b.shape and float(np.mean(cv2.absdiff(a, b))) < 0.5


def wait_for_page(hwnd, cfg, expected, tries=3, total=None):
    """等待頁碼變成 expected。回傳 (N, M) 或 None（讀不到頁碼）；頁碼不對時回傳讀到的值。"""
    got = None
    for _ in range(tries):
        got = read_indicator(hwnd, cfg, expected=expected, total=total)
        if got and got[0] == expected:
            return got
        time.sleep(0.7)
    return got


def click_next(hwnd, cfg, expected, total=None):
    """點下一頁並驗證頁碼變成 expected；沒變就重點（最多 2 次）。"""
    ox, oy = capture.client_origin(hwnd)
    nx, ny = cfg["next_button"]
    for attempt in range(3):
        pyautogui.click(ox + nx, oy + ny)
        time.sleep(cfg["page_wait"])
        got = wait_for_page(hwnd, cfg, expected, tries=2, total=total)
        if got is None:
            return None  # 讀不到頁碼：交給內容驗證
        if got[0] == expected:
            return got
        if got[0] > expected:
            raise ScrapeError(f"頁碼跳過了：預期第 {expected} 頁，卻讀到第 {got[0]} 頁（可能點了兩次）")
    raise ScrapeError(f"翻頁失敗：點了 3 次下一頁，頁碼仍是 {got[0]}（預期 {expected}）。"
                      "請檢查下一頁按鈕座標 next_button、視窗是否被擋住或遊戲是否卡住")


def scrape(hwnd, cfg, pages, refresh=True, page_dir=None):
    """回傳 (DataFrame, 判定出的商品)（全部驗證通過才回傳）；任何驗證失敗拋出 ScrapeError。"""
    if refresh:
        ox, oy = capture.client_origin(hwnd)
        sx, sy = cfg["search_box"]
        pyautogui.click(ox + sx, oy + sy)
        time.sleep(0.3)
        pyautogui.press("enter")
        print("已更新頁面（搜尋 +1 次），等待載入…")
        time.sleep(cfg["refresh_wait"])

    ind = wait_for_page(hwnd, cfg, 1, tries=4)
    if ind is None:
        print("⚠ 讀不到頁碼，改以「畫面是否變化」檢查翻頁（請確認 page_roi 位置正確）")
        total = None
    else:
        if ind[0] != 1:
            raise ScrapeError(f"更新頁面後應在第 1 頁，卻讀到第 {ind[0]} 頁。"
                              "請確認在「市價」分頁，且搜尋結果已載入")
        total = ind[1]
        if total < pages:
            print(f"實際只有 {total} 頁，將只抓 {total} 頁")
            pages = total

    rows, prev_img = [], None
    for p in range(1, pages + 1):
        if esc_pressed():
            raise ScrapeError("偵測到 ESC，已中止")
        if p > 1:
            click_next(hwnd, cfg, p, total=total)
        img = capture.grab(hwnd, cfg["table_roi"])
        if page_dir:
            cv2.imwrite(os.path.join(page_dir, f"page_{p:02d}.png"), img)
        if prev_img is not None and same_image(img, prev_img):
            raise ScrapeError(f"第 {p} 頁的畫面和第 {p - 1} 頁完全相同，翻頁沒有生效")
        prev_img = img

        got = ocr.parse_rows(img, cfg["name_x"], cfg["unit_x"], cfg["time_x"])
        if p == 1 and not any(r["日期時間"] is not None for r in got):
            raise ScrapeError("第 1 頁讀不到任何日期時間：看起來不是「市價」分頁"
                              "（查詢分頁的時間欄是「47小時」），或畫面不是拍賣行")
        for r in got:
            r["頁碼"] = p
        rows += got
        print(f"第 {p}/{pages} 頁：{len(got)} 列，待確認 {sum(r['待確認'] for r in got)} 列")

    item = catalog.detect(cfg, [r["道具名稱"] for r in rows])
    if item is None:
        raise ScrapeError("讀到的道具名稱無法判定成單一商品（可能一個都沒對到，或同時對到多個商品），"
                          "請確認搜尋結果，或檢查 config.yaml 的 items 設定")
    print(f"判定商品：{item['name']}")

    df = pd.DataFrame(rows, columns=["日期時間", "單位價格", "頁碼", "道具名稱", "原始文字", "待確認"])
    return df, item


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, help="覆寫 config 的頁數（測試可用 1）")
    ap.add_argument("--no-refresh", action="store_true", help="不先點搜尋框按 Enter 更新頁面")
    args = ap.parse_args()

    cfg = capture.load_config()
    pages = args.pages or cfg["pages"]
    hwnd = capture.find_window(cfg["window_title"])
    if not hwnd:
        sys.exit(f"找不到標題含「{cfg['window_title']}」的視窗；請用 capture.py --list 查詢並修改 config.yaml")

    data_dir = os.path.join(capture.ROOT, cfg["data_dir"])
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    page_dir = os.path.join(data_dir, "pages", stamp)
    os.makedirs(page_dir, exist_ok=True)

    print(f"{cfg['start_delay']} 秒後開始，ESC 可中止；滑鼠移到螢幕角落也會中止")
    time.sleep(cfg["start_delay"])
    capture.focus_window(hwnd)
    time.sleep(0.3)

    try:
        df, item = scrape(hwnd, cfg, pages, refresh=not args.no_refresh, page_dir=page_dir)
    except ScrapeError as e:
        print(f"\n✖ 已停止，未產生 Excel：{e}")
        print(f"  頁面截圖保留在：{page_dir}")
        sys.exit(1)

    if df.empty:
        sys.exit("沒有辨識到任何資料")
    ok = df[~df["待確認"]].sort_values("日期時間", na_position="last")
    out = pd.concat([ok, df[df["待確認"]]])
    day_dir = os.path.join(data_dir, item["name"], datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(day_dir, exist_ok=True)  # 當天資料夾已存在則不重建
    out_path = os.path.join(day_dir, f"scrape_{stamp}.xlsx")
    out.to_excel(out_path, index=False)
    print(f"已輸出: {out_path}（可用 {len(ok)} 列，待確認 {len(df) - len(ok)} 列）")


if __name__ == "__main__":
    main()
