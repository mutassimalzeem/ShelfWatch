from fastapi import FastAPI, HTTPException
import sqlite3, os
import pandas as pd


app = FastAPI(title = "ShelfWatch API", description = "Grocery availability and true price intelligence", version = "1.0.0")

DB_PATH = os.path.join(os.path.dirname(__file__), "../shelfwatch.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/")
def read_root():
    return {"message": "Welcome to the ShelfWatch API!"}

@app.get("/api/stockouts/current")
def get_current_stockouts():
    conn = get_db_connection()
    query = """
    SELECT source, title, url, price, normalized_amount, normalized_unit, scraped_at
    FROM snapshots
    WHERE normalized_amount IS NULL
    ORDER BY scraped_at DESC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        raise HTTPException(status_code=404, detail="No current stockouts found.")
    
    return df.to_dict(orient="records")


@app.get("/api/shrinkflation/alerts")
def get_shrinkflation_alerts():
    conn = get_db_connection()
    
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
    SELECT source, title, url, price, normalized_amount, normalized_unit, scraped_at, prev_amount
    FROM sku_history
    WHERE prev_amount IS NOT NULL
      AND normalized_amount < prev_amount
    ORDER BY scraped_at DESC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        raise HTTPException(status_code=404, detail="No shrinkflation alerts found.")
    
    return df.to_dict(orient="records")
