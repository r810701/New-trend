import os
import glob
import csv
import pandas as pd
from jinja2 import Environment, FileSystemLoader
from datetime import datetime

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

    # 4. 使用 Jinja2 繪製 HTML 儀表板網頁
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("index.html")

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
