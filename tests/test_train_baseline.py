"""Baseline model guards + selftest pipeline. Run: python -m unittest discover -s tests -v"""
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src", "models"))

import train_baseline  # noqa: E402


class TestBaselineGuards(unittest.TestCase):
    def test_too_few_rows_returns_none(self):
        df = train_baseline._synthetic_fixture(n_rows=50)
        self.assertIsNone(train_baseline.run_baseline(df))

    def test_single_class_returns_none(self):
        df = train_baseline._synthetic_fixture(n_rows=1200, positive_rate=0.0)
        self.assertIsNone(train_baseline.run_baseline(df))

    def test_selftest_fixture_trains_all_folds(self):
        metrics = train_baseline.run_baseline(train_baseline._synthetic_fixture())
        self.assertEqual(len(metrics), 3)
        for m in metrics:
            self.assertGreater(m["pr_auc"], 0.5)
            self.assertGreater(m["f2"], 0.0)


if __name__ == "__main__":
    unittest.main()
