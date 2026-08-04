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
