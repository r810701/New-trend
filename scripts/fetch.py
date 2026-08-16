from __future__ import annotations

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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from newtrend import DATA_DIR
from newtrend.aggregate import aggregate, filter_window
from newtrend.http import FetchError, Fetcher
from newtrend.sources import DEFAULT_SOURCES, ENRICHERS, REGISTRY

DEFAULT_WINDOW_DAYS = 14

FIELDNAMES = [
    "drug_ingredient", "has_inn", "brand", "company", "indication", "flags",
    "source_regions", "latest_date", "gap_code", "gap_label",
    "foreign_stages_json", "taiwan_stages_json", "gap_json", "news_json", "articles_json",
]


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sources", default=",".join(DEFAULT_SOURCES),
                   help=f"逗號分隔，可選：{'、'.join(REGISTRY)}（預設全部）")
    p.add_argument("--target-date", default=os.environ.get("TARGET_DATE"),
                   help="報告基準日 YYYY-MM-DD（預設今天；沿用 TARGET_DATE 環境變數）")
    p.add_argument("--since-days", type=int, default=DEFAULT_WINDOW_DAYS,
                   help=f"往前幾天算時間窗（預設 {DEFAULT_WINDOW_DAYS}）")
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
        except Exception as exc:  # noqa: BLE001
            status[name] = _status_from_exc(exc)
            print(f"  {name:6s} 失敗（{status[name]['reason_label']}）：{exc}",
                  file=sys.stderr)

    if not args.no_enrich and articles:
        for name, module in ENRICHERS.items():
            try:
                filled = module.enrich(fetcher, articles)
                status[name] = {"ok": True, "enriched": filled}
                print(f"  {name:14s} 補充 {filled} 個成分")
            except Exception as exc:  # noqa: BLE001
                status[name] = {**_status_from_exc(exc), "fatal": False}
                print(f"  {name:14s} 補充失敗（{status[name]['reason_label']}，"
                      f"不影響主資料）：{exc}", file=sys.stderr)

    windowed = filter_window(articles, base_date, args.since_days)
    results = aggregate(windowed)

    _write_csv(base_date, results)
    _write_meta(base_date, args, status, len(articles), len(windowed), len(results),
                fetcher.request_count)

    print(f"\n{base_date}：{len(articles)} 筆原始 → 時間窗內 {len(windowed)} 筆 "
          f"→ {len(results)} 個標的（HTTP 請求 {fetcher.request_count} 次）")

    failed = [n for n in names if not status.get(n, {}).get("ok")]
    if failed:
        print(f"\n✗ 以下來源失敗：{', '.join(failed)}", file=sys.stderr)
        print("  報表仍會產生，但已在 meta.json 標記不完整。", file=sys.stderr)
        return 1

    print("✓ 全部來源成功")
    return 0


def _status_from_exc(exc: Exception) -> dict:
    if isinstance(exc, FetchError):
        reason, status_code, label = exc.reason, exc.status_code, exc.reason_label
    else:
        reason, status_code, label = "unknown", None, "未知錯誤（非預期例外）"
    return {
        "ok": False,
        "error": f"{type(exc).__name__}: {exc}",
        "reason": reason,
        "reason_label": label,
        "status_code": status_code,
    }


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
                "drug_ingredient": row.get("drug_ingredient", ""),
                "has_inn": row.get("has_inn", True),
                "brand": row.get("brand", ""),
                "company": row.get("company", ""),
                "indication": row.get("indication", ""),
                "flags": row.get("flags", ""),
                "source_regions": row.get("source_regions", ""),
                "latest_date": row.get("latest_date", ""),
                "gap_code": row.get("gap", {}).get("code", ""),
                "gap_label": row.get("gap", {}).get("label", ""),
                "foreign_stages_json": json.dumps(row.get("foreign_stages", {}), ensure_ascii=False),
                "taiwan_stages_json": json.dumps(row.get("taiwan_stages", {}), ensure_ascii=False),
                "gap_json": json.dumps(row.get("gap", {}), ensure_ascii=False),
                "news_json": json.dumps(row.get("news_articles", []), ensure_ascii=False),
                "articles_json": json.dumps(row.get("articles", []), ensure_ascii=False),
            })


def _write_meta(base_date, args, status, raw_count, windowed_count,
                group_count, requests_made) -> None:
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
