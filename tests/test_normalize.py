"""ingredient_key 正規化的回歸測試。

這是整個專案唯一「算錯了不會報錯、只會安靜給出錯誤結論」的地方：
成分名收斂錯了，跨機構聲量就是假的，但報表看起來完全正常。

用 stdlib unittest，不引進 pytest —— 為了跑四個測試多一個相依不划算。
    .venv/bin/python -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from newtrend.aggregate import TAG_MULTI_AGENCY, TAG_NO_INN, aggregate  # noqa: E402
from newtrend.model import Article, normalize_ingredient, parse_date    # noqa: E402


class TestNormalizeIngredient(unittest.TestCase):
    def test_fda_biologic_suffix_is_stripped(self):
        """FDA 給生物製劑加 4 字母後綴，EMA 不加。不剝掉就永遠對不起來。"""
        self.assertEqual(normalize_ingredient("Bevacizumab-vikg"), "bevacizumab")
        self.assertEqual(normalize_ingredient("Bevacizumab"), "bevacizumab")

    def test_salt_form_does_not_split_one_drug_into_two(self):
        self.assertEqual(normalize_ingredient("bevacizumab sodium"), "bevacizumab")
        self.assertEqual(normalize_ingredient("Amlodipine Besylate"), "amlodipine")

    def test_parenthetical_alias_is_dropped(self):
        self.assertEqual(normalize_ingredient("Datopotamab Deruxtecan (Dato-DXd)"),
                         "datopotamab deruxtecan")

    def test_three_spellings_of_one_drug_collapse_to_one_key(self):
        keys = {normalize_ingredient(s) for s in
                ("bevacizumab-vikg", "Bevacizumab", "bevacizumab sodium")}
        self.assertEqual(len(keys), 1, f"應收斂成同一鍵，實際得到 {keys}")

    def test_empty_input_returns_none_rather_than_a_guess(self):
        for junk in (None, "", "   ", "()"):
            self.assertIsNone(normalize_ingredient(junk))


class TestParseDate(unittest.TestCase):
    def test_each_source_format(self):
        self.assertEqual(str(parse_date("7/24/2026")), "2026-07-24")       # FDA
        self.assertEqual(str(parse_date("2026-08-05T12:00:00")), "2026-08-05")  # NICE
        self.assertEqual(str(parse_date("2026-07-24")), "2026-07-24")      # TFDA
        self.assertEqual(str(parse_date("5 August 2026")), "2026-08-05")   # EMA

    def test_unparseable_returns_none_not_today(self):
        self.assertIsNone(parse_date("下週三"))


class TestAggregate(unittest.TestCase):
    def test_same_drug_from_two_agencies_merges_and_gets_linkage_tag(self):
        articles = [
            Article.make(source="US-FDA", title="a", url="u1",
                         ingredient="Bevacizumab-vikg"),
            Article.make(source="EU-EMA", title="b", url="u2",
                         ingredient="Bevacizumab"),
        ]
        rows = aggregate(articles)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["buzz_count"], 2)
        self.assertIn(TAG_MULTI_AGENCY, rows[0]["trend_tags"])

    def test_tfda_without_inn_stays_separate_and_never_claims_linkage(self):
        articles = [
            Article.make(source="US-FDA", title="a", url="u1", ingredient="Aspirin"),
            Article.make(source="TW-TFDA", title="b", url="u2", ingredient=None,
                         brand="某某錠", extras={"license_no": "衛部藥輸字第001號"}),
        ]
        rows = aggregate(articles)
        self.assertEqual(len(rows), 2, "無 INN 的項目不該被併進任何成分")
        tw = next(r for r in rows if not r["has_inn"])
        self.assertIn(TAG_NO_INN, tw["trend_tags"])
        self.assertNotIn(TAG_MULTI_AGENCY, tw["trend_tags"])

    def test_shared_list_url_does_not_collapse_the_whole_batch(self):
        """FDA 年度頁的每一筆共用同一個 URL —— 指紋只看 URL 會把整批壓成 1 筆。"""
        articles = [
            Article.make(source="US-FDA", title=f"drug {n}", url="same-page",
                         ingredient=name)
            for n, name in enumerate(["alpha", "beta", "gamma"])
        ]
        self.assertEqual(len(aggregate(articles)), 3)

    def test_genuine_duplicate_is_counted_once(self):
        dupe = dict(source="US-FDA", title="a", url="u1", ingredient="Aspirin")
        rows = aggregate([Article.make(**dupe), Article.make(**dupe)])
        self.assertEqual(rows[0]["buzz_count"], 1)


if __name__ == "__main__":
    unittest.main()
