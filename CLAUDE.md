# New-trend — 專案守則

獨立專案，位於 `~/Github_project/New-trend`。
GitHub remote：`github.com/r810701/New-trend`。

本檔寫給改程式的人；`README.md` 寫給使用者。

---

## 1. 這個專案在做什麼

從各國藥政機關抓新藥動態，依**藥品成分（INN）**分組，算跨機構聲量、貼趨勢標籤，
輸出單頁 HTML 儀表板 + Excel。

```
scripts/fetch.py          → data/raw_<YYYY-MM-DD>.csv + raw_<date>.meta.json
scripts/render_report.py  → reports/report_<date>.html
                            reports/report_<date>.xlsx
```

```bash
.venv/bin/python scripts/fetch.py
.venv/bin/python scripts/render_report.py
```

`.venv` 為 Python 3.13。相依只有 requests / beautifulsoup4 / openpyxl / jinja2。
（`pandas` 與 `matplotlib` 已移除：前者只被用來寫一行 `to_excel`，後者全檔沒有 `savefig`。）

```bash
.venv/bin/python -m unittest discover -s tests -v    # 11 tests
```

---

## 2. 資料來源：14 個候選只有 4 個可用

2026-08-05 逐一實測 `urls.txt` 全部 14 個 URL 的結果。**這是實測不是猜測，要推翻請重新實測。**

### 有 parser 的 4 個

| 來源 | 給什麼 | 有沒有 INN |
|---|---|---|
| FDA novel drug approvals（年度頁） | `<table>`：Drug Name / **Active Ingredient** / Approval Date / Use | ✅ |
| EMA under evaluation | 月報 `.xlsx`：**INN** / 適應症 / Orphan / PRIME / 加速審查 | ✅ |
| NICE TA published | `<table>`：標題（首字即 INN）/ TA 編號 / 發布日 | ✅（靠標題首字，非保證） |
| TFDA 新成分新藥核准審查報告摘要 | `<table>`：廠商 / 中文品名 / 許可證號 / 發布日 / PDF | ❌ 見 §4 |

### 不做的 10 個，各有理由

- **403**：OECD health、健保署 `np-2476-1` —— 要規避機器人偵測才過得去，那是紅線，不做。
- **404**：FAERS（`urls.txt` 該行結尾原本有個**全形空格 U+3000**，URL 是壞的）、
  lmspiq `DRPIQ6000`（連結已死）。
- **200 但沒有藥品層級清單**：WHO GHO、EC 藥政策頁、NHS England ×2 —— 是政策頁與資料入口。
- **要再往下爬兩層**：PMDA `0005.html` 是轉接頁，暫不做。

`urls.txt` 已改成帶註解的格式，逐行標明實測狀態。**不要看到 14 個 URL 就以為 14 個都在抓。**

---

## 3. 三個版型坑（踩過了，寫在這裡免得再踩）

### 3.1 bs4 會把 HTML 屬性名轉小寫

NICE 的 `<time dateTime="2026-08-05T12:00:00">` 必須用 `tag.get("datetime")` 讀。
寫 `tag.get("dateTime")` 拿到 `None`，然後在下一行切片時才炸 —— 錯誤訊息離現場很遠。

### 3.2 TFDA 的 `<tr>` 沒有正確閉合

`tr.find_all("td")` 會把該列之後**所有列**的 td 一起吃進來（第 1 列拿到 30 個 td）。
解法：直接 `table.find_all("td")` 再**每 3 個一組**切。不要相信它的列邊界。

### 3.3 EMA 的表頭不在第 1 列

`.xlsx` 前 14 列是報告抬頭（文號、部門、`Data extracted <日期>`），
**表頭在第 15 列**。解析時從表頭字串定位欄位，不要寫死索引 —— 版型會動。

---

## 4. TFDA 只有中文品名，沒有 INN

TFDA 那張表給的是「廠商 +「中文品名」+ 許可證號」，英文成分名在每筆的審查報告摘要 PDF 裡。

所以 TFDA 的 `ingredient_key` 一律是 `None`：它**自成一組、不參與跨源成分比對、
不計入「多國/多機構聯動」標籤**，並標記為「TW 專屬・無 INN 對應」。

這是誠實呈現，不是缺陷。要讓台灣源併進跨源聲量，得解析那些 PDF —— 代價是多一個
pdfplumber 相依與每期數十次下載，值不值得另外評估。

---

## 5. 抓取禮儀（不可放寬）

### 5.1 分站節流值來自各站 robots.txt 實測

| 站 | Crawl-delay | 備註 |
|---|---|---|
| `fda.gov` | **30 秒** | robots.txt 對 `User-agent: *` 明寫 `Crawl-Delay: 30` |
| `nice.org.uk` | 1 秒 | robots.txt 明寫 |
| 其餘 | 2 秒 | 保守預設 |

**不要用單一全域節流值蓋過這張表。**

### 5.2 UA 誠實標示，不偽裝瀏覽器

```
New-trend/0.2 (personal research; +https://github.com/r810701/New-trend)
```

探索階段用過 Chrome UA 探測，那是一次性的，**不要把它寫進正式程式**。

### 5.3 `www.fda.gov.tw` 的 robots.txt 明文擋 AI 業者爬蟲

```
User-agent: ClaudeBot
Disallow: /
User-agent: GPTBot
Disallow: /
```

本專案的腳本帶自己的 UA，適用 `User-agent: *` 區塊，該區塊只擋 `personalized*.aspx`
與 `pwd.aspx`，`/tc/sitelist.aspx` 是允許的 —— 技術上合規。

但方向性訊號在那裡，所以對這一站：**只抓第 1 頁、節流放寬、不平行**。
不要因為「反正 `*` 允許」就加大抓取量。

---

## 6. 架構

```
scripts/
  fetch.py                  # CLI + 編排，沒有任何解析邏輯
  render_report.py
  newtrend/
    http.py                 # Session / UA / 分站節流 / 重試 / 磁碟快取
    model.py                # Article dataclass + ingredient_key 正規化
    aggregate.py            # 分組與貼標
    sources/
      __init__.py           # REGISTRY: name -> callable
      fda_novel.py  ema_evaluation.py  nice_ta.py  tfda_approvals.py
      openfda_api.py  clinicaltrials_api.py
```

**加新站只動 `sources/` 加一個檔並註冊，不要動 `fetch.py`。** 四個站版型完全不同，
這個接縫就是為此存在的。

### `ingredient_key` 正規化

跨源比對的關鍵。規則：小寫、去空白、**去掉 FDA 給生物製劑加的 4 字母後綴**
（`bevacizumab-vikg` → `bevacizumab`，否則同一成分在 FDA 與 EMA 永遠對不起來）、去鹽類尾綴。
**去不掉就原樣保留，不要猜。** 這是純函式，有測試，改它先改測試。

這是全專案唯一「算錯了不會報錯、只會安靜給出錯誤結論」的地方 —— 成分收斂錯了，
跨機構聲量就是假的，但報表看起來完全正常。`tests/test_normalize.py` 為此存在。

### 去重指紋必須含標的本身

`(source, url)` 不夠：FDA 年度頁的 29 筆共用同一個頁面 URL、EMA 的 84 筆共用同一個 xlsx URL，
只看 URL 會把整批壓成 1 筆（實測 90 筆變成 5 個標的）。指紋是 `(source, url, group_key)`。

### 4xx 不要重試

`resp.raise_for_status()` 丟的 `HTTPError` 是 `requests.RequestException` 的子類，
會被重試迴圈接走 —— 於是 404 也重試三次。`http.py` 因此改成自己檢查 `status_code >= 400`
直接丟 `FetchError`。**不要改回 `raise_for_status()`。**

### EMA 是月快照，不是當期事件

EMA 的 `.xlsx` 是「目前審查中」的完整清單，**逐筆沒有日期**，全部套檔頭的 `Data extracted`。
報表必須標明它是「審查中清單」而非當期新事件 —— 否則 14 天視窗的語意是錯的。

### fail loud

任一 source 失敗 → 記進 `sources_status`、印出失敗清單、**以非 0 退出**，
並寫進 `raw_<date>.meta.json` 讓報表能標示「本期 EMA 抓取失敗」。
**絕不安靜產出看起來完整的半套報表。**

---

## 7. GitHub Actions 會 push 回 main

`.github/workflows/generate-report.yml`：`workflow_dispatch` + `cron: '0 0 1 * *'`（每月 1 日）。
它跑同一條 fetch → render 然後 `git push … HEAD:main`。

- **動它之前先 `git pull`** —— `data/` 與 `reports/` 兩邊都會寫，會互相覆蓋。
- git log 裡的 `chore: auto-update drug trend report` 就是它自己 push 的。
- **改 CLI 參數時要維持「無參數可跑」**，否則下次排程會綠燈跑出空報表。

---

## 8. 其他

`apply_scaffold.sh` 是最初用來一次寫出整包骨架的產生器，**已經執行過了，不要再跑** ——
它會覆寫 `scripts/`、`templates/`、`requirements.txt`。

`reports/domain_counts_2026-08-04.png` 是舊版殘骸，現行 render 不產圖。
