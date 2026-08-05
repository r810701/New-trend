"""資料模型與成分名正規化。

`ingredient_key` 是整個專案的關鍵：跨源聲量能不能算對，全看同一個成分在
FDA / EMA / NICE 三邊會不會收斂到同一個鍵。
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime

# FDA 給生物製劑加的 4 字母後綴（bevacizumab-vikg、trastuzumab-dkst…）。
# 不剝掉的話，同一個成分在 FDA 與 EMA 永遠對不起來。
_BIOLOGIC_SUFFIX = re.compile(r"-[a-z]{4}$")

# 鹽類／酯類尾綴。同一個活性成分換個鹽不該算成兩個藥。
_SALTS = (
    "dihydrochloride", "hydrochloride", "hydrobromide", "besylate", "tosylate",
    "mesylate", "maleate", "tartrate", "citrate", "acetate", "phosphate",
    "succinate", "fumarate", "sulphate", "sulfate", "sodium", "potassium",
    "calcium", "magnesium",
)

_PAREN = re.compile(r"\([^)]*\)")
_NON_NAME = re.compile(r"[^a-z0-9 \-/]+")


def normalize_ingredient(raw: str | None) -> str | None:
    """成分名 → 比對用的鍵。取不出東西就回 None，不要猜。

    >>> normalize_ingredient("Bevacizumab-vikg")
    'bevacizumab'
    >>> normalize_ingredient("Datopotamab Deruxtecan (Dato-DXd)")
    'datopotamab deruxtecan'
    """
    if not raw:
        return None

    name = _PAREN.sub(" ", raw).lower()          # 去掉括號內的別名／代號
    name = _NON_NAME.sub(" ", name)
    name = re.sub(r"\s+", " ", name).strip(" -/")
    if not name:
        return None

    name = _BIOLOGIC_SUFFIX.sub("", name)

    # 鹽類可能疊兩層（"…sodium hydrate"），所以剝到不動為止。
    changed = True
    while changed:
        changed = False
        for salt in _SALTS:
            if name.endswith(" " + salt):
                name = name[: -(len(salt) + 1)].strip()
                changed = True

    return name or None


def parse_date(raw: str | None) -> date | None:
    """吃各站不同的日期寫法，認不出來就回 None（不要用 today 假裝有日期）。"""
    if not raw:
        return None
    text = raw.strip()[:19]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d %B %Y", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class Article:
    source: str                          # "US-FDA" / "EU-EMA" / "UK-NICE" / "TW-TFDA"
    title: str
    url: str
    pub_date: date | None = None
    ingredient: str | None = None        # 顯示用原字串
    ingredient_key: str | None = None    # 比對用；TFDA 一律 None，見 CLAUDE.md §4
    brand: str | None = None
    company: str | None = None
    summary: str = ""
    extras: dict = field(default_factory=dict)

    @classmethod
    def make(cls, *, ingredient: str | None = None, **kwargs) -> "Article":
        """統一入口，確保 ingredient_key 一定經過正規化，不會有人忘了呼叫。"""
        return cls(ingredient=ingredient,
                   ingredient_key=normalize_ingredient(ingredient),
                   **kwargs)

    @property
    def has_inn(self) -> bool:
        return self.ingredient_key is not None

    @property
    def group_key(self) -> str:
        """有 INN 就按成分歸戶；沒有的（TFDA）各自成一組，不會誤併。"""
        if self.ingredient_key:
            return self.ingredient_key
        return f"{self.source}::{self.extras.get('license_no') or self.url}"
