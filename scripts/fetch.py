#!/usr/bin/env python3
"""抓取各國藥政新藥動態 → data/raw_<date>.csv

這個檔只負責編排：呼叫哪些 source、套時間窗、寫檔、回報狀態。
**任何解析邏輯都不該出現在這裡** —— 加新站請到 newtrend/sources/ 加一個模組並註冊。
"""

import argparse
import csv
import json
import os
import sys
from datetime import date, datetime

from newtrend import DATA_DIR
from newtrend.aggregate import aggregate, filter_window
from newtrend.http import Fetcher
from newtrend.sources import DEFAULT_SOURCES, ENRICHERS, REGISTRY

DEFAULT_WINDOW_DAYS = 14

FIELDNAMES = ["drug_ingredient", "has_inn", "buzz_count", "source_regions",
              "company", "trend_tags", "flags", "articles_json", "latest_date"]


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sources", default=",".join(DEFAULT_SOURCES),
                   help=f"逗號分隔，可選：{'、'.join(REGISTRY)}（預設全部）")
    p.add_argument("--target-date", default=os.environ.get("TARGET_DATE"),
                   help="報告基準日 YYYY-MM-DD（預設今天；沿用舊的 TARGET_DATE 環境變數）")
    p.add_argument("--since-days", type=int, default=DEFAULT_WINDOW_DAYS,
                   help=f"往前幾天算聲量（預設 {DEFAULT_WINDOW_DAYS}）")
    p.add_argument("--offline", action="store_true", help="只讀快取，完全不連外")
    p.add_argument("--no-cache", action="store_true", help="忽略快取，強制重抓")
    p.add_argument("--no-enrich", action="store_true",
                   help="跳過 openFDA / ClinicalTrials 補充查詢")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    base_date = _resolve_date(args.target_date)
    names = [n.strip() for n in args.sources.split(",") if n.strip()]
    unknown = [n for n in names if n not in REGISTRY]
    if unknown:
        print(f"未知的來源：{', '.join(unknown)}（可選：{'、'.join(REGISTRY)}）",
              file=sys.stderr)
        return 2

    fetcher = Fetcher(offline=args.offline, use_cache=not args.no_cache,
                      cache_day=base_date)

    articles, status = [], {}
    for name in names:
        try:
            got = REGISTRY[name].fetch(fetcher, base_date)
            articles.extend(got)
            status[name] = {"ok": True, "count": len(got)}
            print(f"  {name:6s} {len(got):4d} 筆")
        except Exception as exc:                      # noqa: BLE001 —— 要記下所有失敗型態
            status[name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            print(f"  {name:6s} 失敗：{exc}", file=sys.stderr)

    if not args.no_enrich and articles:
        for name, module in ENRICHERS.items():
            try:
                filled = module.enrich(fetcher, articles)
                status[name] = {"ok": True, "enriched": filled}
                print(f"  {name:14s} 補充 {filled} 個成分")
            except Exception as exc:                  # noqa: BLE001
                # 補充失敗不影響主資料是否可用，記下來但不算整體失敗。
                status[name] = {"ok": False, "fatal": False,
                                "error": f"{type(exc).__name__}: {exc}"}
                print(f"  {name:14s} 補充失敗（不影響主資料）：{exc}", file=sys.stderr)

    windowed = filter_window(articles, base_date, args.since_days)
    results = aggregate(windowed)

    _write_csv(base_date, results)
    _write_meta(base_date, args, status, len(articles), len(windowed), len(results),
                fetcher.request_count)

    print(f"\n{base_date}：{len(articles)} 筆原始 → 時間窗內 {len(windowed)} 筆 "
          f"→ {len(results)} 個標的（HTTP 請求 {fetcher.request_count} 次）")

    failed = [n for n in names if not status.get(n, {}).get("ok")]
    if failed:
        # fail loud：半套資料看起來跟完整資料一模一樣，不出聲就會被當成完整的用。
        print(f"\n✗ 以下來源失敗：{', '.join(failed)}", file=sys.stderr)
        print("  報表仍會產生，但已在 meta.json 標記不完整。", file=sys.stderr)
        return 1

    print("✓ 全部來源成功")
    return 0


def _resolve_date(raw: str | None) -> date:
    if not raw:
        return date.today()
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except ValueError:
        print(f"日期格式看不懂：{raw!r}，改用今天", file=sys.stderr)
        return date.today()


def _write_csv(base_date: date, results: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"raw_{base_date.isoformat()}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in results:
            writer.writerow({
                **{k: row[k] for k in FIELDNAMES if k in row},
                "trend_tags": " | ".join(row["trend_tags"]),
                "articles_json": json.dumps(row["articles"], ensure_ascii=False),
            })


def _write_meta(base_date, args, status, raw_count, windowed_count,
                group_count, requests_made) -> None:
    """讓報表能標示「本期某來源失敗」—— 沒有這個檔，半套報表看起來就是完整的。"""
    path = DATA_DIR / f"raw_{base_date.isoformat()}.meta.json"
    path.write_text(json.dumps({
        "target_date": base_date.isoformat(),
        "since_days": args.since_days,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "offline": args.offline,
        "sources": status,
        "counts": {"raw": raw_count, "in_window": windowed_count,
                   "groups": group_count, "http_requests": requests_made},
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
