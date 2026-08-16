from __future__ import annotations

import hashlib
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import CACHE_DIR

# 誠實標示自己是誰，不偽裝瀏覽器。探索階段用過 Chrome UA，那是一次性的。
USER_AGENT = "New-trend/0.2 (personal research; +https://github.com/r810701/New-trend)"

# 節流值來自各站 robots.txt 實測，不是拍腦袋。
# fda.gov 對 `User-agent: *` 明寫 Crawl-Delay: 30 —— 這是全場最嚴的一個。
CRAWL_DELAY = {
    "www.fda.gov": 30.0,
    "api.fda.gov": 1.0,  # 官方 API，另有速率限制（240 req/min），非爬蟲路徑
    "www.ema.europa.eu": 2.0,
    "www.fda.gov.tw": 3.0,  # robots.txt 明文擋 ClaudeBot/GPTBot，我們放寬節流以示尊重
    "clinicaltrials.gov": 1.0,
}
DEFAULT_DELAY = 2.0

RETRY_STATUS = {500, 502, 503, 504, 429}
MAX_RETRIES = 3
TIMEOUT = 30


RATE_LIMITED = {429}
BOT_BLOCK_STATUS = {403, 401, 451}
NOT_FOUND_STATUS = {404, 410}

REASON_LABELS = {
    "bot_block": "疑似機器人阻擋（對方回 403/451，非我方程式錯誤）",
    "rate_limited": "被限流（HTTP 429）",
    "site_error": "對方伺服器錯誤，重試 3 次仍失敗（HTTP 5xx）",
    "not_found": "找不到頁面（HTTP 404/410），連結可能已失效",
    "client_error": "用戶端請求被拒（HTTP 4xx）",
    "network": "連線逾時或連不上對方站台",
    "format_changed": "版型可能變了，parser 抓不到預期內容",
    "offline_cache_miss": "--offline 模式下沒有這個 URL 的快取",
    "unknown": "未知錯誤",
}


class FetchError(RuntimeError):
    """對外請求失敗。source 模組不該吞掉它 —— 讓它冒到 fetch.py 去記狀態。

    `reason` 是給人看的分類代碼（見 REASON_LABELS），不是給程式邏輯分支用的 ——
    分類目的是讓報表能誠實標示「這是網站擋我們，不是我們程式壞了」，
    避免每次失敗都籠統寫「抓取失敗」，逼人去翻 log 才知道發生什麼事。
    """

    def __init__(self, message: str, *, reason: str = "format_changed",
                status_code: int | None = None) -> None:
        # 預設 format_changed：http.py 內部一定會明指 reason，
        # 沒指定的都是 source 模組手動丟的「找不到 <table>」之類版型錯誤。
        super().__init__(message)
        self.reason = reason
        self.status_code = status_code

    @property
    def reason_label(self) -> str:
        return REASON_LABELS.get(self.reason, REASON_LABELS["unknown"])

    @staticmethod
    def classify_status(status_code: int) -> str:
        if status_code in BOT_BLOCK_STATUS:
            return "bot_block"
        if status_code in RATE_LIMITED:
            return "rate_limited"
        if status_code in NOT_FOUND_STATUS:
            return "not_found"
        if status_code >= 500:
            return "site_error"
        return "client_error"


class Fetcher:
    def __init__(self, *, offline: bool = False, use_cache: bool = True,
                 cache_day: date | None = None) -> None:
        self.offline = offline
        self.use_cache = use_cache
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        # 快取按日期分槽：同一天重跑不重新打站，隔天自然失效，不必寫清理邏輯。
        self.cache_dir = CACHE_DIR / (cache_day or date.today()).isoformat()
        self._last_hit: dict[str, float] = {}
        self.request_count = 0

    # --- 快取 ---------------------------------------------------------------

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / hashlib.sha1(url.encode()).hexdigest()

    def _read_cache(self, url: str) -> bytes | None:
        path = self._cache_path(url)
        return path.read_bytes() if path.exists() else None

    def _write_cache(self, url: str, body: bytes) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path(url).write_bytes(body)
        # 留一份對照表，之後要人工查「這包 sha1 是哪個 URL」時不用重算。
        with (self.cache_dir / "index.txt").open("a", encoding="utf-8") as f:
            f.write(f"{hashlib.sha1(url.encode()).hexdigest()}  {url}\n")

    # --- 節流 ---------------------------------------------------------------

    def _throttle(self, url: str) -> None:
        host = urlparse(url).netloc
        delay = CRAWL_DELAY.get(host, DEFAULT_DELAY)
        last = self._last_hit.get(host)
        if last is not None:
            wait = delay - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_hit[host] = time.monotonic()

    # --- 取用 ---------------------------------------------------------------

    def get_bytes(self, url: str) -> bytes:
        if self.use_cache:
            cached = self._read_cache(url)
            if cached is not None:
                return cached
        if self.offline:
            raise FetchError(f"--offline 但快取沒有這個 URL：{url}",
                             reason="offline_cache_miss")

        last_error: Exception | None = None
        last_status: int | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            self._throttle(url)
            try:
                resp = self.session.get(url, timeout=TIMEOUT)
                self.request_count += 1
                if resp.status_code in RETRY_STATUS:
                    last_status = resp.status_code
                    last_error = FetchError(f"HTTP {resp.status_code}")
                    time.sleep(2 ** attempt)
                    continue
                # 4xx（RETRY_STATUS 以外）直接放棄，不進重試迴圈 —— 403/404
                # 不會因為多打幾次就變成 200，重試只是浪費對方的資源。
                # 注意不能靠 raise_for_status()：它丟的 HTTPError 是 RequestException
                # 的子類，會被下面的 except 接走而照樣重試。
                if resp.status_code >= 400:
                    reason = FetchError.classify_status(resp.status_code)
                    raise FetchError(f"{url} 回 HTTP {resp.status_code}（不重試）",
                                     reason=reason, status_code=resp.status_code)
                if self.use_cache:
                    self._write_cache(url, resp.content)
                return resp.content
            except requests.RequestException as exc:
                last_error = exc
                last_status = None
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)

        # 重試耗盡：last_status 有值 → 對方一直回 5xx/429；沒值 → 是連線層級的問題
        # （逾時、DNS、TLS 之類），兩者對「該不該懷疑自己程式壞了」的意義不同。
        reason = FetchError.classify_status(last_status) if last_status else "network"
        raise FetchError(f"{url} 取用失敗（重試 {MAX_RETRIES} 次）：{last_error}",
                         reason=reason, status_code=last_status)

    def get_text(self, url: str) -> str:
        return self.get_bytes(url).decode("utf-8", errors="replace")

    def get_json(self, url: str):
        import json

        return json.loads(self.get_bytes(url))
