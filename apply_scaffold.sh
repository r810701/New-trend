#!/usr/bin/env bash
set -euo pipefail

BRANCH="feature/report-mvp"

# create branch
git fetch origin
git checkout -b "$BRANCH"

# requirements.txt
cat > requirements.txt <<'EOF'
# Minimal requirements for the report generator
requests
beautifulsoup4
pandas
jinja2
matplotlib
openpyxl
EOF

# urls.txt
cat > urls.txt <<'EOF'
https://www.oecd.org/en/topics/health.html
https://www.who.int/data/gho
https://health.ec.europa.eu/medicinal-products/legal-framework-governing-medicinal-products-human-use-eu/pharmaceutical-strategy-europe_en
https://www.fda.gov/drugs/development-approval-process-drugs/novel-drug-approvals-fda
https://www.fda.gov/drugs/drug-approvals-and-databases/drug-trials-snapshots
EOF

# README.md
cat > README.md <<'EOF'
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
EOF

# scripts/fetch.py
mkdir -p scripts
cat > scripts/fetch.py <<'EOF'
#!/usr/bin/env python3
"""
scripts/fetch.py
簡單的通用擷取器：讀取 urls.txt，對每個頁面抓取 title、meta description、第一段文字，並把結果存成 data/articles.csv
"""
import csv
import os
import time
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

INPUT = "urls.txt"
OUT_DIR = "data"
OUT_CSV = os.path.join(OUT_DIR, "articles.csv")

HEADERS = {
    "User-Agent": "New-trend-report-bot/1.0 (+https://github.com/r810701/New-trend)"
}

os.makedirs(OUT_DIR, exist_ok=True)

def summarize_text(soup):
    # Try common containers
    selectors = ["article p", "main p", "p"]
    for sel in selectors:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)
    return ""

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        return {"url": url, "error": str(e)}

    soup = BeautifulSoup(r.text, "html.parser")
    title = (soup.title.string if soup.title and soup.title.string else "").strip()

    meta = ""
    md = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if md and md.get("content"):
        meta = md.get("content").strip()

    summary = summarize_text(soup)

    domain = urlparse(url).netloc

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "url": url,
        "domain": domain,
        "title": title,
        "meta_description": meta,
        "summary": summary,
    }

def main():
    urls = []
    with open(INPUT, "r", encoding="utf-8") as f:
        for line in f:
            u = line.strip()
            if u:
                urls.append(u)

    rows = []
    for i, u in enumerate(urls):
        print(f"Fetching ({i+1}/{len(urls)}): {u}")
        data = fetch(u)
        rows.append(data)
        time.sleep(1)

    fieldnames = ["timestamp", "url", "domain", "title", "meta_description", "summary"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as csvf:
        writer = csv.DictWriter(csvf, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            # In case of error, still write minimal row
            if "error" in r:
                writer.writerow({"timestamp": datetime.utcnow().isoformat() + "Z", "url": r.get("url"), "domain": "", "title": "", "meta_description": r.get("error"), "summary": ""})
            else:
                writer.writerow(r)

    print("Saved to", OUT_CSV)

if __name__ == "__main__":
    main()
EOF

# scripts/render_report.py
cat > scripts/render_report.py <<'EOF'
#!/usr/bin/env python3
"""
scripts/render_report.py
讀取 data/articles.csv，產生 reports/report_YYYYMMDD.html，並在 reports/ 放圖檔
"""
import os
from datetime import datetime
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader

DATA_CSV = "data/articles.csv"
OUT_DIR = "reports"
TEMPLATE_DIR = "templates"
TEMPLATE_NAME = "report.html"

os.makedirs(OUT_DIR, exist_ok=True)

def make_plot(df, outpath):
    # simple count by domain
    counts = df['domain'].value_counts().head(10)
    plt.figure(figsize=(8,4))
    counts.plot(kind='bar')
    plt.title('Top source domains')
    plt.tight_layout()
    plt.savefig(outpath)
    plt.close()

def render(df):
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    tpl = env.get_template(TEMPLATE_NAME)
    date = datetime.utcnow().strftime('%Y-%m-%d')
    fig = f"domain_counts_{date}.png"
    figpath = os.path.join(OUT_DIR, fig)
    make_plot(df, figpath)

    html_out = os.path.join(OUT_DIR, f"report_{date}.html")
    with open(html_out, 'w', encoding='utf-8') as f:
        f.write(tpl.render(date=date, table=df.to_dict(orient='records'), fig=fig))
    print('Wrote', html_out)

def main():
    if not os.path.exists(DATA_CSV):
        print('No data file found:', DATA_CSV)
        return
    df = pd.read_csv(DATA_CSV)
    render(df)

if __name__ == '__main__':
    main()
EOF

# templates/report.html
mkdir -p templates
cat > templates/report.html <<'EOF'
<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta charset="utf-8" />
    <title>藥品發展趨勢報告 - {{ date }}</title>
    <style>
      body { font-family: Arial, Helvetica, sans-serif; margin: 24px; color: #222 }
      header { border-bottom: 1px solid #ddd; margin-bottom: 18px }
      h1 { margin: 0 }
      .meta { color: #666 }
      table { width: 100%; border-collapse: collapse; margin-top: 12px }
      th, td { border: 1px solid #ddd; padding: 6px }
      th { background: #f7f7f7 }
      .summary { margin-top: 12px }
    </style>
  </head>
  <body>
    <header>
      <h1>藥品發展趨勢報告</h1>
      <div class="meta">產生日期：{{ date }} &nbsp; | &nbsp; 來源數：{{ table|length }}</div>
    </header>

    <section class="summary">
      <h2>摘要</h2>
      <p>本報告由 New-trend 自動化擷取產生，統整來源與簡短摘要，適合當作月報起稿與業務提藥使用。</p>
      <img src="{{ fig }}" alt="domain counts" style="max-width:600px"/>
    </section>

    <section>
      <h2>擷取結果</h2>
      <table>
        <thead>
          <tr><th>#</th><th>來源</th><th>標題</th><th>摘要 / meta</th><th>連結</th></tr>
        </thead>
        <tbody>
        {% for row in table %}
          <tr>
            <td>{{ loop.index }}</td>
            <td>{{ row.domain }}</td>
            <td>{{ row.title }}</td>
            <td>{{ row.meta_description or row.summary }}</td>
            <td><a href="{{ row.url }}">來源</a></td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </section>

    <footer style="margin-top:30px; color:#888">Generated by New-trend</footer>
  </body>
</html>
EOF

# workflow
mkdir -p .github/workflows
cat > .github/workflows/generate-report.yml <<'EOF'
name: Generate report

on:
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run fetch
        run: |
          python scripts/fetch.py

      - name: Render report
        run: |
          python scripts/render_report.py

      - name: Commit reports back to repo
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add reports/ data/
          if git diff --staged --quiet; then
            echo "No changes to commit"
          else
            git commit -m "chore: add generated report and data [skip ci]"
            git push
          fi
EOF

# final commit and push
git add .
git commit -m "scaffold: add initial report generator (fetch, render, workflow, templates, urls)" || true
git push --set-upstream origin "$BRANCH"

echo "Scaffold applied and pushed to branch $BRANCH"
