"""讀取多份 scrape Excel → 合併排序 → 計算 OHLC。

開盤 = 當天最接近 9:00 的價格；收盤 = 當天最接近 24:00（午夜）的價格（時間差相同時取最低價）；
最高/最低 = 所有資料中的最高/最低單位價格。
"""
import os

import pandas as pd

DAY_CUTOFF_HOUR = 1  # 凌晨 0~1 點的資料算前一天（熬夜玩到跨午夜也算同一天）


def trading_date(dt):
    """回傳「交易日」（午夜正規化）：凌晨 DAY_CUTOFF_HOUR 點前的時間算前一天。"""
    return (dt - pd.Timedelta(hours=DAY_CUTOFF_HOUR)).dt.normalize()


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


def _nearest(g, target):
    """g 內「日期時間」最接近 target 的那一列，回傳 (時間, 價格)；時間差相同取最低價。"""
    diff = (g["日期時間"] - target).abs()
    tied = g.loc[diff == diff.min()]
    price = tied["單位價格"].min()
    time = tied.loc[tied["單位價格"] == price, "日期時間"].iloc[0]
    return time, price


def _ohlc(g, open_day=None, close_day=None):
    if open_day is None:
        open_day = trading_date(g["日期時間"]).min()
    if close_day is None:
        close_day = trading_date(g["日期時間"]).max()
    open_time, open_price = _nearest(g, open_day + pd.Timedelta(hours=9))
    close_time, close_price = _nearest(g, close_day + pd.Timedelta(hours=24))
    return {"open_time": open_time, "close_time": close_time, "open": open_price, "close": close_price,
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
    for d, g in df.groupby(trading_date(df["日期時間"])):
        r = _ohlc(g, open_day=d, close_day=d)
        r["date"] = f"{d:%Y-%m-%d}"
        rows.append(r)
    return pd.DataFrame(rows)
