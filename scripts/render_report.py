import csv
import glob
import os
from jinja2 import Template

def main():
    # 搜尋最新的 raw CSV 資料檔
    csv_files = sorted(glob.glob("data/raw_*.csv"))
    if not csv_files:
        print("No CSV files found in data/")
        return
    
    latest_csv = csv_files[-1]
    date_str = os.path.basename(latest_csv).replace("raw_", "").replace(".csv", "")
    print(f"Processing data from: {latest_csv}")

    results = []
    with open(latest_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(row)

    # 1. 嘗試產出 Excel 檔案（若環境允許）
    try:
        import pandas as pd
        df = pd.DataFrame(results)
        os.makedirs("reports", exist_ok=True)
        excel_path = f"reports/report_{date_str}.xlsx"
        df.to_excel(excel_path, index=False)
        print(f"Successfully generated Excel report: {excel_path}")
    except Exception as e:
        print(f"Notice: Excel generation skipped or failed ({e}), rendering HTML report.")

    # 2. 產出 HTML 網頁報表
    template_path = "templates/index.html"
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            tmpl_str = f.read()
        
        tmpl = Template(tmpl_str)
        rendered_html = tmpl.render(
            results=results,
            generated_at=date_str,
            total_items=len(results)
        )
        
        html_path = f"reports/report_{date_str}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(rendered_html)
        print(f"Successfully generated HTML report: {html_path}")

if __name__ == "__main__":
    main()
