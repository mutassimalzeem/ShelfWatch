"""Throwaway repair: rebuild all_products_combined.csv from per-source CSVs
(which the offline verify run never touched) and drop the stub history snapshot.
"""
import os
import pandas as pd
from config import OUTPUT_DIR

order = ["chaldal", "shwapno", "daraz", "othoba"]
frames = []
for src in order:
    p = os.path.join(OUTPUT_DIR, f"{src}_products.csv")
    if os.path.exists(p):
        df = pd.read_csv(p)
        if not df.empty:
            frames.append(df)
            print(f"{src}: {len(df)} rows")
if frames:
    combined = pd.concat(frames, ignore_index=True)
    out = os.path.join(OUTPUT_DIR, "all_products_combined.csv")
    combined.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"RESTORED combined: {len(combined)} rows -> {out}")
else:
    print("No per-source CSVs found; nothing to restore")

stub = os.path.join(OUTPUT_DIR, "history", "snapshot_20261006_110403.csv")
if os.path.exists(stub):
    os.remove(stub)
    print("Removed stub history snapshot:", stub)
print("RESTORE_DONE")
