import os
import csv
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from collections import defaultdict

# 聲量門檻
HIGH_BUZZ_THRESHOLD = 2

# 模擬/實體測試資料（帶有新聞原始連結）
DEMO_RAW_DATA = [
    {
        "source": "US-FDA",
        "title": "FDA Grants Accelerated Approval for Novel ADC Therapy",
        "ingredient": "Datopotamab Deruxtecan (Dato-DXd)",
        "company": "AstraZeneca / Daiichi Sankyo",
        "pub_date": "2026-08-02",
        "summary": "獲准用於先前接受過治療之轉移性非小細胞肺癌 (NSCLC)，三期臨床數據顯示 PFS 顯著改善。",
        "url": "https://www.fda.gov/news-events/press-announcements"
    },
    {
        "source": "EU-EMA",
        "title": "EMA Recommends Marketing Authorization for Dato-DXd",
        "ingredient": "Datopotamab Deruxtecan (Dato-DXd)",
        "company": "AstraZeneca",
        "pub_date": "2026-08-01",
        "summary": "歐洲藥局給予正面審查意見，預計近期於歐盟市場上市。",
        "url": "https://www.ema.europa.eu/en/news"
    },
    {
        "source": "Global Pharma News",
        "title": "New Non-Hormonal Menopause Drug Shows Breakthrough Success",
        "ingredient": "Elinzanetant",
        "company": "Bayer",
        "pub_date": "2026-08-01",
        "summary": "針對更年期血管舒縮症狀 (VMS) 之 NK1/3 受體拮抗劑，多家國際新聞報導其安全性。",
        "url": "https://www.biopharmadive.com"
    },
    {
        "source": "TFDA 衛福部",
        "title": "食藥署核准新型降血脂小干擾 RNA 藥物專案進用",
        "ingredient": "Inclisiran",
        "company": "Novartis",
        "pub_date": "2026-08-03",
        "summary": "一年僅需施打兩針之 siRNA 藥物，提供高膽固醇血症患者長期控制新選擇。",
        "url": "https://www.fda.gov.tw/TC/news.aspx"
    }
]

def main():
    # 支援指定年月（可透過環境變數傳入，預設當下）
    target_date_str = os.environ.get("TARGET_DATE", datetime.now().strftime("%Y-%m-%d"))
    try:
        base_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    except ValueError:
        base_date = datetime.now()

    DAYS_INTERVAL = 14
    cutoff_date = base_date - timedelta(days=DAYS_INTERVAL)

    grouped_data = defaultdict(lambda: {
        "count": 0,
        "sources": set(),
        "companies": set(),
        "articles": [], # 儲存每篇報導的來源、摘要與 URL
        "latest_date": "2000-01-01"
    })

    for item in DEMO_RAW_DATA:
        item_date = datetime.strptime(item["pub_date"], "%Y-%m-%d")
        if cutoff_date <= item_date <= base_date:
            ing = item["ingredient"]
            grouped_data[ing]["count"] += 1
            grouped_data[ing]["sources"].add(item["source"])
            grouped_data[ing]["companies"].add(item["company"])
            grouped_data[ing]["articles"].append({
                "source": item["source"],
                "summary": item["summary"],
                "url": item["url"],
                "date": item["pub_date"]
            })
            if item["pub_date"] > grouped_data[ing]["latest_date"]:
                grouped_data[ing]["latest_date"] = item["pub_date"]

    final_results = []
    for ing, data in grouped_data.items():
        tags = []
        if data["count"] >= HIGH_BUZZ_THRESHOLD:
            tags.append("🔥 高聲量關注")
        if len(data["sources"]) >= 2:
            tags.append("🌍 多國/多機構聯動")
        if not tags:
            tags.append("📈 新進觀察標的")

        final_results.append({
            "drug_ingredient": ing,
            "buzz_count": data["count"],
            "source_regions": "、".join(data["sources"]),
            "company": " / ".join(data["companies"]),
            "trend_tags": " | ".join(tags),
            "articles_json": data["articles"], # 傳遞完整文章與連結資訊
            "latest_date": data["latest_date"]
        })

    final_results.sort(key=lambda x: x["buzz_count"], reverse=True)

    os.makedirs("data", exist_ok=True)
    today_str = base_date.strftime("%Y-%m-%d")
    csv_path = f"data/raw_{today_str}.csv"
    
    import json
    fieldnames = ["drug_ingredient", "buzz_count", "source_regions", "company", "trend_tags", "articles_json", "latest_date"]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in final_results:
            row_copy = row.copy()
            row_copy["articles_json"] = json.dumps(row_copy["articles_json"], ensure_ascii=False)
            writer.writerow(row_copy)
    
    print(f"Data process complete for target date: {today_str}")

if __name__ == "__main__":
    main()
