"""把散裝 Article 收斂成排行榜的一列，並貼趨勢標籤。"""

from datetime import date, timedelta

from .model import Article

HIGH_BUZZ_THRESHOLD = 2
MULTI_AGENCY_THRESHOLD = 2

TAG_HIGH_BUZZ = "🔥 高聲量關注"
TAG_MULTI_AGENCY = "🌍 多國/多機構聯動"
TAG_NEW = "📈 新進觀察標的"
TAG_NO_INN = "🇹🇼 TW 專屬・無 INN 對應"


def filter_window(articles: list[Article], base: date, days: int) -> list[Article]:
    """留下時間窗內的項目。

    兩種東西不套時間窗：

    - **沒有日期的**：沒有依據就不要用 base date 硬塞。
    - **快照類來源**（`extras["snapshot"]`）：EMA 的「審查中清單」描述的是**現在的狀態**，
      它身上那個日期是快照抽取日不是事件日。套 14 天窗會讓一份 7/07 抽取的清單
      在 8/05 整組消失 —— 那 84 個藥並沒有停止審查，只是清單舊了一點。
      報表會另外標明它是審查中清單而非當期新事件。
    """
    cutoff = base - timedelta(days=days)
    return [a for a in articles
            if a.pub_date is None
            or a.extras.get("snapshot")
            or cutoff <= a.pub_date <= base]


def aggregate(articles: list[Article]) -> list[dict]:
    groups: dict[str, list[Article]] = {}
    seen: set[tuple[str, str]] = set()

    for art in articles:
        # 指紋必須含「標的本身」，不能只有 (source, url)：
        # FDA 年度頁的 29 筆共用同一個頁面 URL、EMA 的 84 筆共用同一個 xlsx URL，
        # 只看 URL 會把整批壓成 1 筆（實測 90 筆變 5 個標的）。
        fingerprint = (art.source, art.url, art.group_key)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        groups.setdefault(art.group_key, []).append(art)

    results = []
    for items in groups.values():
        sources = sorted({a.source for a in items})
        companies = sorted({a.company for a in items if a.company})
        ingredients = [a.ingredient for a in items if a.ingredient]
        has_inn = any(a.has_inn for a in items)
        dates = [a.pub_date for a in items if a.pub_date]

        tags: list[str] = []
        if not has_inn:
            # 沒有 INN 就無從跨源比對，講「多機構聯動」是自欺。
            tags.append(TAG_NO_INN)
        else:
            if len(items) >= HIGH_BUZZ_THRESHOLD:
                tags.append(TAG_HIGH_BUZZ)
            if len(sources) >= MULTI_AGENCY_THRESHOLD:
                tags.append(TAG_MULTI_AGENCY)
        if not tags:
            tags.append(TAG_NEW)

        results.append({
            # 同一成分各源寫法不同時取最短的：FDA 的 "bevacizumab-vikg" 與
            # EMA 的 "Bevacizumab" 指同一個東西，顯示乾淨的那個。
            "drug_ingredient": min(ingredients, key=len) if ingredients
                               else (items[0].brand or items[0].title),
            "has_inn": has_inn,
            "buzz_count": len(items),
            "source_regions": "、".join(sources),
            "company": " / ".join(companies),
            "trend_tags": tags,
            "latest_date": max(dates).isoformat() if dates else "",
            "flags": _rollup_flags(items),
            "articles": [{
                "source": a.source,
                "title": a.title,
                "summary": a.summary,
                "url": a.url,
                "date": a.pub_date.isoformat() if a.pub_date else "",
            } for a in sorted(items, key=lambda a: (a.pub_date or date.min), reverse=True)],
        })

    # 先按聲量、再按跨機構數、最後按日期 —— 只用聲量排會讓一堆 1 分的並列亂跳。
    results.sort(key=lambda r: (r["buzz_count"], len(r["source_regions"]),
                                r["latest_date"]), reverse=True)
    return results


def _rollup_flags(items: list[Article]) -> str:
    """把各源給的旗標（EMA 的 orphan/PRIME、ClinicalTrials 的 phase）攤平成一行。"""
    labels = []
    for art in items:
        if art.extras.get("orphan"):
            labels.append("孤兒藥")
        if art.extras.get("prime"):
            labels.append("PRIME")
        if art.extras.get("accelerated"):
            labels.append("加速審查")
        if art.extras.get("phase"):
            labels.append(f"臨床 {art.extras['phase']}")
    return " / ".join(dict.fromkeys(labels))
