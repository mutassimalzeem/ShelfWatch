import pandas as pd
import sqlite3
import os


DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "shelfwatch.db"))

def load_and_prep_data():
    conn = sqlite3.connect(DB_PATH)

    df = pd.read_sql_query("SELECT * FROM snapshots ORDER BY scraped_at ASC", conn)
    conn.close()


    df['scraped_at'] = pd.to_datetime(df['scraped_at'], utc=True)


    #   TEmporal features
    df['weekday'] = df['scraped_at'].dt.weekday
    df['hour_of_day'] = df['scraped_at'].dt.hour


    #   Binning discount depth
    df['discount_depth'] = pd.cut(df['discount_percent'].fillna(0), 
                                  bins=[-1, 0, 10, 25, 50, 100], 
                                  labels=['none', 'low', 'medium', 'high', 'clearance'])


    # Missing price indicator (Don't impute blindly, page down means price is missing)
    df['price_is_missing'] = df['price'].isnull().astype(int)
    
    # Define Target: 1 if 'out_of_stock', 0 if 'in_stock'
    df['target_stockout'] = (df['stock_flag'] == 'out_of_stock').astype(int)
    
    return df   