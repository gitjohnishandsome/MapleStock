# Artale 突襲卷價格追蹤

楓之谷 Artale「突襲額外獎勵票券」價格紀錄工具：自動偵測遊戲視窗、用 OCR 擷取拍賣行成交價，累積成每日 OHLC 並產生 K 線圖；另可比較「官方 WC 管道」與「拍賣行」哪個取得方式比較划算。

> 僅供個人參考，價格走勢不代表未來。擷取時腳本會自動操作遊戲視窗（點擊、按 Enter），請自行評估是否符合遊戲規範。

## 功能

| 啟動檔 | 功能 |
|---|---|
| `run_scrape.bat` | 偵測遊戲視窗 → 更新頁面 → 自動翻 20 頁 → OCR 讀出日期時間與單位價格 → 輸出 Excel |
| `run_import.bat` | 選資料夾，把當天的時段 Excel 合併成 OHLC Excel，確認後匯入資料庫 |
| `run_chart.bat` | 看近一週／近一個月／全部的 K 線圖，附每日數據表 |
| `run_compare.bat` | 輸入買幣價，比較官方管道與拍賣行的成本 |

### 特色
- **視窗偵測**：以視窗標題找到遊戲，擷取客戶區指定範圍（作法參考 [MapleStory-Worlds-Artale-](https://github.com/gitjohnishandsome/MapleStory-Worlds-Artale-)），並加上 OCR。
- **失敗就停止**：每一頁都讀頁碼「N / M」驗證；更新後不在第 1 頁、翻頁失敗、跳頁、不是市價分頁、畫面與上一頁相同，都會立刻停止且不產生 Excel。
- **資料庫只存每天的開高低收**（SQLite）。只接受檔名含 `OHLC` 的 Excel；日期重複會跳出提醒（覆蓋／略過／取消）；同一份 OHLC 混入不同日期會標紅並拒絕。
- **K 線圖**：價格以「萬」顯示、缺漏日期留空、資料可能不完整的日子標 ⚠、可疊官方等值線、圖下附可排序的每日數據表。漲紅跌綠。

## 安裝

需要 Windows 與 Python 3.9+。

```
pip install -r requirements.txt
```

## 快速開始

1. 開啟遊戲，進入拍賣行的「市價」分頁，搜尋「突襲」。
2. 雙擊 `run_scrape.bat` 抓取價格（產生 `data/日期/scrape_*.xlsx`）。建議每天抓幾次，例如 09:00、12:00、18:00、24:00。
3. 一天結束後雙擊 `run_import.bat`：選當天的資料夾 → 檢查預覽 → 匯出 OHLC Excel → 匯入資料庫。
4. 雙擊 `run_chart.bat` 看 K 線圖。

視窗座標（表格範圍、下一頁按鈕、搜尋框、頁碼）在 `config.yaml`，預設是 1280×720 的視窗；更換大小請用 `python capture.py --calibrate` 重新校準。

完整說明見 [操作說明書.md](操作說明書.md)。

## OHLC 規則

- 開盤價：當天最早成交的那筆；收盤價：當天最晚的那筆（同一時間有多筆取最低價）。
- 最高價／最低價：當天資料中最高／最低的單位價格。

## 取得方式比較

官方管道預設 NT$1,990 買 77 張（可在 `config.yaml` 修改）。輸入「1 億楓幣 = NT$ 多少」，程式換算 m = 1,990 ÷ 買幣價（相當於多少億楓幣），再與拍賣單價比較，並標出較划算的一方。

## 專案結構

```
capture.py      視窗偵測與擷取
ocr.py          OCR 解析（RapidOCR）
scrape.py       自動翻頁擷取 + 驗證
store.py        合併 Excel、計算 OHLC
db.py           SQLite（每日 OHLC）
import_gui.py   資料匯入視窗
chart.py        K 線圖與數據表
chart_gui.py    K 線圖視窗
compare.py      官方管道 vs 拍賣行
compare_gui.py  比較視窗
config.yaml     座標與設定
```

## 注意

- `data/`（資料庫、Excel、截圖）不會被版本控制；截圖內含角色名稱與楓幣餘額，請勿公開。
- OCR 在不同解析度或遊戲改版後可能需要重新校準。
