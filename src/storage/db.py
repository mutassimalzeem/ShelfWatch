import os, sqlite3
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(__file__), "../../shelfwatch.db")

def init_db():
    """Initialize the SQLite database and create the products table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
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
            scraped_at TIMESTAMP NOT NULL
        );
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_source_url ON snapshots (source, url);
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_scraped_at ON snapshots (scraped_at);
    ''')
    conn.commit()
    conn.close()


def ingest_latest_csv(csv_path: str):
    """Ingest the latest CSV file into the SQLite database."""
    if not os.path.exists(csv_path):
        print(f"[DB] CSV file not found: {csv_path}")
        return

    df = pd.read_csv(csv_path)
    if df.empty:
        print(f"[DB] CSV file is empty: {csv_path}")
        return

    # Add a timestamp for when the data was scraped
    df['scraped_at'] = pd.Timestamp.now()

    conn = sqlite3.connect(DB_PATH)
    df.to_sql('snapshots', conn, if_exists='append', index=False)
    conn.close()
    print(f"[DB] Ingested {len(df)} rows from {csv_path} into the database.")


if __name__ == "__main__":
    init_db()
    latest_file = os.path.join(os.path.dirname(__file__), "../../scraper/output/all_products_combined.csv")

    if os.path.exists(latest_file):
        ingest_latest_csv(latest_file)
        print(f"[DB] Ingested latest CSV: {latest_file}")