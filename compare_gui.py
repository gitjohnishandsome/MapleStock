"""官方管道 vs 拍賣行：輸入「每 1 億楓幣 = NT$」與拍賣單價，比較哪個取得突襲卷比較划算。"""
import tkinter as tk
from tkinter import messagebox, ttk

import compare


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("突襲卷 取得方式比較")
        self.geometry("560x520")

        ttk.Label(self, padding=(10, 10, 10, 0), foreground="#666",
                  text=f"官方管道：NT${compare.OFFICIAL_TWD:,} 買 {compare.OFFICIAL_TICKETS} 張"
                       f"（每張 NT${compare.OFFICIAL_TWD / compare.OFFICIAL_TICKETS:.2f}）").pack(anchor="w")

        f = ttk.Frame(self, padding=10)
        f.pack(fill="x")
        ttk.Label(f, text="買幣價：1 億楓幣 = NT$").grid(row=0, column=0, sticky="w", pady=4)
        self.rate = tk.StringVar()
        e1 = ttk.Entry(f, textvariable=self.rate, width=14)
        e1.grid(row=0, column=1, padx=6)

        ttk.Label(f, text="拍賣行單價（楓幣）").grid(row=1, column=0, sticky="w", pady=4)
        self.auction = tk.StringVar()
        ttk.Entry(f, textvariable=self.auction, width=14).grid(row=1, column=1, padx=6)
        ttk.Button(f, text="讀取最新收盤價", command=self.load_auction).grid(row=1, column=2)
        self.note = ttk.Label(f, text="", foreground="#666")
        self.note.grid(row=2, column=1, columnspan=2, sticky="w", padx=6)

        ttk.Button(self, text="比較", command=self.run).pack(pady=4)
        self.out = tk.Text(self, height=16, state="disabled")
        self.out.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.out.tag_configure("good", foreground="#2e7d32", font=("", 11, "bold"))

        self.load_auction()
        e1.focus()
        self.bind("<Return>", lambda _e: self.run())

    def load_auction(self):
        price, day = compare.latest_close_price()
        if price:
            self.auction.set(str(price))
            self.note.config(text=f"來源：資料庫 {day} 的收盤價（可自行修改數字）")
        else:
            self.note.config(text="資料庫沒有 OHLC 資料，請手動輸入")

    def show(self, text, good=""):
        self.out.config(state="normal")
        self.out.delete("1.0", "end")
        self.out.insert("end", text)
        if good:
            self.out.insert("end", "\n" + good, "good")
        self.out.config(state="disabled")

    def run(self):
        try:
            rate = float(self.rate.get().replace(",", ""))
            unit = float(self.auction.get().replace(",", ""))
            if rate <= 0 or unit <= 0:
                raise ValueError
        except ValueError:
            return messagebox.showwarning("提示", "請輸入正數：買幣價（1 億楓幣 = NT$ 多少）與拍賣單價")
        r = compare.compare(rate, unit)
        n = compare.OFFICIAL_TICKETS
        text = (
            f"買幣價：1e = NT${rate:,.0f}\n"
            f"比率 m = {compare.OFFICIAL_TWD:,} ÷ {rate:,.0f} = {r['m']:.3f}\n"
            f"→ NT${compare.OFFICIAL_TWD:,} 約等於 {r['m']:.3f} 億楓幣（{r['official_mesos_total']:,.0f}）\n\n"
            f"【官方管道】{n} 張 = NT${compare.OFFICIAL_TWD:,}\n"
            f"  每張 NT${r['official_twd_each']:.2f}　≈　{r['official_mesos_each']:,.0f} 楓幣\n"
            f"【拍賣行】單價 {unit:,.0f} 楓幣\n"
            f"  每張　≈　NT${r['auction_twd_each']:.2f}　（{n} 張共 {r['auction_total_mesos']:,.0f} 楓幣）\n\n"
            f"拍賣行比官方管道{'貴' if r['diff'] > 0 else '便宜'} {abs(r['diff']) * 100:.1f}%\n")
        self.show(text, f"→ 目前較划算：{r['winner']}")


if __name__ == "__main__":
    App().mainloop()
