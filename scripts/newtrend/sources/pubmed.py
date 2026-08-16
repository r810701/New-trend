from __future__ import annotations

"""PubMed E-utilities API —— 檢索近一年（365天）第三期臨床試驗與同行評審論文篇數。

官方 API，完全免費公開，無需 API Key。
查詢近一年內提及該藥物之 Phase 3 / Pivotal Clinical Trials 同行評審文獻量。
"""

import json
from urllib.parse import quote

from ..http import Fetcher, FetchError
from ..model import Article

API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
MAX_LOOKUPS = 40


def enrich(fetcher: Fetcher, articles: list[Article]) -> int:
    targets: dict[str, list[Article]] = {}
    for art in articles:
        if art.ingredient_key:
            targets.setdefault(art.ingredient_key, []).append(art)

    filled = 0
    for key, group in list(targets.items())[:MAX_LOOKUPS]:
        count, top_id = _query_pubmed_p3_count(fetcher, key)
        if count is not None:
            for art in group:
                art.extras["pubmed_p3_count"] = count
                if top_id:
                    art.extras["pubmed_top_id"] = top_id
            filled += 1

    return filled


def _query_pubmed_p3_count(fetcher: Fetcher, ingredient_key: str) -> tuple[int | None, str | None]:
    """檢索近一年 (reldate=365) Phase 3 相關文獻篇數。"""
    term = f'("{ingredient_key}"[Title/Abstract]) AND (Phase 3 OR "Phase III" OR "clinical trial"[Publication Type])'
    url = f"{API}?db=pubmed&term={quote(term)}&datetype=pdat&reldate=365&retmode=json"
    
    try:
        payload = fetcher.get_json(url)
        res = payload.get("esearchresult", {})
        count = int(res.get("count", 0))
        idlist = res.get("idlist", [])
        top_id = idlist[0] if idlist else None
        return count, top_id
    except (FetchError, ValueError, KeyError):
        return None, None
