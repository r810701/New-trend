簡短說明

這個專案會產生藥品趨勢報表的 MVP：
- scripts/fetch.py: 從 urls.txt 逐站抓取標題與摘要，輸出 data/articles.csv
- scripts/render_report.py: 讀取 CSV 並產生 HTML 報告與圖表，輸出到 reports/
- .github/workflows/generate-report.yml: 手動觸發的 workflow (workflow_dispatch)，執行腳本並把報表 commit 回 repo

如何本地執行
1. 建議建立虛擬環境並安裝套件
   python -m venv .venv
   source .venv/bin/activate  # 或 Windows: .venv\\Scripts\\activate
   pip install -r requirements.txt

2. 執行抓取與產生報表
   python scripts/fetch.py
   python scripts/render_report.py

3. 產生的檔案會放在 data/ 與 reports/ 目錄，workflow 會把 reports/ commit 回 repo

注意事項
- 目前使用通用擷取器，對於每個目標網站可能需要額外的 site-specific parser 才能擷取完整欄位（廠商、研發階段等）。
- 請遵守 robots.txt 與網站使用條款，避免高頻率爬取。
