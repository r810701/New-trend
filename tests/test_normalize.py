from __future__ import annotations

import unittest
from datetime import date
from newtrend.aggregate import aggregate
from newtrend.model import Article, normalize_ingredient, parse_date


class TestNormalizeIngredient(unittest.TestCase):
    def test_fda_biologic_suffix_is_stripped(self):
        self.assertEqual(normalize_ingredient("adagrasib-vikg"), "adagrasib")
        self.assertEqual(normalize_ingredient("mirvetuximab soravtansine-gynx"),
                         "mirvetuximab soravtansine")

    def test_parenthetical_alias_is_dropped(self):
        self.assertEqual(normalize_ingredient("lecanemab (BAN2401)"), "lecanemab")

    def test_salt_form_does_not_split_one_drug_into_two(self):
        self.assertEqual(normalize_ingredient("sotorasib sodium"), "sotorasib")
        self.assertEqual(normalize_ingredient("sotorasib dihydrochloride"), "sotorasib")

    def test_three_spellings_of_one_drug_collapse_to_one_key(self):
        k1 = normalize_ingredient("Tepotinib hydrochloride (EMD 1218065)")
        k2 = normalize_ingredient("tepotinib-hydr")
        k3 = normalize_ingredient("TEPOTINIB")
        self.assertEqual(k1, "tepotinib")
        self.assertEqual(k1, k2)
        self.assertEqual(k2, k3)

    def test_empty_input_returns_none_rather_than_a_guess(self):
        self.assertIsNone(normalize_ingredient(None))
        self.assertIsNone(normalize_ingredient(""))
        self.assertIsNone(normalize_ingredient("   "))


class TestParseDate(unittest.TestCase):
    def test_each_source_format(self):
        self.assertEqual(parse_date("08/04/2026"), date(2026, 8, 4))  # US FDA %m/%d/%Y
        self.assertEqual(parse_date("2026-08-04"), date(2026, 8, 4))  # ISO
        self.assertEqual(parse_date("04 August 2026"), date(2026, 8, 4))  # EMA %d %B %Y
        self.assertEqual(parse_date("2026/08/04"), date(2026, 8, 4))

    def test_unparseable_returns_none_not_today(self):
        self.assertIsNone(parse_date("not-a-date"))
        self.assertIsNone(parse_date(None))


class TestAggregate(unittest.TestCase):
    def test_same_drug_from_two_agencies_merges_and_calculates_stages(self):
        articles = [
            Article.make(source="US-FDA", title="FDA Approval", url="u1",
                         ingredient="Bevacizumab-vikg", extras={"kind": "approval"}),
            Article.make(source="EU-EMA", title="EMA Review", url="u2",
                         ingredient="Bevacizumab", extras={"orphan": True}),
        ]
        rows = aggregate(articles)
        self.assertEqual(len(rows), 1)
        # 國外 3 階段：實證、審查、核准皆達成
        foreign = rows[0]["foreign_stages"]
        self.assertEqual(len(foreign["stages"]), 3)
        self.assertTrue(foreign["stages"][0]["reached"])  # 實證
        self.assertTrue(foreign["stages"][1]["reached"])  # 審查
        self.assertTrue(foreign["stages"][2]["reached"])  # 核准
        # 台灣尚未上市
        self.assertEqual(rows[0]["gap"]["code"], "foreign_approved_tw_pending")

    def test_unreached_stages_are_marked_not_reached(self):
        articles = [
            Article.make(source="EU-EMA", title="EMA Review", url="u2",
                         ingredient="TestDrug", extras={"kind": "under_evaluation"}),
        ]
        rows = aggregate(articles)
        self.assertEqual(len(rows), 1)
        foreign = rows[0]["foreign_stages"]
        # 核准未達成 -> 標示尚未出現
        self.assertFalse(foreign["stages"][2]["reached"])
        self.assertEqual(foreign["stages"][2]["title"], "尚未出現")

    def test_tfda_without_inn_stays_separate(self):
        articles = [
            Article.make(source="US-FDA", title="a", url="u1", ingredient="Aspirin"),
            Article.make(source="TW-TFDA", title="b", url="u2", ingredient=None,
                         brand="某某新藥", extras={"license_no": "衛部藥輸字第001號"}),
        ]
        rows = aggregate(articles)
        self.assertEqual(len(rows), 2, "無 INN 的項目不該被併進任何成分")
        tw = next(r for r in rows if not r["has_inn"])
        self.assertEqual(tw["gap"]["code"], "tw_exclusive")

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
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
