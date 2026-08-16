# New-trend — 跨國新藥審查進度與台灣落差對比儀表板

從各國藥政主管機關（FDA／EMA／TFDA）與臨床實證資料庫抓取新藥動態，依**藥品成分（INN）**歸戶，以**色溫進度線條**與**四大功能區域**直觀呈現國外與台灣的上市/審查進度落差，全階段附帶官方可查驗認證連結。

---

## 核心功能與四大區域佈局

```
┌─────────────────┬─────────────────────┬───────────────────┬─────────────────────┐
│ 【區域一】      │ 【區域二】          │ 【區域三】        │ 【區域四】          │
│ 藥物基本資料    │ 國外進度 (4 階段)   │ 台灣進度 (3 階段) │ 新聞聲量與生技期刊  │
├─────────────────┼─────────────────────┼───────────────────┼─────────────────────┤
│ • INN 成分名    │ 🔵 實證文獻/臨床   │ 🔵 臨床/查驗送件  │ • FiercePharma      │
│ • 商品名 / 原廠 │ 🟢 國外申請遞件     │ 🟢 取得藥證       │ • BioPharma Dive    │
│ • 主要適應症    │ 🟤 審查與特殊認定   │ 🔴 核准健保給付   │ • 環球生技月刊      │
│ • 孤兒藥/PRIME  │ 🔴 國外核准上市     │ (未出現標示灰色)  │ • GeneOnline 基因   │
│ • 臨床試驗期別  │ (未出現標示灰色)    │ ⚡ 進度落差對比   │ • PubMed 實證文獻   │
└─────────────────┴─────────────────────┴───────────────────┴─────────────────────┘
```

---

## 主管機關與文獻來源

| 來源 | 抓取內容 | 查證性質 |
|---|---|---|
| **US-FDA** Novel Drug Approvals | 當年度新分子實體（NME）核准清單（含 Active Ingredient） | 官方正式核准上市 |
| **EU-EMA** Medicines under evaluation | 最新審查中月報 xlsx（INN／適應症／孤兒藥／PRIME／加速審查） | **審查中清單快照** |
| **TW-TFDA** 新成分新藥核准審查報告摘要 | 國內廠商／中文品名／衛部許可證號／審查報告 PDF 連結 | 台灣官方藥證核發 |
| **ClinicalTrials.gov v2** API | 國際臨床試驗登錄案號與試驗期別（Phase 1~4） | 臨床實證文獻 |
| **openFDA** API | 補充 FDA NDA/BLA 申請案號與原廠 Sponsor | 官方審查案號 |
| **生技期刊與專業論壇** | Fierce Biotech/Pharma, 環球生技, GeneOnline, PubMed | 新聞聲量與期刊動態 (第四區域) |

> **說明**：UK-NICE 因持續對爬蟲回傳 403 阻擋，已自主要排程中移除；原趨勢聲量概念已捨棄，轉為專注於實證資料與文獻來源之真實性檢驗。

---

## 安裝與執行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```bash
# 1. 抓取資料
.venv/bin/python scripts/fetch.py            # → data/raw_<date>.csv + .meta.json

# 2. 產出 HTML 儀表板與 Excel 對比報表
.venv/bin/python scripts/render_report.py    # → reports/report_<date>.html / .xlsx
```

```bash
# 執行單元測試
.venv/bin/python -m unittest discover -s tests -v
```

---

## fetch.py 選項

| 參數 | 說明 |
|---|---|
| `--sources fda,ema,tfda` | 只跑指定來源（預設全部） |
| `--target-date 2026-08-16` | 指定報告基準日（也吃 `TARGET_DATE` 環境變數） |
| `--since-days 14` | 時間窗天數 |
| `--offline` | 只讀快取，完全不連外 |
| `--no-cache` | 忽略快取強制重抓 |
| `--no-enrich` | 跳過 openFDA / ClinicalTrials API 補充查詢 |

---

## 國外 vs 台灣 進度落差判定

- 🚨 **國外已核准 ｜ 台灣未上市**：FDA 已正式核准上市，台灣尚未取得藥證（關鍵追蹤落差）。
- ⏳ **國外審查中 ｜ 台灣未送件**：國外 EMA / FDA 審查進行中，台灣尚未有公開申請紀錄。
- 🔵 **台灣已獲藥證 ｜ 健保審議中**：TFDA 已核准新藥許可證，尚未列入健保給付。
- 🟢 **台美同步 ｜ 健保已給付**：國內已取得藥證並通過健保給付收載。
- 🇹🇼 **台灣核准新藥**：TFDA 最新公告核准之新成分新藥。

---

## 自動化與排程

`.github/workflows/generate-report.yml` 每月 1 日（與手動觸發）執行 fetch 與 render，並自動 commit 更新回儲存庫。
