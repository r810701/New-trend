"""UK-NICE — 已發布的 Technology Appraisal guidance。

給的是「英國願不願意付錢用這個藥」，與 FDA/EMA 的「能不能上市」是不同層次的訊號，
所以同一個成分在三邊都出現才真的算跨機構聯動。
"""

from datetime import date

from bs4 import BeautifulSoup

from ..http import Fetcher, FetchError
from ..model import Article, parse_date

SOURCE = "UK-NICE"
BASE = "https://www.nice.org.uk"
LIST_URL = BASE + "/guidance/published?ndt=Guidance&ngt=Technology+appraisal+guidance"

# 清單已按日期新到舊排序，共 93 頁。只取前兩頁就涵蓋數個月，不必全爬。
PAGES = 2


def fetch(fetcher: Fetcher, base_date: date) -> list[Article]:
    articles = []
    for page in range(1, PAGES + 1):
        url = LIST_URL if page == 1 else f"{LIST_URL}&pa={page}"
        soup = BeautifulSoup(fetcher.get_text(url), "html.parser")

        table = soup.find("table")
        if table is None:
            raise FetchError(f"{url} 找不到 <table> —— NICE 改版了")

        for tr in (table.find("tbody") or table).find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue
            link = cells[0].find("a")
            if link is None:
                continue

            title = link.get_text(" ", strip=True)
            time_tag = tr.find("time")
            # bs4 會把屬性名轉小寫：原始碼是 dateTime，這裡必須讀 datetime。
            published = parse_date(time_tag.get("datetime")) if time_tag else None

            articles.append(Article.make(
                source=SOURCE,
                title=f"NICE 技術評估發布：{title}",
                url=link["href"] if link["href"].startswith("http") else BASE + link["href"],
                pub_date=published,
                ingredient=_ingredient_from_title(title),
                summary=title,
                extras={"kind": "hta", "ta_number": cells[1].get_text(strip=True)},
            ))

    if not articles:
        raise FetchError("NICE 解析出 0 筆 —— 版型可能變了")
    return articles


def _ingredient_from_title(title: str) -> str | None:
    """NICE 標題慣例是 "<成分> for treating <適應症>"，取 for 之前那段。

    不符合這個慣例（例如比較兩種療法的評估）就回 None，讓它落在無 INN 那一組，
    不要硬拆出一個看起來像成分的字串。
    """
    head = title.split(" for ")[0].strip()
    if not head or head == title or " " in head.strip() and len(head.split()) > 3:
        return None
    return head
