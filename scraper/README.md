# Bangladesh Grocery Scraper

Scrapes product data from Bangladeshi grocery/e-commerce platforms for model training.

## Target Fields
- `title` — Product name
- `price` — Current selling price (BDT)
- `list_price` — Original/regular price before discount
- `discount_percent` — Discount percentage (calculated or from badge)
- `stock_flag` — `in_stock` / `out_of_stock` / `unknown`
- `category_path` — Breadcrumb path (e.g., "Food > Fruits & Vegetables > Fresh Fruits")
- `category_rank` — Position in the category listing (1-based)
- `source` — Platform name
- `url` — Page URL where product was found

## Sources

| Platform | Method | Notes |
|----------|--------|-------|
| **Chaldal** | `requests` + BS4 (SSR) | Best data quality, products in HTML |
| **Shwapno** | Playwright (CSR) or HTTP fallback | JS-rendered; needs Playwright for full data |
| **Daraz BD** | `requests` + BS4 (Hybrid) | Flash Sale SSR; category grids may need JS |
| **Othoba** | `requests` + BS4 (SSR) | nopCommerce; good alternative source |

## Setup

```bash
pip install -r requirements.txt
# For Shwapno full scraping:
playwright install chromium
```

## Usage

```bash
# Run all scrapers
python main.py

# Run individual scrapers
python main.py chaldal
python main.py shwapno
python main.py daraz
python main.py othoba

# Or run individual scraper files directly
python scraper_chaldal.py
python scraper_othoba.py

# Daraz is disabled by default (bot-check blocked, non-grocery noise);
# force it with:
python main.py daraz
```

## Output

CSV files saved to `scraper/output/`:
- `chaldal_products.csv`
- `shwapno_products.csv`
- `daraz_products.csv` (only when Daraz is enabled/forced)
- `othoba_products.csv`
- `all_products_combined.csv` (combined; every row carries a UTC `scraped_at`)
- `history/snapshot_<UTC timestamp>.csv` — snapshot ledger for time-series
  modeling; oldest snapshots are pruned beyond `HISTORY_KEEP` (config.py)

## Database & Scheduling

- `python src/storage/db.py` ingests `all_products_combined.csv` into
  `shelfwatch.db` (table `snapshots`). Ingestion is idempotent per file
  content (SHA-256 run id stored in `ingest_log`) and preserves the CSV's
  UTC `scraped_at` instead of re-stamping with local time.
- `python run_crawler_scheduler.py` runs scrape + ingest every 6 hours using
  absolute paths, a UTF-8 child environment and a `scheduler.lock` lock file.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Legal Compliance Notes

- **Foodpanda BD**: EXCLUDED — explicitly blocks GPTBot/AI training bots
- **Chaldal**: Content signals framework present; no explicit ai-train ban
- **Shwapno**: robots.txt allows product pages; avoids query-param URLs
- **Daraz**: robots.txt allows product pages; no AI bot restrictions found
- **Othoba**: robots.txt allows product pages (nopCommerce defaults)
- All scrapers use 3-second crawl delay and polite User-Agent
- Only public product data is collected (names, prices, categories)

## Limitations

- Shwapno requires Playwright for full product data (CSR site)
- Daraz category grids may return empty without JS rendering
- Exact CSS selectors may need updating if sites change their markup
- Stock flags are inferred from visible text; may not reflect real-time inventory
- Othoba pagination follows discovered pager hrefs; if markup changes, only page 1 is scraped
- Daraz category grids are bot-check blocked; only the /catalog/ flash-sale strip is reachable
