"""TW-TFDA — 新成分新藥核准審查報告摘要。

**這一站拿不到英文成分名**（在每筆的 PDF 摘要裡），所以 `ingredient` 一律留 None，
讓它落在「無 INN」那一組、不參與跨源聲量。詳見 CLAUDE.md §4。

抓取禮儀見 CLAUDE.md §5.3：站方 robots.txt 明文擋 ClaudeBot/GPTBot，
本模組因此只抓第 1 頁、節流放寬。**不要在這裡加分頁迴圈。**
"""

import re
from datetime import date

from bs4 import BeautifulSoup

from ..http import Fetcher, FetchError
from ..model import Article, parse_date

SOURCE = "TW-TFDA"
BASE = "https://www.fda.gov.tw"
LIST_URL = BASE + "/tc/sitelist.aspx?sid=2712&pn=1"

# 標題格式：<廠商>「<中文品名>」(<許可證字號>)
_TITLE = re.compile(r"^(?P<company>.*?)「(?P<brand>.*?)」\s*[(（](?P<license>.*?)[)）]")


def fetch(fetcher: Fetcher, base_date: date) -> list[Article]:
    soup = BeautifulSoup(fetcher.get_text(LIST_URL), "html.parser")
    table = soup.find("table")
    if table is None:
        raise FetchError(f"{LIST_URL} 找不到 <table> —— TFDA 改版了")

    # 這張表的 <tr> 沒有正確閉合，tr.find_all("td") 會把後面所有列一起吃進來
    # （第 1 列會拿到 30 個 td）。所以直接取全部 td 再每 3 個一組切。
    cells = table.find_all("td")
    if len(cells) % 3:
        raise FetchError(f"TFDA td 數量 {len(cells)} 不是 3 的倍數 —— 欄位數變了")

    articles = []
    for i in range(0, len(cells), 3):
        title = cells[i + 1].get_text(" ", strip=True)
        link = cells[i + 1].find("a")
        if not title:
            continue

        parsed = _TITLE.match(title)
        href = link["href"] if link else LIST_URL
        articles.append(Article.make(
            source=SOURCE,
            title=f"TFDA 核准新成分新藥：{title}",
            url=href if href.startswith("http") else BASE + href,
            pub_date=parse_date(cells[i + 2].get_text(strip=True)),
            ingredient=None,                        # 英文成分名在 PDF 裡，這裡拿不到
            brand=parsed.group("brand") if parsed else title,
            company=parsed.group("company") if parsed else None,
            summary="審查報告摘要 PDF（英文成分名需開啟 PDF 查閱）",
            extras={
                "kind": "approval",
                "no_inn": True,
                "license_no": parsed.group("license") if parsed else "",
            },
        ))

    if not articles:
        raise FetchError("TFDA 解析出 0 筆 —— 版型可能變了")
    return articles
