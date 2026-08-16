from __future__ import annotations

"""來源註冊表。

加新站＝在這裡加一個檔並註冊一行，**不要動 fetch.py**。
四個站的版型完全不同，這個接縫就是為此存在的。
"""

from . import (
    clinicaltrials_api,
    ema_evaluation,
    fda_novel,
    openfda_api,
    pubmed,
    tfda_approvals,
)

# name -> module（模組需提供 fetch(fetcher, base_date) -> list[Article]）
REGISTRY = {
    "fda": fda_novel,
    "ema": ema_evaluation,
    "tfda": tfda_approvals,
}

# 官方 API：不產生 Article，只對既有項目補 extras。
ENRICHERS = {
    "openfda": openfda_api,
    "clinicaltrials": clinicaltrials_api,
    "pubmed": pubmed,
}

DEFAULT_SOURCES = list(REGISTRY)

__all__ = ["REGISTRY", "ENRICHERS", "DEFAULT_SOURCES"]
