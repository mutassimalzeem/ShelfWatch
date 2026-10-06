"""
Bangladesh Grocery Scraper - Main Runner
Runs all scrapers and combines results into a single dataset.

Usage:
    python main.py              # Run all scrapers
    python main.py chaldal      # Run only Chaldal
    python main.py shwapno      # Run only Shwapno
    python main.py daraz        # Run only Daraz
    python main.py othoba       # Run only Othoba
"""
import sys
import os
from datetime import datetime, timezone
import pandas as pd
from config import OUTPUT_DIR, DARAZ_ENABLED, HISTORY_KEEP

# Scraped titles/prices contain Bengali text; redirected stdout on Windows
# defaults to cp1252 and would crash the run with UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def _prune_history(history_dir, keep):
    """Retain only the newest `keep` snapshot CSVs so the ledger stays bounded."""
    if keep <= 0:
        return
    snaps = sorted(f for f in os.listdir(history_dir)
                   if f.startswith("snapshot_") and f.endswith(".csv"))
    for old in snaps[:-keep]:
        try:
            os.remove(os.path.join(history_dir, old))
            print(f"[HISTORY] pruned old snapshot {old}")
        except OSError:
            pass


def run_all(sources=None):
    results = {}

    if sources is None or "chaldal" in sources:
        try:
            from scraper_chaldal import scrape_chaldal
            results["chaldal"] = scrape_chaldal()
        except Exception as e:
            print(f"[CHALDAL] Fatal error: {e}")
            results["chaldal"] = pd.DataFrame()

    if sources is None or "shwapno" in sources:
        try:
            from scraper_shwapno import scrape_shwapno
            results["shwapno"] = scrape_shwapno()
        except Exception as e:
            print(f"[SHWAPNO] Fatal error: {e}")
            results["shwapno"] = pd.DataFrame()

    if sources is None and not DARAZ_ENABLED:
        print("[DARAZ] Skipped (DARAZ_ENABLED=False in config.py; "
              "run `python main.py daraz` to force).")
    elif sources is None or "daraz" in sources:
        try:
            from scraper_daraz import scrape_daraz
            results["daraz"] = scrape_daraz()
        except Exception as e:
            print(f"[DARAZ] Fatal error: {e}")
            results["daraz"] = pd.DataFrame()

    if sources is None or "othoba" in sources:
        try:
            from scraper_othoba import scrape_othoba
            results["othoba"] = scrape_othoba()
        except Exception as e:
            print(f"[OTHOBA] Fatal error: {e}")
            results["othoba"] = pd.DataFrame()

    # Combine all results
    frames = [df for df in results.values() if df is not None and not df.empty]
    if frames:
        combined = pd.concat(frames, ignore_index=True)

        # Timestamp every row so snapshots are usable for time-series modeling
        now_utc = datetime.now(timezone.utc)
        stamp = now_utc.isoformat(timespec="seconds")
        if "scraped_at" not in combined.columns:
            combined["scraped_at"] = stamp
        else:
            combined["scraped_at"] = combined["scraped_at"].fillna(stamp)

        # Save latest snapshot
        out_path = os.path.join(OUTPUT_DIR, "all_products_combined.csv")
        combined.to_csv(out_path, index=False, encoding="utf-8-sig")

        # Save historical snapshot ledger (crucial for time-series modeling)
        history_dir = os.path.join(OUTPUT_DIR, "history")
        os.makedirs(history_dir, exist_ok=True)
        snapshot_path = os.path.join(
            history_dir, f"snapshot_{now_utc.strftime('%Y%m%d_%H%M%S')}.csv")
        combined.to_csv(snapshot_path, index=False, encoding="utf-8-sig")
        _prune_history(history_dir, HISTORY_KEEP)

        print(f"\n{'='*60}")
        print(f"COMBINED RESULTS: {len(combined)} total products")
        print(f"Saved to: {out_path}")
        print(f"History snapshot: {snapshot_path}")
        print(f"{'='*60}")
        print(f"\nBreakdown by source:")
        print(combined["source"].value_counts().to_string())
        print(f"\nColumns: {list(combined.columns)}")
        print(f"\nSample rows:")
        print(combined.head(10).to_string())
        return combined
    else:
        print("\nNo products scraped from any source.")
        return pd.DataFrame()


if __name__ == "__main__":
    args = sys.argv[1:]
    sources = args if args else None
    run_all(sources)
