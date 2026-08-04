import os
import glob
import csv
import pandas as pd
from jinja2 import Template
from datetime import datetime

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>全球新藥熱度與上市聲量排行榜</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f4f7f6; font-family: "Microsoft JhengHei", sans-serif; }
        .hero-header { background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%); color: white; padding: 2.5rem 0; }
        .card-insight { border-left: 5px solid #ff9f43; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        .badge-buzz { background-color: #ffeaa7; color: #d63031; font-weight: bold; border: 1px solid #fdcb6e; }
        .badge-global { background-color: #e3f2fd; color: #0d6efd; font-weight: bold; border: 1px solid #90caf9; }
        .rank-num { font-size: 1.2rem; font-weight: bold; color: #6c757d; }
    </style>
</head>
<body>
    <div class="hero-header text-center mb-4">
        <h1>🔥 全球新藥聲量與上市趨勢排行榜</h1>
        <p class="lead mb-0">自動監測 14 天內多國審查、熱門新聞與上市密度</p>
        <small class="opacity-75">報告產出時間：{{ generated_at }} | 本期追蹤熱門標的：{{ total_items }} 項</small>
    </div>

    <div class="container mb-5">
        <div class="card card-insight p-4 bg-white rounded mb-4">
            <h5 class="text-warning fw-bold">📊 情報分析提示 (Trend Insights)</h5>
            <p class="mb-0 text-secondary">
                本系統透過演算法統計近 14 天內之醫藥報導與官方公告。若標註有 <span class="badge badge-buzz">🔥 高聲量關注</span> 或 <span class="badge badge-global">🌍 多國/多機構聯動</span>，代表該藥品正處於全球核准或上市熱潮，建議列入醫院藥委會（Pharmacy Committee）主動引進評估首選。
            </p>
        </div>

        <div class="card shadow-sm">
            <div class="card-header bg-white py-3">
                <h5 class="m-0 font-weight-bold text-dark">🏆 新藥聲量排行榜 (Ranked by Buzz Frequency)</h5>
            </div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0">
                        <thead class="table-dark">
                            <tr>
                                <th style="width: 5%;">#</th>
                                <th style="width: 20%;">藥物成分 (Ingredient)</th>
                                <th style="width: 10%;">近14天聲量</th>
                                <th style="width: 18%;">趨勢與熱度標籤</th>
                                <th style="width: 15%;">來源機構/國家</th>
                                <th style="width: 22%;">跨國熱點摘要</th>
                                <th style="width: 10%;">最新日期</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for item in results %}
                            <tr>
                                <td class="rank-num">{{ loop.index }}</td>
                                <td class="fw-bold text-primary fs-6">{{ item.drug_ingredient }}<br><small class="text-muted">({{ item.company }})</small></td>
                                <td><span class="badge bg-danger rounded-pill px-3 py-2 fs-6">{{ item.buzz_count }} 次報導</span></td>
                                <td>
                                    {% if '高聲量' in item.trend_tags %}
                                        <span class="badge badge-buzz px-2 py-1 mb-1">{{ item.trend_tags }}</span>
                                    {% else %}
                                        <span class="badge badge-global px-2 py-1 mb-1">{{ item.trend_tags }}</span>
                                    {% endif %}
                                </td>
                                <td><small class="fw-bold text-dark">{{ item.source_regions }}</small></td>
                                <td><small class="text-secondary">{{ item.key_summary }}</small></td>
                                <td><small class="text-muted">{{ item.latest_date }}</small></td>
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
    data_dir = "data"
    csv_files = glob.glob(os.path.join(data_dir, "raw_*.csv"))
    if not csv_files:
        print("No CSV raw data files found in data/")
        return

    latest_csv = max(csv_files, key=os.path.getctime)
    results = []
    with open(latest_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(row)

    os.makedirs("reports", exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 匯出 Excel
    df = pd.DataFrame(results)
    df.to_excel(f"reports/report_{today_str}.xlsx", index=False)

    # 繪製 HTML 儀表板
    template = Template(HTML_TEMPLATE)
    html_content = template.render(
        results=results,
        total_items=len(results),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    with open(f"reports/report_{today_str}.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print("Successfully generated Trend Ranking Dashboard!")

if __name__ == "__main__":
    main()
