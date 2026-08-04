#!/usr/bin/env python3
"""
scripts/fetch.py
- 讀取 urls.txt（seed 列表）
- 對每個 seed 抓取 page，找內頁連結（最多 N 個），再深入抓取內頁
- 嘗試抽出欄位：drug_name, indication, sponsor, phase, date, summary, url
- 輸出 CSV: data/articles_detailed.csv
Notes:
- 已加入 retry 與隨機 User-Agent 以降低 403 機率
- 若仍被 403，請改用 Playwright 或 site-specific API
"""
import csv
import os
import random
import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

INPUT = "urls.txt"
OUT_DIR = "data"
OUT_CSV = os.path.join(OUT_DIR, "articles_detailed.csv")
MAX_LINKS_PER_SITE = 8
SLEEP_BETWEEN_REQUESTS = 1.0  # seconds
REQUEST_TIMEOUT = 20

USER_AGENTS = [
    # A small set of common UAs; 可以擴充
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:116.0) Gecko/20100101 Firefox/116.0",
]

os.makedirs(OUT_DIR, exist_ok=True)


def make_session():
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504, 403])
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s


def get_headers(referer=None):
    ua = random.choice(USER_AGENTS)
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def safe_get(session, url, referer=None):
    try:
        return session.get(url, headers=get_headers(referer), timeout=REQUEST_TIMEOUT)
    except Exception as e:
        return e


def is_same_domain(seed_url, candidate):
    try:
        s = urlparse(seed_url).netloc
        c = urlparse(candidate).netloc
        return s == c or c == ""
    except Exception:
        return False


def canonicalize(base, link):
    return urljoin(base, link)


def extract_text_snippets(soup):
    # return a list of top paragraph texts
    paras = []
    for sel in ("article p", "main p", "div[class*='content'] p", "p"):
        for p in soup.select(sel):
            txt = p.get_text(" ", strip=True)
            if txt and len(txt) > 50:
                paras.append(txt)
            if len(paras) >= 6:
                break
        if paras:
            break
    return paras


def extract_meta_date(soup):
    # common meta properties
    for prop in ["article:published_time", "pubdate", "publishdate", "date"]:
        tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        if tag and tag.get("content"):
            return tag.get("content").strip()
    # time tag
    t = soup.find("time")
    if t:
        if t.get("datetime"):
            return t.get("datetime").strip()
        txt = t.get_text(" ", strip=True)
        if txt:
            return txt
    # fallback: search for date-like patterns in page text
    text = soup.get_text(" ", strip=True)
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if m:
        return m.group(1)
    m = re.search(r"\b(\d{1,2} [A-Za-z]{3,9} \d{4})\b", text)
    if m:
        return m.group(1)
    return ""


def find_phase(text):
    # search for Phase I, Phase II/III, phase 3, approved, marketing authorisation, EUA
    m = re.search(r"\bPhase\s*(I{1,3}|IV|[1-4])\b", text, re.I)
    if m:
        return m.group(0)
    if re.search(r"\bPhase\s*(I|II|III|IV)\b", text, re.I):
        return re.search(r"\bPhase\s*(I|II|III|IV)\b", text, re.I).group(0)
    if re.search(r"\bapproved\b|\bmarketing authoris|marketing authoriz|authorization\b", text, re.I):
        return "Approved"
    if re.search(r"\bEUA\b|\bEmergency Use Authorization\b", text, re.I):
        return "EUA"
    return ""


def find_sponsor(text):
    # naive patterns
    m = re.search(r"(sponsored by|sponsor:|sponsor -|sponsored\s+by|manufactured by|manufacturer:)\s*([A-Za-z0-9&\-\.,\(\) ]{3,80})", text, re.I)
    if m:
        return m.group(2).strip(" .;,-")
    # common phrase 'by <Company>'
    m2 = re.search(r"\bby\s+([A-Z][A-Za-z0-9&\-\., ]{2,80})", text)
    if m2:
        candidate = m2.group(1).split(",")[0].strip()
        # ignore short common words
        if len(candidate) > 3 and len(candidate.split()) <= 5:
            return candidate
    return ""


def find_indication(text):
    # look for sentences with 'indication' or 'for the treatment of' or 'indicated for'
    m = re.search(r"([^.]{0,200}(indicat(?:ed|ion)|for the treatment of|treatment of|in patients with)[^.]{0,200})", text, re.I)
    if m:
        return m.group(1).strip()
    # fallback: first sentence containing 'treatment' or disease words
    m2 = re.search(r"([^.]{0,200}(treatment|disease|patients with|cancer|diabetes|infection)[^.]{0,200})", text, re.I)
    if m2:
        return m2.group(1).strip()
    return ""


def find_drug_name(title, paras_text):
    # default: title is often the drug name + descriptor; try to simplify
    if title:
        t = re.sub(r"\s+[\|\-–].*$", "", title).strip()
        # if title contains ':' maybe second part is drug, use before colon
        if len(t.split()) <= 6:
            return t
        # else take first 6 words
        return " ".join(t.split()[:6])
    # fallback: search for uppercase token in first paragraph
    for p in paras_text:
        m = re.search(r"\b([A-Z][A-Za-z0-9\-\+]{2,40})\b", p)
        if m:
            return m.group(1)
    return ""


def extract_from_page(session, url, seed_url=None):
    resp = safe_get(session, url, referer=seed_url)
    if isinstance(resp, Exception):
        return {"url": url, "error": str(resp)}
    if resp.status_code >= 400:
        return {"url": url, "error": f"HTTP {resp.status_code}"}
    soup = BeautifulSoup(resp.text, "html.parser")

    title = (soup.title.string if soup.title and soup.title.string else "").strip()
    metasummary = ""
    md = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if md and md.get("content"):
        metasummary = md.get("content").strip()

    paras = extract_text_snippets(soup)
    combined_text = " ".join([title, metasummary] + paras)

    drug_name = find_drug_name(title, paras)
    indication = find_indication(combined_text)
    sponsor = find_sponsor(combined_text)
    phase = find_phase(combined_text)
    date = extract_meta_date(soup)
    summary = metasummary or (paras[0] if paras else "")

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "seed": seed_url or "",
        "url": url,
        "domain": urlparse(url).netloc,
        "title": title,
        "drug_name": drug_name,
        "indication": indication,
        "sponsor": sponsor,
        "phase": phase,
        "date": date,
        "summary": summary,
    }


def collect_candidate_links(soup, base_url, max_links=MAX_LINKS_PER_SITE):
    links = []
    for a in soup.find_all("a", href=True):
        href = a.get("href").strip()
        if href.startswith("mailto:") or href.startswith("tel:"):
            continue
        full = canonicalize(base_url, href)
        if not is_same_domain(base_url, full):
            continue
        # simple heuristics to prefer article-like links
        if any(x in full.lower() for x in ["/news", "/press", "/article", "/publication", "/publications", "/data", "/en/"]):
            links.append(full)
        else:
            # also accept links with path depth >1
            path = urlparse(full).path
            if path.count("/") >= 2 and len(path) > 6:
                links.append(full)
        if len(links) >= max_links:
            break
    # de-dup preserve order
    seen = set()
    out = []
    for l in links:
        if l not in seen:
            seen.add(l)
            out.append(l)
    return out[:max_links]


def process_seed(session, seed_url):
    out_rows = []
    resp = safe_get(session, seed_url)
    if isinstance(resp, Exception):
        return [{"url": seed_url, "error": str(resp)}]
    if getattr(resp, "status_code", 500) >= 400:
        return [{"url": seed_url, "error": f"HTTP {resp.status_code}"}]
    soup = BeautifulSoup(resp.text, "html.parser")

    # candidate inner pages
    candidates = collect_candidate_links(soup, seed_url, max_links=MAX_LINKS_PER_SITE)
    # ensure the seed page itself is also considered
    if seed_url not in candidates:
        candidates.insert(0, seed_url)

    for i, link in enumerate(candidates):
        print(f"  -> fetching inner ({i+1}/{len(candidates)}): {link}")
        r = extract_from_page(session, link, seed_url=seed_url)
        out_rows.append(r)
        time.sleep(SLEEP_BETWEEN_REQUESTS)
    return out_rows


def main():
    seeds = []
    with open(INPUT, "r", encoding="utf-8") as f:
        for line in f:
            u = line.strip()
            if u:
                seeds.append(u)

    session = make_session()
    results = []
    for idx, s in enumerate(seeds):
        print(f"[{idx+1}/{len(seeds)}] Seed: {s}")
        try:
            rows = process_seed(session, s)
            results.extend(rows)
        except Exception as e:
            results.append({"url": s, "error": str(e)})
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    # write CSV
    fieldnames = ["timestamp", "seed", "url", "domain", "title", "drug_name", "indication", "sponsor", "phase", "date", "summary"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as csvf:
        writer = csv.DictWriter(csvf, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            # If error row
            if "error" in r:
                writer.writerow({
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "seed": r.get("url", ""),
                    "url": r.get("url", ""),
                    "domain": "",
                    "title": "",
                    "drug_name": "",
                    "indication": "",
                    "sponsor": "",
                    "phase": "",
                    "date": "",
                    "summary": r.get("error", "")
                })
            else:
                writer.writerow({
                    "timestamp": r.get("timestamp", ""),
                    "seed": r.get("seed", ""),
                    "url": r.get("url", ""),
                    "domain": r.get("domain", ""),
                    "title": r.get("title", ""),
                    "drug_name": r.get("drug_name", ""),
                    "indication": r.get("indication", ""),
                    "sponsor": r.get("sponsor", ""),
                    "phase": r.get("phase", ""),
                    "date": r.get("date", ""),
                    "summary": r.get("summary", ""),
                })
    print("Wrote", OUT_CSV)


if __name__ == "__main__":
    main()
