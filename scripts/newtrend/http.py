"""HTTP 取用層：誠實 UA、分站節流、重試、磁碟快取。

所有對外請求都必須走這裡，不要在 source 模組裡自己開 requests。
理由是節流表與快取只有集中起來才有意義 —— 散在各處的 sleep 擋不住併發。
"""

import hashlib
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import CACHE_DIR

# 誠實標示自己是誰，不偽裝瀏覽器。探索階段用過 Chrome UA，那是一次性的。
USER_AGENT = "New-trend/0.2 (personal research; +https://github.com/r810701/New-trend)"

# 節流值來自各站 robots.txt 實測（2026-08-05），不是拍腦袋。
# fda.gov 對 `User-agent: *` 明寫 Crawl-Delay: 30 —— 這是全場最嚴的一個。
CRAWL_DELAY = {
    "www.fda.gov": 30.0,
    "api.fda.gov": 1.0,  # 官方 API，另有速率限制（240 req/min），非爬蟲路徑
    "www.nice.org.uk": 1.0,
    "www.ema.europa.eu": 2.0,
    "www.fda.gov.tw": 3.0,  # robots.txt 明文擋 ClaudeBot/GPTBot，我們放寬節流以示尊重
    "clinicaltrials.gov": 1.0,
}
DEFAULT_DELAY = 2.0

RETRY_STATUS = {500, 502, 503, 504, 429}
MAX_RETRIES = 3
TIMEOUT = 30


class FetchError(RuntimeError):
    """對外請求失敗。source 模組不該吞掉它 —— 讓它冒到 fetch.py 去記狀態。"""


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
            raise FetchError(f"--offline 但快取沒有這個 URL：{url}")

        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            self._throttle(url)
            try:
                resp = self.session.get(url, timeout=TIMEOUT)
                self.request_count += 1
                if resp.status_code in RETRY_STATUS:
                    last_error = FetchError(f"HTTP {resp.status_code}")
                    time.sleep(2 ** attempt)
                    continue
                # 4xx 直接放棄，不進重試迴圈 —— 重試一個 404 只是浪費對方的資源。
                # 注意不能靠 raise_for_status()：它丟的 HTTPError 是 RequestException
                # 的子類，會被下面的 except 接走而照樣重試。
                if resp.status_code >= 400:
                    raise FetchError(f"{url} 回 HTTP {resp.status_code}（不重試）")
                if self.use_cache:
                    self._write_cache(url, resp.content)
                return resp.content
            except requests.RequestException as exc:
                last_error = exc
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)

        raise FetchError(f"{url} 取用失敗（重試 {MAX_RETRIES} 次）：{last_error}")

    def get_text(self, url: str) -> str:
        return self.get_bytes(url).decode("utf-8", errors="replace")

    def get_json(self, url: str):
        import json

        return json.loads(self.get_bytes(url))
