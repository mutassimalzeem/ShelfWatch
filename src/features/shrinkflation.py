# src/features/shrinkflation.py
import pandas as pd
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "../../shelfwatch.db")

def detect_stealth_shrinkflation():
    conn = sqlite3.connect(DB_PATH)
    
    # Query to find products where the normalized amount decreased over time, 
    # but the brand/title grouping suggests it's the same SKU family.
    # In a real environment, you'd match on a unique product ID or a fuzzy-matched group ID.
    query = """
    WITH sku_history AS (
        SELECT 
            source,
            title,
            url,
            price,
            normalized_amount,
            normalized_unit,
            scraped_at,
            LAG(normalized_amount, 1) OVER (PARTITION BY url ORDER BY scraped_at) as prev_amount
        FROM snapshots
        WHERE normalized_amount IS NOT NULL
    )
    SELECT * 
    FROM sku_history
    WHERE prev_amount > normalized_amount
      AND prev_amount IS NOT NULL;
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"Detected {len(df)} potential shrinkflation events.")
    if not df.empty:
        print(df[['source', 'title', 'prev_amount', 'normalized_amount', 'price']].head())
    
    return df

if __name__ == "__main__":
    detect_stealth_shrinkflation()