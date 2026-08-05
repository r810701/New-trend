"""New-trend：跨國藥政新藥動態擷取與報表產生。"""

from pathlib import Path

# 從本檔位置反推 repo 根，讓 fetch.py / render_report.py 從任何 cwd 執行結果都一致。
# （GitHub Actions 從 repo 根跑，人通常也是，但 cwd 不該是正確性的前提。）
ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
CACHE_DIR = DATA_DIR / ".cache"

__all__ = ["ROOT", "DATA_DIR", "REPORTS_DIR", "CACHE_DIR"]
