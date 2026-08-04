#!/usr/bin/env python3
"""
scripts/render_report.py
讀取 data/articles.csv，產生 reports/report_YYYYMMDD.html，並在 reports/ 放圖檔
"""
import os
from datetime import datetime
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader

DATA_CSV = "data/articles.csv"
OUT_DIR = "reports"
TEMPLATE_DIR = "templates"
TEMPLATE_NAME = "report.html"

os.makedirs(OUT_DIR, exist_ok=True)

def make_plot(df, outpath):
    # simple count by domain
    counts = df['domain'].value_counts().head(10)
    plt.figure(figsize=(8,4))
    counts.plot(kind='bar')
    plt.title('Top source domains')
    plt.tight_layout()
    plt.savefig(outpath)
    plt.close()

def render(df):
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    tpl = env.get_template(TEMPLATE_NAME)
    date = datetime.utcnow().strftime('%Y-%m-%d')
    fig = f"domain_counts_{date}.png"
    figpath = os.path.join(OUT_DIR, fig)
    make_plot(df, figpath)

    html_out = os.path.join(OUT_DIR, f"report_{date}.html")
    with open(html_out, 'w', encoding='utf-8') as f:
        f.write(tpl.render(date=date, table=df.to_dict(orient='records'), fig=fig))
    print('Wrote', html_out)

def main():
    if not os.path.exists(DATA_CSV):
        print('No data file found:', DATA_CSV)
        return
    df = pd.read_csv(DATA_CSV)
    render(df)

if __name__ == '__main__':
    main()
