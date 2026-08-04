import os
import glob
import csv
import pandas as pd
from jinja2 import Template
from datetime import datetime

# 將 HTML 範本直接寫在程式碼中，100% 避免 TemplateNotFound 錯誤
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>新藥趨勢與主動進用情報儀表板</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; font-family: "Microsoft JhengHei", sans-serif; }
        .hero-header { background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); color: white; padding: 2.5rem 0; }
        .card-insight { border-left: 5px solid #0d6efd; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        .badge-advantage { background-color: #e7f5ff; color: #1971c2; border: 1px solid #a5d8ff; }
    </style>
</head>
<body>
    <div class="hero-header text-center mb-4">
        <h1>💊 全球與在地新藥進用情報分析</h1>
        <p class="lead mb-0">自動監測官方與市場趨勢 ➔ 生成主動評估建議</p>
        <small class="opacity-75">報告更新時間：{{ generated_at }} | 本期追蹤項目：{{ total_items }} 筆</small>
    </div>

    <div class="container mb-5">
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="card card-insight p-4 bg-white rounded">
                    <h4 class="text-primary fw-bold">💡 本期主動進用情報摘要 (Insight Report)</h4>
                    <p class="text-muted">系統已根據抓取文章之語意與提及頻率，自動分析出具備臨床優勢與高度關注之標的：</p>
                    <div class="alert alert-info mb-0">
                        <strong>📌 臨床評估重點：</strong> 建議優先關注內文標註有 <code>突破性療法</code>、<code>第一線</code> 或 <code>顯著降低</code> 疾病風險之藥品，作為藥事委員會（Pharmacy Committee）新藥提案之優先清單。
                    </div>
                </div>
            </div>
        </div>

        <div class="card shadow-sm">
            <div class="card-header bg-white py-3">
                <h5 class="m-0 font-weight-bold text-dark">📋 新藥動態與臨床優勢清單</h5>
            </div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0">
                        <thead class="table-light">
                            <tr>
                                <th>藥品名稱</th>
                                <th>臨床優勢與亮點標記</th>
                                <th>適應症與廠商</th>
                                <th>來源標題</th>
                                <th>資料來源</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for item in results %}
                            <tr>
                                <td class="fw-bold text-primary fs-6">{{ item.drug_name }}</td>
                                <td><span class="badge badge-advantage px-2 py-1">{{ item.advantage_highlights }}</span></td>
                                <td><small class="text-muted">{{ item.indication }}<br>({{ item.company }})</small></td>
                                <td>{{ item.title }}</td>
                                <td><a href="{{ item.source_url }}" target="_blank" class="btn btn-sm btn-outline-primary">開啟原文 ↗</a></td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

def main():
    # 1. 尋找最新的 CSV 檔案
    data_dir = "data"
    csv_files = glob.glob(os.path.join(data_dir, "raw_*.csv"))
    if not csv_files:
        print("No CSV raw data files found in data/")
        return

    latest_csv = max(csv_files, key=os.path.getctime)
    print(f"Loading data from: {latest_csv}")

    # 2. 讀取 CSV 資料
    results = []
    with open(latest_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(row)

    # 3. 匯出 Excel 報告 (.xlsx)
    os.makedirs("reports", exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    excel_path = f"reports/report_{today_str}.xlsx"
    
    df = pd.DataFrame(results)
    df.to_excel(excel_path, index=False)
    print(f"Generated Excel report: {excel_path}")

    # 4. 直接渲染內嵌的 HTML 範本
    template = Template(HTML_TEMPLATE)
    html_content = template.render(
        results=results,
        total_items=len(results),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    html_path = f"reports/report_{today_str}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Successfully generated HTML report: {html_path}")

if __name__ == "__main__":
    main()
  
