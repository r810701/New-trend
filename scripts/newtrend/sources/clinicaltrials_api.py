"""ClinicalTrials.gov v2 官方 API —— 補研發階段（phase）。

README 從第一天就想要「研發階段」欄位，這是唯一免費且結構化的來源。
一樣是官方 API 不是爬蟲，且**只做補充**，查不到留空、不擋主流程。
"""

from urllib.parse import quote

from ..http import Fetcher, FetchError
from ..model import Article

API = "https://clinicaltrials.gov/api/v2/studies"
MAX_LOOKUPS = 25

_ORDER = ["PHASE4", "PHASE3", "PHASE2", "PHASE1", "EARLY_PHASE1"]
_LABEL = {"PHASE4": "四期", "PHASE3": "三期", "PHASE2": "二期",
          "PHASE1": "一期", "EARLY_PHASE1": "早期一期"}


def enrich(fetcher: Fetcher, articles: list[Article]) -> int:
    targets: dict[str, list[Article]] = {}
    for art in articles:
        if art.ingredient_key:
            targets.setdefault(art.ingredient_key, []).append(art)

    filled = 0
    for key, group in list(targets.items())[:MAX_LOOKUPS]:
        phase = _highest_phase(fetcher, key)
        if not phase:
            continue
        for art in group:
            art.extras.setdefault("phase", phase)
        filled += 1

    return filled


def _highest_phase(fetcher: Fetcher, ingredient_key: str) -> str | None:
    """取該成分目前最高的試驗期別 —— 最高期別才代表研發進度。"""
    url = (f"{API}?query.intr={quote(ingredient_key)}&pageSize=20"
           f"&fields=protocolSection.designModule.phases")
    try:
        payload = fetcher.get_json(url)
    except (FetchError, ValueError):
        return None

    found = set()
    for study in payload.get("studies") or []:
        phases = (study.get("protocolSection", {})
                       .get("designModule", {})
                       .get("phases") or [])
        found.update(phases)

    for phase in _ORDER:
        if phase in found:
            return _LABEL[phase]
    return None
