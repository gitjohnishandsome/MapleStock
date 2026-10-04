"""SQLite 資料庫：只存「每個商品每天的開高低收」(daily)，且只接受檔名含 OHLC 的 Excel。

時段 Excel（scrape_*.xlsx，20 頁原始價格）不進資料庫，只用來「產生 OHLC Excel」(make_ohlc_excel)。
"""
import os
import sqlite3
from datetime import datetime, time, timedelta

import pandas as pd

import capture
import catalog
import store

DATA_DIR = os.path.join(capture.ROOT, capture.load_config()["data_dir"])
DB_PATH = os.path.join(DATA_DIR, "maple.db")

DAILY_COLS = ["商品", "日期", "開盤價", "最高價", "最低價", "收盤價", "開盤時間", "收盤時間"]
REQUIRED = ["商品", "日期", "開盤價", "最高價", "最低價", "收盤價"]


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TABLE IF NOT EXISTS daily ("
                "item TEXT, date TEXT, open INTEGER, high INTEGER, low INTEGER, close INTEGER, "
                "open_time TEXT, close_time TEXT, PRIMARY KEY (item, date))")
    _migrate_old(con)
    _migrate_item_column(con)
    return con


def _default_item():
    items = capture.load_config().get("items") or []
    return items[0]["name"] if items else "未分類"


def _migrate_item_column(con):
    """舊版 daily 表沒有 item 欄位（只追蹤單一商品）：補上預設商品名稱，重建成 (item, date) 複合主鍵。"""
    cols = [r[1] for r in con.execute("PRAGMA table_info(daily)")]
    if "item" in cols:
        return
    con.execute("ALTER TABLE daily RENAME TO daily_old")
    con.execute("CREATE TABLE daily (item TEXT, date TEXT, open INTEGER, high INTEGER, low INTEGER, close INTEGER, "
                "open_time TEXT, close_time TEXT, PRIMARY KEY (item, date))")
    con.execute("INSERT INTO daily SELECT ?, date, open, high, low, close, open_time, close_time FROM daily_old",
                (_default_item(),))
    con.execute("DROP TABLE daily_old")
    con.commit()


def _migrate_old(con):
    """舊版資料庫存原始價格(prices 表)：轉成每日 OHLC 後移除。"""
    if not con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prices'").fetchone():
        return
    old = pd.read_sql_query("SELECT dt, price FROM prices", con)
    if not old.empty:
        item = _default_item()
        df = pd.DataFrame({"日期時間": pd.to_datetime(old["dt"]), "單位價格": old["price"]})
        for r in store.candles(df, "day").itertuples():
            con.execute("INSERT OR IGNORE INTO daily VALUES (?,?,?,?,?,?,?,?)",
                        (item, r.date, int(r.open), int(r.high), int(r.low), int(r.close),
                         _ts(r.open_time), _ts(r.close_time)))
    con.execute("DROP TABLE prices")
    con.commit()


def _ts(v, day=None):
    """轉成資料庫用的完整時間字串。v 可以是完整日期時間，或只有時間（HH:MM[:SS] 字串／time 物件，需帶 day）。"""
    if v is None or (not isinstance(v, (time, str)) and pd.isna(v)):
        return None
    if isinstance(v, time):
        return f"{day} {v:%H:%M:%S}"
    if isinstance(v, str):
        v = v.strip()
        if not v:
            return None
        if day and len(v) <= 8 and ":" in v and "-" not in v:  # 只有時間
            return f"{day} {pd.Timestamp(v):%H:%M:%S}"
    return f"{pd.Timestamp(v):%Y-%m-%d %H:%M:%S}"


def _hms(s):
    """日期時間欄 → 只留時間 HH:MM:SS 的字串（Excel 顯示用）。"""
    return pd.to_datetime(s).dt.strftime("%H:%M:%S")


# ---------- 由時段 Excel 產生 OHLC Excel（不進資料庫） ----------
def summarize_file(path, cfg=None):
    """單一時段 Excel 的摘要：總列數、可用列數、日期範圍、判定出的商品。"""
    cfg = cfg or capture.load_config()
    df = pd.read_excel(path)
    if "日期時間" not in df.columns or "單位價格" not in df.columns:
        return {"name": os.path.basename(path), "total": len(df), "usable": 0, "dmin": None, "dmax": None,
                "error": "缺少「日期時間」或「單位價格」欄位", "dates": [], "item": None}
    dt = pd.to_datetime(df["日期時間"], errors="coerce")
    ok = dt.notna() & pd.to_numeric(df["單位價格"], errors="coerce").notna()
    names = df.loc[ok, "道具名稱"].tolist() if "道具名稱" in df.columns else []
    item = catalog.detect(cfg, names)
    return {"name": os.path.basename(path), "total": len(df), "usable": int(ok.sum()),
            "dmin": dt[ok].min() if ok.any() else None, "dmax": dt[ok].max() if ok.any() else None, "error": None,
            "dates": sorted(store.trading_date(dt[ok]).dt.strftime("%Y-%m-%d").unique()),
            "item": item["name"] if item else None}


def ohlc_filename(c, item_name):
    """依商品與資料的日期範圍命名：單日 OHLC_商品_2026-10-03.xlsx，多日加上迄日。"""
    first, last = c["date"].iloc[0], c["date"].iloc[-1]
    return f"OHLC_{item_name}_{first}.xlsx" if first == last else f"OHLC_{item_name}_{first}_{last}.xlsx"


def make_ohlc_excel(scrape_paths, out_path, cfg=None):
    """合併所選時段 Excel，依日期算出每天開高低收，寫成 OHLC Excel。回傳天數。"""
    cfg = cfg or capture.load_config()
    df = store.load_files(scrape_paths)
    if df.empty:
        raise ValueError("所選檔案中沒有可用的日期時間與價格資料")
    item = catalog.detect(cfg, df["道具名稱"].tolist() if "道具名稱" in df.columns else [])
    if item is None:
        raise ValueError("讀到的道具名稱無法判定成單一商品（可能一個都沒對到，或同時對到多個商品／檔案混了不同商品），"
                          "請確認檔案內容，或檢查 config.yaml 的 items 設定")
    c = store.candles(df, "day")
    if len(c) > 1:  # 防呆：一份 OHLC 只能是同一天
        raise ValueError("所選資料包含不同日期：" + "、".join(c["date"]) + "\n同一份 OHLC 只能是同一天，請移除不同日期的檔案。")
    pd.DataFrame({"商品": item["name"], "日期": c["date"], "開盤價": c["open"], "最高價": c["high"], "最低價": c["low"],
                  "收盤價": c["close"], "開盤時間": _hms(c["open_time"]), "收盤時間": _hms(c["close_time"])}
                 ).to_excel(out_path, index=False)
    return len(c)


# ---------- 匯入 OHLC Excel ----------
def read_ohlc_excel(path):
    """讀取並驗證 OHLC Excel。檔名需含 OHLC，否則拒絕。回傳整理過的 DataFrame。"""
    name = os.path.basename(path)
    if "ohlc" not in name.lower():
        raise ValueError(f"檔名「{name}」不含 OHLC，拒絕匯入。\n只能匯入 OHLC Excel（檔名需含 OHLC）。")
    df = pd.read_excel(path)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"缺少欄位：{'、'.join(missing)}\n需要欄位：{'、'.join(DAILY_COLS)}")
    df = df.dropna(subset=REQUIRED).copy()
    if df.empty:
        raise ValueError("檔案中沒有可用的資料列")
    items = df["商品"].unique().tolist()
    if len(items) > 1:
        raise ValueError(f"檔案內有多個商品：{'、'.join(items)}\n同一份 OHLC 只能是同一個商品，請先整理後再匯入")
    df["日期"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")
    for col in ["開盤價", "最高價", "最低價", "收盤價"]:
        df[col] = df[col].astype(int)
    # 防呆：最高/最低需涵蓋開收
    df["最高價"] = df[["最高價", "開盤價", "收盤價"]].max(axis=1)
    df["最低價"] = df[["最低價", "開盤價", "收盤價"]].min(axis=1)
    for col in ["開盤時間", "收盤時間"]:
        if col not in df.columns:
            df[col] = None
    dup = df[df["日期"].duplicated(keep="last")]["日期"].unique().tolist()
    if dup:
        raise ValueError(f"檔案內有重複的日期：{'、'.join(dup)}，請先整理後再匯入")
    return df


def existing_dates(df):
    """df 內已存在於資料庫的日期（同一商品）；回傳排序後的 list。"""
    item = df["商品"].iloc[0]
    with connect() as con:
        have = {r[0] for r in con.execute("SELECT date FROM daily WHERE item = ?", (item,))}
    return sorted(d for d in df["日期"] if d in have)


def save_daily(df, skip_dates=()):
    """寫入資料庫（同商品同日期覆蓋）。skip_dates 內的日期略過。回傳寫入天數。"""
    skip = set(skip_dates)
    n = 0
    with connect() as con:
        for r in df.itertuples(index=False):
            if r.日期 in skip:
                continue
            con.execute("INSERT OR REPLACE INTO daily VALUES (?,?,?,?,?,?,?,?)",
                        (r.商品, r.日期, r.開盤價, r.最高價, r.最低價, r.收盤價,
                         _ts(r.開盤時間, r.日期), _ts(r.收盤時間, r.日期)))
            n += 1
    return n


# ---------- 讀取 / 匯出 ----------
def list_items():
    """資料庫裡目前有資料的商品名稱（排序後）。"""
    with connect() as con:
        return [r[0] for r in con.execute("SELECT DISTINCT item FROM daily ORDER BY item")]


def load_daily(item, days=None):
    """讀某商品每日 OHLC。days=None 全部，否則只取最近 days 天（含今天）。"""
    sql, args = "SELECT date, open, high, low, close, open_time, close_time FROM daily WHERE item = ?", [item]
    if days:
        start = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        sql, args = sql + " AND date >= ?", args + [start]
    with connect() as con:
        df = pd.read_sql_query(sql + " ORDER BY date", con, params=args)
    df["open_time"] = pd.to_datetime(df["open_time"])
    df["close_time"] = pd.to_datetime(df["close_time"])
    return df


def export_daily_excel(path, item):
    df = load_daily(item)
    pd.DataFrame({"商品": item, "日期": df["date"], "開盤價": df["open"], "最高價": df["high"], "最低價": df["low"],
                  "收盤價": df["close"], "開盤時間": _hms(df["open_time"]), "收盤時間": _hms(df["close_time"])}
                 ).to_excel(path, index=False)
    return len(df)


def count(item=None):
    with connect() as con:
        if item:
            return con.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM daily WHERE item = ?", (item,)).fetchone()
        return con.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM daily").fetchone()
