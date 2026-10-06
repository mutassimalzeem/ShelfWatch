import os
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "../../scraper/output/all_products_combined.csv")

def audit():
    if not os.path.exists(DATA_DIR):
        print(f"[AUDIT] Data file not found: {DATA_DIR}")
        return

    df = pd.read_csv(DATA_DIR)
    print(f"[AUDIT] Auditing data from: {DATA_DIR}")
    print(f"[AUDIT] Total rows: {len(df)}")
    print(f"[AUDIT] Columns: {list(df.columns)}")
    print(f"Source breakdown:\n{df['source'].value_counts()}\n")


    print("=== Missing Values Summary ===")
    print(df.isnull().sum())
    print("\n=== STOCK STATUS DISTRIBUTION ===")
    print(df.groupby(['source', 'stock_flag']).size().unstack(fill_value=0))

    print("\n=== PRICE INTEGRITY CHECK ===")
    zero_price = (df['price'] <= 0).sum()
    print(f"Rows with price <= 0: {zero_price}")

    # Check for potential 10x typos using IQR per category
    sample_anomalies = df[df['price'] > df['price'].quantile(0.99)]
    print(f"Top 1% price outliers count: {len(sample_anomalies)}")

if __name__ == "__main__":
    audit()