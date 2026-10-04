"""武器製作成本計算機：選武器與製作數量 → 手動填每個材料的單價與現成武器單價 → 算總材料成本與盈餘。

材料名稱與每把需求數量來自 weapons.yaml（固定配方）；製作數量、單價、現成武器單價每次手動輸入時
自動存成 data/craft_calc.yaml（依武器、依材料名稱分開存），下次開啟同一把武器會自動帶出上次的數字，
可再調整。
"""
import os
import tkinter as tk
from tkinter import ttk

import yaml

import capture

ROOT = os.path.dirname(os.path.abspath(__file__))
WEAPONS_PATH = os.path.join(ROOT, "weapons.yaml")
SAVE_PATH = os.path.join(capture.ROOT, capture.load_config().get("data_dir", "data"), "craft_calc.yaml")

GOOD, BAD = "#e53935", "#2e7d32"  # 跟 chart.py 一致：紅＝划算（盈餘），綠＝不划算（虧損）


def load_weapons():
    with open(WEAPONS_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("weapons") or []


def load_saved():
    if not os.path.exists(SAVE_PATH):
        return {}
    try:
        with open(SAVE_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("武器製作成本計算機")
        self.geometry("560x560")

        self.weapons = load_weapons()
        self.saved = load_saved()  # {武器名稱: {quantity, market_price, prices: {材料名稱: 單價}}}
        self.price_rows = []  # [(材料名稱, 每把需求數量, StringVar 單價, 總需求數量 Label, 小計 Label)]

        pick = ttk.Frame(self, padding=10)
        pick.pack(fill="x")
        ttk.Label(pick, text="武器：").pack(side="left")
        self.weapon_name = tk.StringVar()
        self.weapon_box = ttk.Combobox(pick, textvariable=self.weapon_name, width=18, state="readonly",
                                        values=[w["name"] for w in self.weapons])
        self.weapon_box.pack(side="left")
        self.weapon_box.bind("<<ComboboxSelected>>", lambda _e: self.build_materials())

        ttk.Label(pick, text="  製作數量：").pack(side="left")
        self.quantity = tk.StringVar(value="1")
        qty_entry = ttk.Entry(pick, textvariable=self.quantity, width=6)
        qty_entry.pack(side="left")
        qty_entry.bind("<KeyRelease>", lambda _e: self.update_result())

        self.mat_frame = ttk.LabelFrame(self, text="材料（單價請自行查價後填入；總需求數量＝每把需求 × 製作數量）", padding=8)
        self.mat_frame.pack(fill="both", padx=10, pady=4)

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill="x")
        ttk.Label(bottom, text="現成武器單價：").pack(side="left")
        self.market_price = tk.StringVar()
        e = ttk.Entry(bottom, textvariable=self.market_price, width=16)
        e.pack(side="left", padx=6)
        e.bind("<KeyRelease>", lambda _e: self.update_result())

        self.result = tk.Text(self, height=7, state="disabled")
        self.result.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self.result.tag_configure("good", foreground=GOOD, font=("", 12, "bold"))
        self.result.tag_configure("bad", foreground=BAD, font=("", 12, "bold"))

        if not self.weapons:
            ttk.Label(self, foreground="#c62828",
                      text="weapons.yaml 裡沒有任何武器配方，請照格式加一筆").pack(padx=10)
            return
        self.weapon_name.set(self.weapons[0]["name"])
        self.build_materials()

    def current_weapon(self):
        name = self.weapon_name.get()
        return next((w for w in self.weapons if w["name"] == name), None)

    def build_materials(self):
        for child in self.mat_frame.winfo_children():
            child.destroy()
        self.price_rows = []
        w = self.current_weapon()
        if not w:
            return

        saved = self.saved.get(w["name"]) or {}
        saved_prices = saved.get("prices") or {}
        self.quantity.set(str(saved.get("quantity", "1")))
        self.market_price.set(str(saved.get("market_price", "")))

        heads = [("材料", 14), ("每把需求", 8), ("總需求數量", 10), ("單價", 10), ("小計", 12)]
        for col, (text, width) in enumerate(heads):
            ttk.Label(self.mat_frame, text=text, width=width, font=("", 9, "bold")).grid(row=0, column=col, pady=(0, 4))

        for row, m in enumerate(w["materials"], start=1):
            ttk.Label(self.mat_frame, text=m["name"]).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Label(self.mat_frame, text=f"{m['qty']:,}").grid(row=row, column=1)
            need_label = ttk.Label(self.mat_frame, text="0", anchor="e")
            need_label.grid(row=row, column=2)
            price_var = tk.StringVar(value=str(saved_prices.get(m["name"], "")))
            entry = ttk.Entry(self.mat_frame, textvariable=price_var, width=10)
            entry.grid(row=row, column=3, padx=4)
            entry.bind("<KeyRelease>", lambda _e: self.update_result())
            subtotal = ttk.Label(self.mat_frame, text="0", width=12, anchor="e")
            subtotal.grid(row=row, column=4)
            self.price_rows.append((m["name"], m["qty"], price_var, need_label, subtotal))

        self.update_result()

    @staticmethod
    def _num(s):
        s = s.replace(",", "").strip()
        try:
            v = float(s)
            return v if v >= 0 else 0.0
        except ValueError:
            return 0.0

    @staticmethod
    def _qty(s, default=1):
        """製作數量：無效或小於 1 就當成 1（正在輸入途中也不報錯）。"""
        s = s.replace(",", "").strip()
        try:
            v = int(float(s))
            return v if v >= 1 else default
        except ValueError:
            return default

    def update_result(self):
        count = self._qty(self.quantity.get())
        total = 0.0
        for name, qty, price_var, need_label, subtotal_label in self.price_rows:
            need = qty * count
            sub = need * self._num(price_var.get())
            total += sub
            need_label.config(text=f"{need:,}")
            subtotal_label.config(text=f"{sub:,.0f}")
        market_each = self._num(self.market_price.get())
        market_total = market_each * count
        profit = market_total - total

        self.result.config(state="normal")
        self.result.delete("1.0", "end")
        self.result.insert("end", f"製作數量：{count} 把\n\n")
        self.result.insert("end", f"總材料成本：{total:,.0f}\n")
        self.result.insert("end", f"現成武器總價：{market_total:,.0f}（單價 {market_each:,.0f} × {count}）\n\n")
        label, tag = ("盈餘（自己做比買現成划算）", "good") if profit >= 0 else ("虧損（買現成比較划算）", "bad")
        self.result.insert("end", f"{label}：{abs(profit):,.0f}", tag)
        self.result.config(state="disabled")

        self.save_current()

    def save_current(self):
        """把目前這把武器輸入的數字存檔，下次選到同一把武器會自動帶出來。"""
        w = self.current_weapon()
        if not w:
            return
        self.saved[w["name"]] = {
            "quantity": self.quantity.get(),
            "market_price": self.market_price.get(),
            "prices": {name: price_var.get() for name, qty, price_var, need_label, subtotal_label in self.price_rows},
        }
        try:
            os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
            with open(SAVE_PATH, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.saved, f, allow_unicode=True, sort_keys=False)
        except OSError:
            pass


if __name__ == "__main__":
    App().mainloop()
