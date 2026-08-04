import os
import csv
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from collections import defaultdict

HIGH_BUZZ_THRESHOLD = 2

# 實體/佐證資料：每篇文章明確對應到特定藥物成分 (drug_ingredient)
DEMO_RAW_DATA = [
    {
        "ingredient": "Datopotamab Deruxtecan (Dato-DXd)",
        "company": "AstraZeneca / Daiichi Sankyo",
        "source": "US-FDA 官網公告",
        "title": "FDA 專案優先審查核准：新型抗體藥物複合體 (ADC)",
        "summary": "獲准用於先前接受過治療之轉移性非小細胞肺癌 (NSCLC)，三期臨床數據顯示 PFS 顯著改善。",
        "url": "https://www.fda.gov/news-events/press-announcements",
        "pub_date": "2026-08-02"
    },
    {
        "ingredient": "Datopotamab Deruxtecan (Dato-DXd)",
        "company": "AstraZeneca / Daiichi Sankyo",
        "source": "EU-EMA 歐盟藥局",
        "title": "EMA 人用藥品委員會 (CHMP) 給予正面上市推薦意見",
        "summary": "歐洲藥局給予正面審查意見，預計近期於歐盟市場全面上市。",
        "url": "https://www.ema.europa.eu/en/news",
        "pub_date": "2026-08-01"
    },
    {
        "ingredient": "Elinzanetant",
        "company": "Bayer (拜耳)",
        "source": "Global Pharma News 醫藥新聞",
        "title": "Bayer 突破性更年期非荷爾蒙新藥臨床試驗發表",
        "summary": "針對更年期血管舒縮症狀 (VMS) 之 NK1/3 受體拮抗劑，多家國際新聞報導其顯著療效。",
        "url": "https://www.biopharmadive.com",
        "pub_date": "2026-08-01"
    },
    {
        "ingredient": "Inclisiran",
        "company": "Novartis (諾華)",
        "source": "TFDA 衛福部食藥署",
        "title": "食藥署核准新型降血脂小干擾 RNA 藥物專案進用",
        "summary": "一年僅需施打兩針之 siRNA 藥物，提供高膽固醇血症患者長期控制新選擇。",
        "url": "https://www.fda.gov.tw/TC/news.aspx",
        "pub_date": "2026-08-03"
    }
]

def main():
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
        "articles": [],
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
                "title": item["title"],
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
            "articles": data["articles"],
            "latest_date": data["latest_date"]
        })

    final_results.sort(key=lambda x: x["buzz_count"], reverse=True)

    os.makedirs("data", exist_ok=True)
    today_str = base_date.strftime("%Y-%m-%d")
    csv_path = f"data/raw_{today_str}.csv"
    
    fieldnames = ["drug_ingredient", "buzz_count", "source_regions", "company", "trend_tags", "articles_json", "latest_date"]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in final_results:
            row_copy = row.copy()
            row_copy["articles_json"] = json.dumps(row_copy["articles"], ensure_ascii=False)
            del row_copy["articles"]
            writer.writerow(row_copy)
    
    print(f"Data process complete for target date: {today_str}")

if __name__ == "__main__":
    main()
