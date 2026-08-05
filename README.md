# New-trend — 全球新藥熱度與上市聲量報表

從各國藥政機關抓新藥動態，依**藥品成分（INN）**歸戶，算跨機構聲量、貼趨勢標籤，
輸出單頁 HTML 儀表板與 Excel。

## 資料來源

| 來源 | 抓什麼 | 性質 |
|---|---|---|
| **US-FDA** Novel Drug Approvals | 當年度新分子實體核准清單（含 Active Ingredient） | 當期事件 |
| **EU-EMA** Medicines under evaluation | 最新一份月報 xlsx（INN／適應症／孤兒藥／PRIME／加速審查） | **審查中清單快照** |
| **UK-NICE** Technology Appraisal | 已發布的技術評估（英國付不付錢用這個藥） | 當期事件 |
| **TW-TFDA** 新成分新藥核准審查報告摘要 | 廠商／中文品名／許可證號／PDF 連結 | 當期事件，**無英文成分名** |

另用兩個官方公開 API 做補充（非爬蟲）：
[openFDA](https://open.fda.gov/) 補申請案號與藥廠、
[ClinicalTrials.gov v2](https://clinicaltrials.gov/data-api/api) 補研發階段。

`urls.txt` 記錄了全部候選站的實測狀態 —— 其中 10 個站沒有 parser，各有原因（403、連結已死、
或本身只是政策頁沒有藥品清單）。**不要以為那份清單上的 URL 都在抓。**

## 安裝與執行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```bash
python scripts/fetch.py            # → data/raw_<date>.csv + .meta.json
python scripts/render_report.py    # → reports/report_<date>.html / .xlsx
```

### fetch.py 選項

| 參數 | 說明 |
|---|---|
| `--sources fda,ema,nice,tfda` | 只跑指定來源（預設全部） |
| `--target-date 2026-07-01` | 指定報告基準日（也吃舊的 `TARGET_DATE` 環境變數） |
| `--since-days 14` | 聲量時間窗天數 |
| `--offline` | 只讀快取，完全不連外 |
| `--no-cache` | 忽略快取強制重抓 |
| `--no-enrich` | 跳過兩個官方 API 的補充查詢 |

抓取結果會快取在 `data/.cache/<日期>/`，同一天重跑不會重新打站。

**任一來源失敗時 `fetch.py` 以非 0 退出**，並在 `meta.json` 與 HTML 報表上標明本期資料不完整 ——
半套報表看起來跟完整的一模一樣，所以一定要出聲。

### render_report.py 選項

| 參數 | 說明 |
|---|---|
| `--input data/raw_2026-07-01.csv` | 指定輸入（預設取檔名日期最新的一份） |

## 怎麼讀這份報表

- **🔥 高聲量關注**：同一成分在本期被 2 個以上項目提及。
- **🌍 多國/多機構聯動**：同一成分同時出現在 2 個以上藥政機構 —— 這是最有訊號的一個標籤。
- **📈 新進觀察標的**：本期僅單一來源提及。
- **🇹🇼 TW 專屬・無 INN 對應**：TFDA 公告只有中文品名，無法與國際來源比對，故單獨列示。

兩個口徑要注意：

1. **EMA 那 80 多筆是「目前審查中」的清單快照，不是這兩週發生的事**。它逐筆沒有日期，
   因此不受時間窗限制。FDA／NICE／TFDA 才是當期事件。
2. **TFDA 不參與跨機構聲量計算** —— 英文成分名在 PDF 裡，抓不到就沒辦法比對，
   硬湊只會做出假的聯動訊號。

## 自動化

`.github/workflows/generate-report.yml` 每月 1 日（與手動觸發）跑同一條管線，
並把 `data/` 與 `reports/` commit 回 `main`。
**本地動手前先 `git pull`** —— 兩邊都會寫同一批檔案。

## 抓取禮儀

各站節流值取自其 robots.txt 實測（`fda.gov` 要求 30 秒），UA 誠實標示不偽裝瀏覽器。
細節與不可放寬的理由見 [`CLAUDE.md`](CLAUDE.md) §5。
