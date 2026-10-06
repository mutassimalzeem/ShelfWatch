"""Throwaway verification: scraped_at column + history snapshot ledger in main.run_all.
Stubs the four scraper modules so no network access is needed.
"""
import sys
import types
import os
import pandas as pd
import main
from config import OUTPUT_DIR


def make_df(source, n):
    return pd.DataFrame([{
        "source": source,
        "title": f"{source} item {i}",
        "price": 10.0 + i,
        "list_price": None,
        "discount_percent": None,
        "stock_flag": "in_stock",
        "category_path": "test",
        "category_rank": i,
        "url": "",
    } for i in range(n)])


stubs = {
    "scraper_chaldal": ("scrape_chaldal", make_df("chaldal", 3)),
    "scraper_shwapno": ("scrape_shwapno", make_df("shwapno", 2)),
    "scraper_daraz": ("scrape_daraz", make_df("daraz", 2)),
    "scraper_othoba": ("scrape_othoba", make_df("othoba", 1)),
}
for modname, (funcname, df) in stubs.items():
    mod = types.ModuleType(modname)
    setattr(mod, funcname, lambda df=df: df)
    sys.modules[modname] = mod

combined = main.run_all()
assert "scraped_at" in combined.columns, "scraped_at column missing"
assert combined["scraped_at"].notna().all(), "scraped_at has NaN values"

history_dir = os.path.join(OUTPUT_DIR, "history")
files = sorted(os.listdir(history_dir))
assert files, "no history snapshots written"
latest = os.path.join(history_dir, files[-1])
snap = pd.read_csv(latest)
assert "scraped_at" in snap.columns, "snapshot lacks scraped_at"
assert len(snap) == len(combined), "snapshot row count mismatch"
print("VERIFY_OK:", files[-1], "| rows:", len(snap),
      "| scraped_at:", snap["scraped_at"].iloc[0])
