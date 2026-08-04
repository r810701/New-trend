import os
import csv
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from collections import defaultdict

# 設定聲量熱門門檻
HIGH_BUZZ_THRESHOLD = 2

# 預備演示資料（模擬時間區間內有多家媒體報導之熱門新藥）
DEMO_RAW_DATA = [
    {
        "source": "US-FDA",
        "title": "FDA Grants Accelerated Approval for Novel ADC Therapy",
        "ingredient": "Datopotamab Deruxtecan (Dato-DXd)",
        "company": "AstraZeneca / Daiichi Sankyo",
        "pub_date": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),
        "summary": "獲准用於先前接受過治療之轉移性非小細胞肺癌 (NSCLC)，三期臨床數據顯示 PFS 顯著改善。",
        "url": "https://www.fda.gov"
    },
    {
        "source": "EU-EMA",
        "title": "EMA Recommends Marketing Authorization for Dato-DXd",
        "ingredient": "Datopotamab Deruxtecan (Dato-DXd)",
        "company": "AstraZeneca",
        "pub_date": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
        "summary": "歐洲藥品管理局給予正面審查意見，預計近期於歐盟市場上市。",
        "url": "https://www.ema.europa.eu"
    },
    {
        "source": "Global Pharma News",
        "title": "New Non-Hormonal Menopause Drug Shows Breakthrough Success",
        "ingredient": "Elinzanetant",
        "company": "Bayer",
        "pub_date": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
        "summary": "針對更年期血管舒縮症狀 (VMS) 之 NK1/3 受體拮抗劑，多家國際新聞連續報導其安全性與療效。",
        "url": "https://www.biopharmadive.com"
    },
    {
        "source": "TFDA 衛福部",
        "title": "食藥署核准新型降血脂小干擾 RNA 藥物專案進用",
        "ingredient": "Inclisiran",
        "company": "Novartis",
        "pub_date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        "summary": "一年僅需施打兩針之 siRNA 藥物，提供高膽固醇血症患者長期控制新選擇。",
        "url": "https://www.fda.gov.tw"
    }
]

def main():
    # 預設監測近 14 天內的資料
    DAYS_INTERVAL = 14
    cutoff_date = datetime.now() - timedelta(days=DAYS_INTERVAL)
    
    # 進行資料彙整與聲量統計
    grouped_data = defaultdict(lambda: {
        "count": 0,
        "sources": set(),
        "companies": set(),
        "summaries": [],
        "latest_date": "2000-01-01",
        "urls": []
    })

    # 模擬/真實抓取資料並進行聲量歸併
    for item in DEMO_RAW_DATA:
        item_date = datetime.strptime(item["pub_date"], "%Y-%m-%d")
        
        # 時間區間過濾
        if item_date >= cutoff_date:
            ing = item["ingredient"]
            grouped_data[ing]["count"] += 1
            grouped_data[ing]["sources"].add(item["source"])
            grouped_data[ing]["companies"].add(item["company"])
            grouped_data[ing]["summaries"].append(f"[{item['source']}] {item['summary']}")
            grouped_data[ing]["urls"].append(item["url"])
            if item["pub_date"] > grouped_data[ing]["latest_date"]:
                grouped_data[ing]["latest_date"] = item["pub_date"]

    # 轉化為趨勢報告格式
    final_results = []
    for ing, data in grouped_data.items():
        # 判斷趨勢標籤
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
            "key_summary": "；".join(data["summaries"]),
            "latest_date": data["latest_date"],
            "primary_url": data["urls"][0]
        })

    # 按聲量 (buzz_count) 由高到低排序，形成排行榜
    final_results.sort(key=lambda x: x["buzz_count"], reverse=True)

    # 寫入 CSV
    os.makedirs("data", exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    csv_path = f"data/raw_{today_str}.csv"
    
    fieldnames = ["drug_ingredient", "buzz_count", "source_regions", "company", "trend_tags", "key_summary", "latest_date", "primary_url"]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(final_results)
    
    print(f"Trend data generated successfully! Processed {len(final_results)} trending topics.")

if __name__ == "__main__":
    main()
