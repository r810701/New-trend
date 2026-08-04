#!/usr/bin/env python3
"""
scripts/render_report.py
- 讀取 data/articles_detailed.csv
- 產生：
  - reports/report_YYYY-MM-DD.html（月報樣式）
  - reports/report_YYYY-MM-DD.xlsx（Excel）
  - 圖表：phase distribution、top sponsors
"""
import os
from datetime import datetime
from collections import Counter

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader

DATA_CSV = "data/articles_detailed.csv"
OUT_DIR = "reports"
TEMPLATE_DIR = "templates"
TEMPLATE_NAME = "report_detailed.html"

os.makedirs(OUT_DIR, exist_ok=True)


def safe_read_csv(path):
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception as e:
        print("Error reading CSV:", e)
        return pd.DataFrame(columns=["timestamp", "seed", "url", "domain", "title", "drug_name", "indication", "sponsor", "phase", "date", "summary"])


def make_bar_chart(values, title, outpath, top_n=10):
    if values.empty:
        return
    counts = values.value_counts().head(top_n)
    plt.figure(figsize=(8, 4))
    counts.plot(kind="bar", color="#2c7fb8")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(outpath)
    plt.close()


def render(df):
    date = datetime.utcnow().strftime("%Y-%m-%d")
    # plots
    ph_fig = f"phase_distribution_{date}.png"
    sponsor_fig = f"top_sponsors_{date}.png"
    ph_path = os.path.join(OUT_DIR, ph_fig)
    sp_path = os.path.join(OUT_DIR, sponsor_fig)

    if "phase" in df.columns:
        make_bar_chart(df["phase"].replace("", "Unknown"), "Phase / Approval Status Distribution", ph_path)
    if "sponsor" in df.columns:
        make_bar_chart(df["sponsor"].replace("", "Unknown"), "Top Sponsors (by mentions)", sp_path)

    # Excel output
    xlsx_out = os.path.join(OUT_DIR, f"report_{date}.xlsx")
    try:
        df.to_excel(xlsx_out, index=False)
    except Exception as e:
        print("Failed to write Excel:", e)

    # Jinja2 render
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    tpl = env.get_template(TEMPLATE_NAME)
    exec_summary = {
        "generated_at": date,
        "total_records": len(df),
        "unique_drugs": len(df["drug_name"].replace("", pd.NA).dropna().unique()) if "drug_name" in df.columns else 0,
        "unique_sponsors": len(df["sponsor"].replace("", pd.NA).dropna().unique()) if "sponsor" in df.columns else 0,
    }

    html_out = os.path.join(OUT_DIR, f"report_{date}.html")
    with open(html_out, "w", encoding="utf-8") as f:
        f.write(tpl.render(date=date, exec_summary=exec_summary, table=df.to_dict(orient="records"),
                           ph_fig=os.path.basename(ph_path), sp_fig=os.path.basename(sp_path)))
    print("Wrote", html_out)
    print("Wrote", xlsx_out)


def main():
    df = safe_read_csv(DATA_CSV)
    if df.empty:
        print("No data found; please run fetch.py first.")
        return
    # basic cleaning: trim strings
    for c in ["title", "drug_name", "indication", "sponsor", "phase", "date", "summary"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    render(df)


if __name__ == "__main__":
    main()
