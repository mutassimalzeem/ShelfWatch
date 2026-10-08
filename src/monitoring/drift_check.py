# src/monitoring/drift_check.py
import sqlite3
import pandas as pd
import os
import logging

logging.basicConfig(level=logging.INFO)
DB_PATH = os.path.join(os.path.dirname(__file__), "../../shelfwatch.db")

def check_scraper_health_and_drift():
    conn = sqlite3.connect(DB_PATH)
    
    # Compare the last 24 hours against the previous 7 days
    query_recent = "SELECT price FROM snapshots WHERE scraped_at >= date('now', '-1 day') AND price IS NOT NULL"
    query_history = "SELECT price FROM snapshots WHERE scraped_at >= date('now', '-8 day') AND scraped_at < date('now', '-1 day') AND price IS NOT NULL"
    
    recent_prices = pd.read_sql_query(query_recent, conn)['price']
    historical_prices = pd.read_sql_query(query_history, conn)['price']
    conn.close()

    if recent_prices.empty or historical_prices.empty:
        logging.warning("Not enough data to calculate drift.")
        return

    # Basic drift check: Did the mean price shift by more than 15%? 
    # (A sudden shift usually indicates a scraper bug, not hyperinflation)
    recent_mean = recent_prices.mean()
    historical_mean = historical_prices.mean()
    
    shift_percent = abs(recent_mean - historical_mean) / historical_mean * 100
    
    logging.info(f"Historical Mean Price: {historical_mean:.2f}")
    logging.info(f"Recent Mean Price: {recent_mean:.2f}")
    
    if shift_percent > 15:
        logging.error(f"DRIFT ALERT: Average price shifted by {shift_percent:.1f}%. Check the scraper selectors!")
    else:
        logging.info("Data drift is within acceptable bounds.")

if __name__ == "__main__":
    check_scraper_health_and_drift()