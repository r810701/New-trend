#!/usr/bin/env python3
"""data/raw_<date>.csv → reports/report_<date>.{html,xlsx}

輸出檔名的日期**取自輸入 CSV 的檔名**，不是 today()。
舊版兩邊各算各的：`TARGET_DATE=2026-01-01` 會產出 `raw_2026-01-01.csv` 但
`report_<今天>.html`，資料與檔名對不起來。
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from jinja2 import Template
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from newtrend import DATA_DIR, REPORTS_DIR

_RAW_NAME = re.compile(r"^raw_(\d{4}-\d{2}-\d{2})\.csv$")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>全球新藥熱度與上市聲量排行榜 {{ target_date }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f4f7f6; font-family: "Microsoft JhengHei", sans-serif; }
        .hero-header { background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%); color: white; padding: 2rem 0; }
        .card-insight { border-left: 5px solid #ff9f43; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        .badge-buzz { background-color: #ffeaa7; color: #d63031; font-weight: bold; border: 1px solid #fdcb6e; }
        .badge-global { background-color: #e3f2fd; color: #0d6efd; font-weight: bold; border: 1px solid #90caf9; }
        .badge-tw { background-color: #f1f3f5; color: #495057; font-weight: bold; border: 1px solid #ced4da; }
        .article-box { background-color: #f8f9fa; border-left: 3px solid #0d6efd; padding: 8px 12px; margin-bottom: 8px; border-radius: 4px; }
        .btn-verify { font-size: 0.78rem; padding: 2px 8px; font-weight: 500; }
        .src-ok { color: #1b7a43; } .src-bad { color: #c92a2a; font-weight: bold; }

        @media print {
            .no-print { display: none !important; }
            body { background-color: white; }
            .hero-header { background: #2c5364 !important; -webkit-print-color-adjust: exact; }
            .card { border: 1px solid #ccc !important; box-shadow: none !important; }
        }
    </style>
</head>
<body>
    <div class="hero-header text-center mb-4 position-relative">
        <h1>🔥 全球新藥聲量與上市趨勢排行榜</h1>
        <p class="lead mb-0">FDA／EMA／NICE／TFDA 四方來源，依藥品成分歸戶</p>
        <small class="opacity-75">報告基準日：{{ target_date }} ｜ 聲量視窗：近 {{ since_days }} 天 ｜ 本期標的：{{ total_items }} 項</small>

        <div class="position-absolute top-0 end-0 p-3 no-print">
            <button onclick="window.print()" class="btn btn-light fw-bold shadow-sm">📄 列印 / 另存 PDF</button>
        </div>
    </div>

    <div class="container mb-5">
        {% if failed_sources %}
        <div class="alert alert-danger">
            <strong>⚠ 本期資料不完整</strong>：以下來源抓取失敗 —— {{ failed_sources|join('、') }}。
            排行榜缺少這些來源的項目，跨機構聲量會被低估。
        </div>
        {% endif %}

        <div class="card card-insight p-4 bg-white rounded mb-4">
            <h5 class="text-warning fw-bold">📌 趨勢標籤定義與資料口徑</h5>
            <ul class="mb-2 text-secondary small">
                <li><span class="badge badge-buzz">🔥 高聲量關注</span>：同一成分在本期被 <strong>2 個（含）以上</strong>項目提及。</li>
                <li><span class="badge badge-global">🌍 多國/多機構聯動</span>：同一成分同時出現在 <strong>2 個以上藥政機構</strong>（US-FDA／EU-EMA／UK-NICE）。</li>
                <li><span class="badge badge-global">📈 新進觀察標的</span>：本期僅單一來源提及。</li>
                <li><span class="badge badge-tw">🇹🇼 TW 專屬・無 INN 對應</span>：TFDA 公告只有中文品名，英文成分名在 PDF 內，<strong>無法與國際來源比對</strong>，故單獨列示、不計入聯動。</li>
            </ul>
            <div class="alert alert-info py-2 px-3 mb-2 small">
                <strong>EMA 是「審查中清單」快照</strong>，不是當期新事件：該來源逐筆沒有日期，
                整份套用快照抽取日，因此<strong>不受 {{ since_days }} 天視窗限制</strong>。
                FDA／NICE／TFDA 則為當期事件，有套視窗。
            </div>
            <small class="text-muted">
                來源狀態：
                {% for name, ok in source_status %}
                    <span class="{{ 'src-ok' if ok else 'src-bad' }}">{{ name }} {{ '✓' if ok else '✗' }}</span>{% if not loop.last %} ｜ {% endif %}
                {% endfor %}
            </small>
        </div>

        <div class="card shadow-sm">
            <div class="card-header bg-white py-3">
                <h5 class="m-0 font-weight-bold text-dark">🏆 新藥聲量排行榜</h5>
            </div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0">
                        <thead class="table-dark">
                            <tr>
                                <th style="width: 4%;">#</th>
                                <th style="width: 20%;">藥物成分 (Ingredient)</th>
                                <th style="width: 9%;">聲量</th>
                                <th style="width: 16%;">趨勢標籤</th>
                                <th style="width: 10%;">屬性</th>
                                <th style="width: 32%;">佐證與來源連結</th>
                                <th style="width: 9%;">最新日期</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for item in results %}
                            <tr>
                                <td class="fw-bold text-muted">{{ loop.index }}</td>
                                <td class="fw-bold text-primary fs-6">
                                    {{ item.drug_ingredient }}<br>
                                    {% if item.company %}<small class="text-muted">({{ item.company }})</small>{% endif %}
                                </td>
                                <td><span class="badge bg-danger rounded-pill px-3 py-2">{{ item.buzz_count }}</span></td>
                                <td>
                                    {% for tag in item.trend_tags %}
                                        <span class="badge {{ tag_class(tag) }} px-2 py-1 mb-1 d-block text-start">{{ tag }}</span>
                                    {% endfor %}
                                </td>
                                <td><small class="text-secondary">{{ item.flags }}</small></td>
                                <td>
                                    {% for art in item.articles %}
                                        <div class="article-box">
                                            <div class="d-flex justify-content-between align-items-center mb-1">
                                                <strong class="text-dark small">[{{ art.source }}] {{ art.title }}</strong>
                                                <a href="{{ art.url }}" target="_blank" rel="noopener" class="btn btn-sm btn-outline-primary btn-verify ms-2">來源 ↗</a>
                                            </div>
                                            {% if art.summary %}<small class="text-secondary d-block">{{ art.summary }}</small>{% endif %}
                                        </div>
                                    {% endfor %}
                                </td>
                                <td><small class="text-muted">{{ item.latest_date }}</small></td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        <p class="text-muted small mt-3">產生時間 {{ generated_at }}</p>
    </div>
</body>
</html>
"""


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", type=Path,
                   help="指定 data/raw_<date>.csv（預設取日期最新的一份）")
    p.add_argument("--target-date", default=os.environ.get("TARGET_DATE"),
                   help="改讀該日期的 CSV（也吃 TARGET_DATE 環境變數，"
                        "與 fetch.py 配對用）")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    # 三段優先序：明指的檔 > 指定日期 > 日期最新的一份。
    # 中間那段是為了跟 fetch.py 的 TARGET_DATE 配對 —— 少了它，
    # `TARGET_DATE=2026-07-01` 跑完 fetch 再跑 render 會去渲染別天的資料。
    if args.input:
        csv_path = args.input
    elif args.target_date:
        csv_path = DATA_DIR / f"raw_{args.target_date.strip()}.csv"
    else:
        csv_path = _latest_csv()

    if csv_path is None or not csv_path.exists():
        print(f"找不到 {csv_path or 'data/raw_*.csv'} —— 先跑 scripts/fetch.py",
              file=sys.stderr)
        return 1

    target_date = _date_from_name(csv_path)
    results = _read_rows(csv_path)
    meta = _read_meta(csv_path)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    _write_xlsx(REPORTS_DIR / f"report_{target_date}.xlsx", results)
    _write_html(REPORTS_DIR / f"report_{target_date}.html", results, target_date, meta)

    print(f"✓ reports/report_{target_date}.html / .xlsx（{len(results)} 個標的）")
    if meta.get("_failed"):
        print(f"  ⚠ 本期有來源失敗：{', '.join(meta['_failed'])}（報表已標示）")
    return 0


def _latest_csv() -> Path | None:
    """按檔名的日期挑最新，不是 ctime。

    舊版用 os.path.getctime：重跑一個舊日期會讓那份剛寫出的舊資料勝出。
    """
    dated = []
    for path in DATA_DIR.glob("raw_*.csv"):
        m = _RAW_NAME.match(path.name)
        if m:
            dated.append((m.group(1), path))
    return max(dated)[1] if dated else None


def _date_from_name(path: Path) -> str:
    m = _RAW_NAME.match(path.name)
    return m.group(1) if m else datetime.now().strftime("%Y-%m-%d")


def _read_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            row["articles"] = json.loads(row.get("articles_json") or "[]")
            row["trend_tags"] = [t for t in (row.get("trend_tags") or "").split(" | ") if t]
            row["buzz_count"] = int(row.get("buzz_count") or 0)
            rows.append(row)
    return rows


def _read_meta(csv_path: Path) -> dict:
    meta_path = csv_path.with_name(csv_path.stem + ".meta.json")
    if not meta_path.exists():
        return {}
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    # fatal=False 是補充查詢（openFDA / ClinicalTrials）失敗，不算資料不完整。
    meta["_failed"] = [n for n, s in (meta.get("sources") or {}).items()
                       if not s.get("ok") and s.get("fatal", True)]
    return meta


def _tag_class(tag: str) -> str:
    if "高聲量" in tag:
        return "badge-buzz"
    if "TW 專屬" in tag:
        return "badge-tw"
    return "badge-global"


def _write_html(path: Path, results, target_date: str, meta: dict) -> None:
    sources = meta.get("sources") or {}
    html = Template(HTML_TEMPLATE).render(
        results=results,
        total_items=len(results),
        target_date=target_date,
        since_days=meta.get("since_days", 14),
        failed_sources=meta.get("_failed") or [],
        source_status=[(n, s.get("ok", False)) for n, s in sources.items()],
        generated_at=meta.get("generated_at",
                              datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        tag_class=_tag_class,
    )
    path.write_text(html, encoding="utf-8")


def _write_xlsx(path: Path, results) -> None:
    """兩個分頁。舊版把整包 articles JSON 塞進一格，實際上是不能看的。"""
    wb = Workbook()

    rank = wb.active
    rank.title = "排行榜"
    _header(rank, ["#", "藥物成分", "有無 INN", "聲量", "來源機構", "廠商",
                   "趨勢標籤", "屬性", "最新日期"])
    for i, row in enumerate(results, 1):
        rank.append([i, row["drug_ingredient"],
                     "有" if row.get("has_inn") == "True" else "無",
                     row["buzz_count"], row.get("source_regions", ""),
                     row.get("company", ""), " | ".join(row["trend_tags"]),
                     row.get("flags", ""), row.get("latest_date", "")])

    detail = wb.create_sheet("文章明細")
    _header(detail, ["藥物成分", "來源", "標題", "摘要", "日期", "連結"])
    for row in results:
        for art in row["articles"]:
            detail.append([row["drug_ingredient"], art.get("source", ""),
                           art.get("title", ""), art.get("summary", ""),
                           art.get("date", ""), art.get("url", "")])

    for sheet, widths in ((rank, [5, 32, 9, 7, 22, 26, 30, 20, 12]),
                          (detail, [28, 10, 52, 60, 12, 46])):
        for col, width in enumerate(widths, 1):
            sheet.column_dimensions[get_column_letter(col)].width = width
        sheet.freeze_panes = "A2"

    wb.save(path)


def _header(sheet, names: list[str]) -> None:
    sheet.append(names)
    fill = PatternFill("solid", fgColor="2C5364")
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(vertical="center")


if __name__ == "__main__":
    sys.exit(main())
