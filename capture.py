"""視窗偵測與擷取（win32gui 依標題找視窗，作法參考 MapleStory-Worlds-Artale- repo）。"""
import argparse
import os
import sys
from datetime import datetime

import mss
import numpy as np
import win32con
import win32gui
import yaml

import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # 避免 DPI 縮放造成座標/大小錯誤
except Exception:
    pass

sys.stdout.reconfigure(errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))


def load_config():
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_windows():
    out = []

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title.strip():
                out.append((hwnd, title))

    win32gui.EnumWindows(cb, None)
    return out


def find_window(title_part):
    key = title_part.lower()
    for hwnd, title in list_windows():
        if key in title.lower():
            return hwnd
    return None


def focus_window(hwnd):
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass


def client_origin(hwnd):
    """客戶區左上角的螢幕座標。"""
    return win32gui.ClientToScreen(hwnd, (0, 0))


def client_size(hwnd):
    l, t, r, b = win32gui.GetClientRect(hwnd)
    return r - l, b - t


def grab(hwnd, roi=None):
    """擷取視窗客戶區（或其中 ROI），回傳 BGR numpy 陣列。視窗需在最上層。"""
    ox, oy = client_origin(hwnd)
    if roi is None:
        w, h = client_size(hwnd)
        roi = [0, 0, w, h]
    x, y, w, h = roi
    with mss.MSS() as sct:
        shot = sct.grab({"left": ox + x, "top": oy + y, "width": w, "height": h})
    return np.ascontiguousarray(np.array(shot)[:, :, :3])


def main():
    import cv2

    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="列出所有視窗標題")
    ap.add_argument("--calibrate", action="store_true", help="存整個遊戲視窗截圖供量測座標")
    args = ap.parse_args()

    if args.list:
        for hwnd, title in list_windows():
            print(hwnd, title)
        return

    cfg = load_config()
    hwnd = find_window(cfg["window_title"])
    if not hwnd:
        sys.exit(f"找不到標題含「{cfg['window_title']}」的視窗，請用 --list 查標題並修改 config.yaml")
    focus_window(hwnd)
    import time
    time.sleep(0.5)
    print("找到視窗:", win32gui.GetWindowText(hwnd), "客戶區大小:", client_size(hwnd))

    if args.calibrate:
        focus_window(hwnd)
        import time
        time.sleep(0.5)
        os.makedirs(os.path.join(ROOT, cfg["data_dir"]), exist_ok=True)
        path = os.path.join(ROOT, cfg["data_dir"], "calibrate.png")
        cv2.imwrite(path, grab(hwnd))
        roi = cfg["table_roi"]
        img = grab(hwnd)
        x, y, w, h = roi
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 2)
        nx, ny = cfg["next_button"]
        cv2.circle(img, (nx, ny), 8, (0, 255, 0), 2)
        prev = os.path.join(ROOT, cfg["data_dir"], "calibrate_preview.png")
        cv2.imwrite(prev, img)
        print("已存:", path)
        print("已存(紅框=table_roi, 綠圈=next_button):", prev)


if __name__ == "__main__":
    main()
