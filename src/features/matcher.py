"""Retailers use slightly different naming conventions (e.g., "Oreo Original 120g" vs. "Oreo Biscuit Regular 120 gm").
Fuzzy matching calculates a string similarity score to bridge this gap.
"""

import os, sqlite3
from rapidfuzz import fuzz, process
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(__file__), "../../shelfwatch.db")

def find_matches_across_stores(target_title, store_df, threshold = 80):
    """
    Find matches for a target title across different stores using fuzzy matching.

    Args:
        target_title (str): The title to match against.
        store_df (pd.DataFrame): DataFrame containing store data with 'title' column.
        threshold (int): Minimum similarity score to consider a match."""

    choices = store_df['title'].tolist()
    matches = process.extract(target_title, choices, scorer=fuzz.token_sort_ratio, limit=3)

    valid_matches = [match for match in matches if match[1] >= threshold]

    return valid_matches

def run_matching_demo():
    """
    Demonstrates the fuzzy matching functionality by comparing a target title against titles from different stores.
    """
    # Connect to the SQLite database
    conn = sqlite3.connect(DB_PATH)

    # Load data from the database into a DataFrame
    query = """SELECT source, title, url, normalized_amount, normalized_unit 
    FROM snapshots 
    WHERE scraped_at = (SELECT MAX(scraped_at) FROM snapshots)
    """
    df = pd.read_sql_query(query, conn)

    # Close the database connection
    conn.close()

    if df.empty:
        print("No data found in the database.")
        return

    # Example: Match Chaldal products against Shwapno products
    chaldal_products = df[df['source'] == 'chaldal']
    shwapno_products = df[df['source'] == 'shwapno']
    
    if chaldal_products.empty or shwapno_products.empty:
        print("Need data from at least two sources to run cross-matching.")
        return
        
    print("=== Cross-Retailer Match Candidates ===")
    sample_targets = chaldal_products.head(10)
    for _, row in sample_targets.iterrows():
        matches = find_matches_across_stores(row['title'], shwapno_products)
        if matches:
            print(f"Target (Chaldal): {row['title']} | Unit: {row['normalized_amount']}{row['normalized_unit']}")
            for match_title, score, _ in matches:
                print(f"  -> Match (Shwapno): {match_title} (Score: {score:.1f})")

if __name__ == "__main__":
    run_matching_demo()