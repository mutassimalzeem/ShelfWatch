"""Stdlib smoke tests. Run from repo root:  python -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scraper"))
sys.path.insert(0, os.path.join(REPO_ROOT, "src", "features"))

import main as scraper_main  # noqa: E402
from pack_parser import (parse_pack_size,  # noqa: E402
                         calculate_normalized_price)
from scraper_chaldal import parse_price  # noqa: E402
from scraper_daraz import _paginated_url  # noqa: E402
from scraper_othoba import _clean_title  # noqa: E402


class TestParsePrice(unittest.TestCase):
    def test_currency_and_commas(self):
        self.assertEqual(parse_price("৳ 1,070"), 1070.0)
        self.assertEqual(parse_price("Tk 42"), 42.0)

    def test_empty(self):
        self.assertIsNone(parse_price(""))
        self.assertIsNone(parse_price(None))


class TestCleanTitle(unittest.TestCase):
    def test_strips_buy_now(self):
        self.assertEqual(_clean_title("Buy Now      Rose & Ceramide Face Cream"),
                         "Rose & Ceramide Face Cream")

    def test_strips_nav_blob(self):
        raw = ("আই নীতিEMI Policy   গ্রাহক সহায়তাCall us at 09613800800  "
               "Hot Deals of the Day  More Products    MUMUSO Cotton Pads (180 Counts)")
        self.assertEqual(_clean_title(raw), "MUMUSO Cotton Pads (180 Counts)")

    def test_rejects_garbage(self):
        self.assertIsNone(_clean_title(None))
        self.assertIsNone(_clean_title("   "))


class TestPaginatedUrl(unittest.TestCase):
    def test_page_one_unchanged(self):
        self.assertEqual(_paginated_url("https://x/y/", 1), "https://x/y/")

    def test_appends_and_merges(self):
        self.assertEqual(_paginated_url("https://x/y/", 2), "https://x/y/?page=2")
        self.assertEqual(_paginated_url("https://x/y/?a=1", 3),
                         "https://x/y/?a=1&page=3")


class TestPackParser(unittest.TestCase):
    def test_volume(self):
        self.assertEqual(parse_pack_size("ACI Pure Mustard Oil 1Ltr."),
                         (1.0, "l", 1000.0))

    def test_weight_kg(self):
        self.assertEqual(parse_pack_size("PRAN Minicate Rice 5kg"),
                         (5.0, "kg", 5000.0))

    def test_grams_with_plusminus(self):
        self.assertEqual(parse_pack_size("Malta ± 50 gm"), (50.0, "g", 50.0))

    def test_piece(self):
        self.assertEqual(parse_pack_size("Daab (Green Coconut) each"),
                         (1.0, "piece", None))

    def test_none(self):
        self.assertEqual(parse_pack_size("Banana Chompa (Ready To Eat)"),
                         (None, None, None))
        self.assertEqual(parse_pack_size(None), (None, None, None))

    def test_normalized_price(self):
        self.assertEqual(calculate_normalized_price(380.0, 1000.0), 38.0)
        self.assertIsNone(calculate_normalized_price(380.0, None))
        self.assertIsNone(calculate_normalized_price(380.0, 0))


class TestHistoryPruning(unittest.TestCase):
    def test_prune_keeps_newest(self):
        with tempfile.TemporaryDirectory() as td:
            for i in range(5):
                open(os.path.join(td, f"snapshot_2026010{i}_000000.csv"), "w").close()
            open(os.path.join(td, "unrelated.csv"), "w").close()
            scraper_main._prune_history(td, 2)
            left = sorted(f for f in os.listdir(td) if f.startswith("snapshot_"))
            self.assertEqual(left, ["snapshot_20260103_000000.csv",
                                    "snapshot_20260104_000000.csv"])


if __name__ == "__main__":
    unittest.main()
