"""資料匯入：① 由時段 Excel 產生 OHLC Excel（先列出資料、確認後才匯出）② 匯入資料庫 ③ 匯出資料庫。"""
import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import capture
import db
import store

DATA = db.DATA_DIR
OHLC_DIR = os.path.join(DATA, "OHLC")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("資料匯入")
        self.geometry("900x780")
        self.files = []
        self.main_item = None
        self.cfg = capture.load_config()

        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status, padding=8, font=("", 10, "bold")).pack(fill="x")

        # ① 產生 OHLC
        mk = ttk.LabelFrame(self, text="① 由時段 Excel 產生 OHLC Excel（不進資料庫）", padding=8)
        mk.pack(fill="both", padx=8, pady=4)
        bar = ttk.Frame(mk)
        bar.pack(fill="x")
        ttk.Button(bar, text="選擇資料夾…", command=self.pick_folder).pack(side="left")
        ttk.Button(bar, text="重新讀取", command=self.reload).pack(side="left", padx=6)
        self.folder_var = tk.StringVar(value="尚未選擇資料夾（會讀取資料夾內所有 .xlsx 時段檔）")
        ttk.Label(bar, textvariable=self.folder_var, foreground="#666").pack(side="left", padx=6)

        cols = ("name", "item", "rows", "range")
        self.tree = ttk.Treeview(mk, columns=cols, show="headings", height=6, selectmode="extended")
        for c, t, w in [("name", "已匯入的檔案", 280), ("item", "判定商品", 160),
                        ("rows", "可用／總列數", 100), ("range", "資料時間範圍", 300)]:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        self.tree.tag_configure("bad", foreground="red")
        self.tree.pack(fill="x", pady=6)

        ttk.Label(mk, text="預覽：合併後每天的開高低收").pack(anchor="w")
        self.preview = tk.Text(mk, height=9, state="disabled")
        self.preview.tag_configure("red", foreground="red", font=("", 10, "bold"))
        self.preview.pack(fill="x")
        self.confirm = ttk.Button(mk, text="確認無誤，匯出 OHLC Excel", command=self.export_ohlc, state="disabled")
        self.confirm.pack(anchor="e", pady=(6, 0))

        # ② 匯入資料庫
        imp = ttk.LabelFrame(self, text="② 匯入資料庫（只接受檔名含 OHLC 的 Excel）", padding=8)
        imp.pack(fill="x", padx=8, pady=4)
        ttk.Button(imp, text="匯入 OHLC Excel…", command=self.import_ohlc).pack(side="left")
        ttk.Label(imp, foreground="#666", text="  日期重複時會跳出提醒，可選擇覆蓋或略過").pack(side="left")

        # ③ 匯出
        exp = ttk.LabelFrame(self, text="③ 匯出", padding=8)
        exp.pack(fill="x", padx=8, pady=4)
        ttk.Label(exp, text="商品：").pack(side="left")
        self.export_item = tk.StringVar()
        self.export_item_box = ttk.Combobox(exp, textvariable=self.export_item, width=20, state="readonly")
        self.export_item_box.pack(side="left", padx=(0, 10))
        ttk.Button(exp, text="匯出資料庫到 OHLC Excel…", command=self.export_daily).pack(side="left")
        ttk.Label(exp, foreground="#666", text="  可在 Excel 修正某天數字，再匯入（日期重複時選覆蓋）").pack(side="left")

        self.info = tk.Text(self, height=6, state="disabled")
        self.info.pack(fill="both", expand=True, padx=8, pady=8)
        self.update_status()

    # ---- 共用 ----
    def update_status(self):
        items = db.list_items()
        self.export_item_box["values"] = items
        if items and not self.export_item.get():
            self.export_item.set(items[0])
        n, lo, hi = db.count()
        self.status.set(f"資料庫：{len(items)} 個商品、共 {n} 天（{lo} ～ {hi}）" if n else "資料庫目前是空的")

    def log(self, text):
        self.info.config(state="normal")
        self.info.insert("end", text + "\n")
        self.info.see("end")
        self.info.config(state="disabled")

    def set_preview(self, text, red=""):
        self.preview.config(state="normal")
        self.preview.delete("1.0", "end")
        if red:
            self.preview.insert("end", red + "\n\n", "red")
        self.preview.insert("end", text)
        self.preview.config(state="disabled")

    # ---- ① ----
    folder = ""

    def pick_folder(self):
        d = filedialog.askdirectory(title="選擇時段 Excel 所在的資料夾", initialdir=DATA, mustexist=True)
        if d:
            self.folder = d
            self.reload()

    def reload(self):
        """讀取資料夾內所有 .xlsx（不含子資料夾；略過檔名含 OHLC 的檔案與 Excel 暫存檔）。"""
        if not self.folder:
            return messagebox.showinfo("提示", "請先選擇資料夾")
        self.folder_var.set(self.folder)
        self.files = sorted(
            os.path.join(self.folder, n) for n in os.listdir(self.folder)
            if n.lower().endswith(".xlsx") and not n.startswith("~$") and "ohlc" not in n.lower())
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        self.candles = None
        self.main_item = None
        self.confirm.config(state="disabled")
        sums = []
        for p in self.files:
            try:
                s = db.summarize_file(p, self.cfg)
            except Exception as e:  # noqa: BLE001
                s = {"name": os.path.basename(p), "total": 0, "usable": 0, "dmin": None, "dmax": None,
                     "error": str(e), "dates": [], "item": None}
            sums.append(s)

        # 防呆：所有資料必須是同一天、同一個商品；有問題的檔案標紅
        all_dates = sorted({d for s in sums for d in s["dates"]})
        date_mismatch = len(all_dates) > 1
        date_counts = {}
        for s in sums:
            for d in s["dates"]:
                date_counts[d] = date_counts.get(d, 0) + s["usable"]
        main_date = max(date_counts, key=date_counts.get) if date_counts else None

        all_items = sorted({s["item"] for s in sums if s["item"]})
        item_mismatch = len(all_items) > 1
        item_counts = {}
        for s in sums:
            if s["item"]:
                item_counts[s["item"]] = item_counts.get(s["item"], 0) + s["usable"]
        main_item = max(item_counts, key=item_counts.get) if item_counts else None
        no_item = [s["name"] for s in sums if s["usable"] and not s["item"]]

        problems = []
        for s in sums:
            rng = (f"{s['dmin']:%Y-%m-%d %H:%M} ～ {s['dmax']:%Y-%m-%d %H:%M}" if s["dmin"] is not None
                   else (s["error"] or "沒有可用資料"))
            bad = ((date_mismatch and any(d != main_date for d in s["dates"]))
                   or (item_mismatch and s["item"] and s["item"] != main_item)
                   or (s["usable"] and not s["item"]))
            self.tree.insert("", "end", values=(s["name"], s["item"] or "⚠ 無法判定", f"{s['usable']} / {s['total']}", rng),
                             tags=("bad",) if bad else ())
            if s["usable"] == 0:
                problems.append(s["name"])

        if not self.files:
            return self.set_preview("尚未選擇檔案")
        try:
            df = store.load_files(self.files)
            if df.empty:
                return self.set_preview("所選檔案中沒有可用的日期時間與價格資料")
            self.candles = store.candles(df, "day")
        except Exception as e:  # noqa: BLE001
            return self.set_preview(f"讀取失敗：{e}")

        lines = [f"商品：{main_item or '（無法判定）'}",
                 f"共 {len(self.files)} 份檔案、{len(df)} 筆價格（已去除重複）→ {len(self.candles)} 天", ""]
        lines += [f"{r.date}  開 {r.open:,.0f}  高 {r.high:,.0f}  低 {r.low:,.0f}  收 {r.close:,.0f}"
                  f"   （{r.open_time:%H:%M} ～ {r.close_time:%H:%M}）" for r in self.candles.itertuples()]
        if problems:
            lines += ["", "⚠ 以下檔案沒有可用資料：" + "、".join(problems)]

        red_lines = []
        if date_mismatch:
            bad_files = [s["name"] for s in sums if any(d != main_date for d in s["dates"])]
            red_lines.append("✖ 所選資料包含不同日期：" + "、".join(all_dates) + "\n"
                              "日期不同的檔案（清單中紅字）：" + "、".join(bad_files))
        if item_mismatch:
            bad_files = [s["name"] for s in sums if s["item"] and s["item"] != main_item]
            red_lines.append("✖ 所選資料包含不同商品：" + "、".join(all_items) + "\n"
                              "商品不同的檔案（清單中紅字）：" + "、".join(bad_files))
        if no_item:
            red_lines.append("✖ 以下檔案判定不出商品（可能是新商品還沒加進 config.yaml 的 items，"
                              "或搜尋結果不是預期的商品）：" + "、".join(no_item))
        if red_lines:
            red_lines.append("同一份 OHLC 只能是同一天、同一個商品，已禁止匯出。請移除有問題的檔案。")
            return self.set_preview("\n".join(lines), "\n".join(red_lines))

        self.main_item = main_item
        lines += ["", f"將儲存為：{os.path.join(OHLC_DIR, db.ohlc_filename(self.candles, main_item))}"]
        self.set_preview("\n".join(lines))
        self.confirm.config(state="normal")

    def export_ohlc(self):
        if self.candles is None or len(self.candles) != 1 or not self.main_item:
            return messagebox.showerror("拒絕匯出", "所選資料包含不同日期或不同商品，不能匯出。")
        out = os.path.join(OHLC_DIR, db.ohlc_filename(self.candles, self.main_item))
        if os.path.exists(out) and not messagebox.askyesno("檔案已存在", f"{os.path.basename(out)} 已存在，要覆蓋嗎？"):
            return
        os.makedirs(OHLC_DIR, exist_ok=True)
        try:
            days = db.make_ohlc_excel(self.files, out, self.cfg)
        except Exception as e:  # noqa: BLE001
            return messagebox.showerror("錯誤", str(e))
        self.log(f"已由 {len(self.files)} 份時段 Excel 產生「{self.main_item}」{days} 天的 OHLC：{out}")
        messagebox.showinfo("完成", f"已匯出：\n{out}\n\n可在下方「② 匯入資料庫」匯入。")

    # ---- ② ----
    def import_ohlc(self):
        path = filedialog.askopenfilename(title="選擇 OHLC Excel", initialdir=OHLC_DIR if os.path.isdir(OHLC_DIR) else DATA,
                                          filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        try:
            df = db.read_ohlc_excel(path)
        except Exception as e:  # noqa: BLE001
            return messagebox.showerror("無法匯入", str(e))
        item = df["商品"].iloc[0]
        dup = db.existing_dates(df)
        skip = ()
        if dup:
            shown = "、".join(dup[:15]) + (f" …等共 {len(dup)} 天" if len(dup) > 15 else "")
            ans = messagebox.askyesnocancel(
                "日期重複", f"商品「{item}」以下日期資料庫已經有資料：\n{shown}\n\n"
                           "是 ＝ 覆蓋這些日期\n否 ＝ 略過這些日期，只匯入新日期\n取消 ＝ 不匯入")
            if ans is None:
                return self.log("已取消匯入")
            if ans is False:
                skip = dup
        n = db.save_daily(df, skip)
        self.update_status()
        note = f"（略過重複 {len(skip)} 天）" if skip else (f"（含覆蓋 {len(dup)} 天）" if dup else "")
        self.log(f"匯入 {os.path.basename(path)}：商品「{item}」寫入 {n} 天{note}")

    # ---- ③ ----
    def export_daily(self):
        item = self.export_item.get()
        if not item:
            return messagebox.showinfo("提示", "資料庫是空的，沒有商品可以匯出")
        path = filedialog.asksaveasfilename(initialdir=DATA, defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
                                            initialfile=f"OHLC_{item}_匯出_{datetime.now():%Y%m%d}.xlsx")
        if not path:
            return
        d, n = os.path.split(path)
        if "ohlc" not in n.lower():
            path = os.path.join(d, "OHLC_" + n)
        self.log(f"已匯出「{item}」{db.export_daily_excel(path, item)} 天：{path}")


if __name__ == "__main__":
    App().mainloop()
