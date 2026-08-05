"""openFDA 官方 API —— 補申請案編號與藥廠。

不是爬蟲：`api.fda.gov` 是 FDA 官方公開 API，有文件、免費、無金鑰限 240 req/min。
能用 API 就不要爬 HTML。

這個模組**不產生新的 Article**，只對既有項目做補充。查不到就留空，不擋主流程 ——
補充資料缺了報表照樣有意義，為了它讓整批失敗不划算。
"""

from urllib.parse import quote

from ..http import Fetcher, FetchError
from ..model import Article

API = "https://api.fda.gov/drug/drugsfda.json"
MAX_LOOKUPS = 25  # 官方 API 也是別人的資源，不要一次打上百次


def enrich(fetcher: Fetcher, articles: list[Article]) -> int:
    """就地補 extras；回傳補到幾筆。"""
    targets = _pick_targets(articles)
    filled = 0

    for key, group in list(targets.items())[:MAX_LOOKUPS]:
        info = _lookup(fetcher, key)
        if not info:
            continue
        for art in group:
            art.extras.setdefault("application_no", info.get("application_no", ""))
            if info.get("sponsor") and not art.company:
                art.company = info["sponsor"]
        filled += 1

    return filled


def _pick_targets(articles: list[Article]) -> dict[str, list[Article]]:
    targets: dict[str, list[Article]] = {}
    for art in articles:
        if art.ingredient_key:
            targets.setdefault(art.ingredient_key, []).append(art)
    return targets


def _lookup(fetcher: Fetcher, ingredient_key: str) -> dict | None:
    url = (f"{API}?search=openfda.generic_name:%22{quote(ingredient_key)}%22"
           f"&limit=1")
    try:
        payload = fetcher.get_json(url)
    except (FetchError, ValueError):
        # 查無資料時 openFDA 回 404，那是正常結果不是故障。
        return None

    results = payload.get("results") or []
    if not results:
        return None

    entry = results[0]
    return {
        "application_no": entry.get("application_number", ""),
        "sponsor": entry.get("sponsor_name", ""),
    }
