"""讀取多份 scrape Excel → 合併排序 → 計算 OHLC。

開盤 = 最早時間的價格；收盤 = 最晚時間的價格（同一時間有多筆時取最低價）；
最高/最低 = 所有資料中的最高/最低單位價格。
"""
import os

import pandas as pd


def load_files(paths):
    frames = []
    for p in paths:
        df = pd.read_excel(p)
        df["來源檔案"] = os.path.basename(p)
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["日期時間"] = pd.to_datetime(df["日期時間"], errors="coerce")
    df["單位價格"] = pd.to_numeric(df["單位價格"], errors="coerce")
    df = df.dropna(subset=["日期時間", "單位價格"])
    df = df.drop_duplicates(subset=["日期時間", "單位價格"])
    return df.sort_values(["日期時間", "單位價格"]).reset_index(drop=True)


def _ohlc(g):
    t0, t1 = g["日期時間"].min(), g["日期時間"].max()
    return {"open_time": t0, "close_time": t1,
            "open": g.loc[g["日期時間"] == t0, "單位價格"].min(),
            "close": g.loc[g["日期時間"] == t1, "單位價格"].min(),
            "high": g["單位價格"].max(), "low": g["單位價格"].min(), "rows": len(g)}


def candles(df, period="day"):
    """period: 'day' 每天一根；'all' 所選全部合併成一根。"""
    if df.empty:
        return pd.DataFrame()
    if period == "all":
        r = _ohlc(df)
        r["date"] = f"{df['日期時間'].min():%Y-%m-%d} ~ {df['日期時間'].max():%Y-%m-%d}"
        return pd.DataFrame([r])
    rows = []
    for d, g in df.groupby(df["日期時間"].dt.normalize()):
        r = _ohlc(g)
        r["date"] = f"{d:%Y-%m-%d}"
        rows.append(r)
    return pd.DataFrame(rows)
