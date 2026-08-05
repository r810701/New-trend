"""US-FDA — Novel Drug Approvals（年度頁）。

四個來源裡資料品質最好的一個：官方策展的 NME 清單，且**直接給 Active Ingredient**，
不必從標題猜成分。
"""

import re
from datetime import date

from bs4 import BeautifulSoup

from ..http import Fetcher, FetchError
from ..model import Article, parse_date

SOURCE = "US-FDA"
INDEX_URL = "https://www.fda.gov/drugs/development-approval-process-drugs/novel-drug-approvals-fda"

_YEAR_LINK = re.compile(r"/drugs/novel-drug-approvals-fda/novel-drug-approvals-(\d{4})")


def fetch(fetcher: Fetcher, base_date: date) -> list[Article]:
    year_url = _latest_year_url(fetcher, base_date.year)
    soup = BeautifulSoup(fetcher.get_text(year_url), "html.parser")

    table = soup.find("table")
    if table is None:
        raise FetchError(f"{year_url} 找不到 <table> —— FDA 改版了，parser 需要更新")

    body = table.find("tbody") or table
    articles = []
    for tr in body.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(cells) < 5:
            continue
        _no, brand, ingredient, approved, indication = cells[:5]
        articles.append(Article.make(
            source=SOURCE,
            title=f"FDA 核准新分子實體：{brand}",
            url=year_url,
            pub_date=parse_date(approved),
            ingredient=ingredient,
            brand=brand,
            summary=indication,
            extras={"kind": "approval"},
        ))

    if not articles:
        raise FetchError(f"{year_url} 的表格解析出 0 筆 —— 版型可能變了")
    return articles


def _latest_year_url(fetcher: Fetcher, want_year: int) -> str:
    """索引頁列出各年度分頁。優先取當年度，取不到就退到索引頁看得到的最新一年。"""
    soup = BeautifulSoup(fetcher.get_text(INDEX_URL), "html.parser")
    years = {}
    for a in soup.find_all("a", href=True):
        m = _YEAR_LINK.search(a["href"])
        if m:
            years[int(m.group(1))] = "https://www.fda.gov" + m.group(0)

    if not years:
        raise FetchError("FDA 索引頁找不到任何年度連結 —— 版型可能變了")
    return years.get(want_year, years[max(years)])
