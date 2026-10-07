-- src/features/label_definitions.sql
-- This creates a view that looks at the current and previous snapshot for a given SKU

CREATE VIEW IF NOT EXISTS sku_status_history AS
SELECT 
    url,
    source,
    scraped_at,
    stock_flag,
    LAG(stock_flag, 1) OVER (PARTITION BY url ORDER BY scraped_at) as prev_stock_flag,
    LAG(stock_flag, 2) OVER (PARTITION BY url ORDER BY scraped_at) as prev_prev_stock_flag
FROM snapshots;

-- Define True Stock-Out: False for at least 2 consecutive snapshots
CREATE VIEW IF NOT EXISTS valid_stockouts AS
SELECT * 
FROM sku_status_history
WHERE stock_flag = 'out_of_stock' 
  AND prev_stock_flag = 'out_of_stock';