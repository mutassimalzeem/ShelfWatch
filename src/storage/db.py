"""SQLite storage for ShelfWatch snapshots.

Ingestion is idempotent: every CSV is fingerprinted (SHA-256 of its bytes)
and recorded in `ingest_log`, so re-running on the same file is a no-op.
The CSV's own UTC `scraped_at` column is preserved when present instead of
being overwritten with a local naive timestamp.
"""
import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from src.features.pack_parser import parse_pack_size, calculate_normalized_price

import pandas as pd

DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "shelfwatch.db"))


def _connect():
    return sqlite3.connect(DB_PATH)


def init_db(conn=None):
    """Create the snapshots + ingest_log tables and indexes if missing."""
    close = False
    if conn is None:
        conn = _connect()
        close = True
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            price REAL,
            list_price REAL,
            discount_percent REAL,
            stock_flag TEXT NOT NULL,
            category_path TEXT,
            category_rank INTEGER,
            url TEXT,
            scraped_at TIMESTAMP NOT NULL,
            normalized_unit TEXT,
            normalized_amount REAL,
            price_per_100 REAL,
        );
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ingest_log (
            run_id TEXT PRIMARY KEY,
            csv_path TEXT NOT NULL,
            rows INTEGER NOT NULL,
            ingested_at TEXT NOT NULL
        );
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_source_url ON snapshots (source, url);
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_scraped_at ON snapshots (scraped_at);
    ''')
    conn.commit()
    if close:
        conn.close()


def _file_run_id(csv_path):
    h = hashlib.sha256()
    with open(csv_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest_latest_csv(csv_path: str, force: bool = False):
    """Append a combined CSV once per unique file content. Returns row count."""
    if not os.path.exists(csv_path):
        print(f"[DB] CSV file not found: {csv_path}")
        return 0

    df = pd.read_csv(csv_path)
    if df.empty:
        print(f"[DB] CSV file is empty: {csv_path}")
        return 0

    # Keep the scraper's UTC stamp; only fabricate one when absent.
    fallback = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if "scraped_at" not in df.columns:
        df["scraped_at"] = fallback
    else:
        df["scraped_at"] = df["scraped_at"].fillna(fallback)

    parsed_data = df['title'].apply(parse_pack_size)
    df['normalized_amount'] = [x[0] for x in parsed_data]
    df['normalized_unit'] = [x[1] for x in parsed_data]
    df['price_per_100'] = df.apply(lambda row: calculate_normalized_price(row['price'], row['normalized_amount'])
                                   if row['normalized_unit'] in ['g', 'ml'] else None, axis=1)
                                          

    run_id = _file_run_id(csv_path)
    conn = _connect()
    init_db(conn)
    if not force and conn.execute(
            "select 1 from ingest_log where run_id = ?", (run_id,)).fetchone():
        print(f"[DB] Already ingested (run_id {run_id[:12]}...): {csv_path}")
        conn.close()
        return 0

    df.to_sql("snapshots", conn, if_exists="append", index=False)
    conn.execute(
        "insert or replace into ingest_log (run_id, csv_path, rows, ingested_at) "
        "values (?, ?, ?, ?)",
        (run_id, csv_path, len(df),
         datetime.now(timezone.utc).isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    print(f"[DB] Ingested {len(df)} rows from {csv_path} (run_id {run_id[:12]}...).")
    return len(df)


def rebuild_snapshots(csv_path: str):
    """One-time repair: drop legacy duplicated rows, then ingest cleanly."""
    conn = _connect()
    init_db(conn)
    conn.execute("delete from snapshots")
    conn.execute("delete from ingest_log")
    conn.commit()
    conn.close()
    print("[DB] snapshots + ingest_log cleared for rebuild.")
    return ingest_latest_csv(csv_path, force=True)


if __name__ == "__main__":
    init_db()
    latest_file = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..",
        "scraper", "output", "all_products_combined.csv"))
    if os.path.exists(latest_file):
        ingest_latest_csv(latest_file)
    else:
        print(f"[DB] CSV file not found: {latest_file}")