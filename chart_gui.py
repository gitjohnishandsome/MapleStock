"""K 線圖：直接讀資料庫，顯示近一週／近一個月／全部，並附每日數據表。"""
import os
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

import capture
import chart
import db


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("突襲卷 K 線圖")
        self.geometry("640x500")

        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status, padding=8, font=("", 10, "bold")).pack(fill="x")

        show = ttk.LabelFrame(self, text="顯示範圍", padding=8)
        show.pack(fill="x", padx=8, pady=4)
        self.scope = tk.StringVar(value="7")
        for text, val in [("近一週", "7"), ("近一個月", "30"), ("全部", "all")]:
            ttk.Radiobutton(show, text=text, variable=self.scope, value=val).pack(side="left", padx=6)

        line = ttk.LabelFrame(self, text="官方等值線（選填）", padding=8)
        line.pack(fill="x", padx=8, pady=4)
        ttk.Label(line, text="買幣價：1 億楓幣 = NT$").pack(side="left")
        self.rate = tk.StringVar()
        ttk.Entry(line, textvariable=self.rate, width=10).pack(side="left", padx=6)
        ttk.Label(line, foreground="#666",
                  text="填了會畫一條虛線＝官方管道每張換算的楓幣價；K 棒在線下＝拍賣行較便宜").pack(side="left")

        ttk.Button(self, text="產生 K 線圖", command=self.make).pack(pady=8)
        self.info = tk.Text(self, height=12, state="disabled")
        self.info.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        n, lo, hi = db.count()
        self.status.set(f"資料庫：{n} 天（{lo} ～ {hi}）" if n else "資料庫目前是空的，請先用「資料匯入」匯入 Excel")

    def log(self, text):
        self.info.config(state="normal")
        self.info.delete("1.0", "end")
        self.info.insert("end", text)
        self.info.config(state="disabled")

    def make(self):
        rate = None
        if self.rate.get().strip():
            try:
                rate = float(self.rate.get().replace(",", ""))
                if rate <= 0:
                    raise ValueError
            except ValueError:
                return messagebox.showwarning("提示", "買幣價請輸入正數，或留空不畫等值線")
        scope = self.scope.get()
        c = db.load_daily(None if scope == "all" else int(scope))
        if c.empty:
            n, lo, hi = db.count()
            hint = f"\n目前資料庫的資料範圍是 {lo} ～ {hi}，可改選「全部」。" if n else "\n資料庫是空的，請先用「資料匯入」匯入 Excel。"
            return messagebox.showwarning("提示", "這個範圍內沒有資料。" + hint)
        label = {"7": "近一週", "30": "近一個月", "all": "全部"}[scope]
        out = os.path.join(capture.ROOT, "kline.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(chart.build_html(c, f"突襲卷 K 線（{label}）", rate))
        d = chart.prepare(c)
        gaps = chart.missing_dates(d)
        lines = [f"{label}：{len(c)} 根 K 棒" + (f"，另加官方等值線（1e=NT${rate:g}）" if rate else ""), ""]
        for r in d.itertuples():
            lines.append(f"{r.d:%Y-%m-%d}  開 {chart.wan(r.open)}  高 {chart.wan(r.high)}  低 {chart.wan(r.low)}  "
                         f"收 {chart.wan(r.close)}" + (f"  ⚠ {r.warn}" if r.warn else ""))
        if gaps:
            lines += ["", "⚠ 沒有資料的日期：" + "、".join(f"{g:%m/%d}" for g in gaps[:20])]
        self.log("\n".join(lines))
        webbrowser.open(out)


if __name__ == "__main__":
    App().mainloop()
