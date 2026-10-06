"""
Configuration for Bangladesh Grocery Scraper
Target fields: title, price, list_price, stock_flag, category_path, discount_badge, category_rank
"""
import os

# Output directory
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Request settings
REQUEST_TIMEOUT = 30
CRAWL_DELAY = 3  # seconds between requests (polite scraping)
MAX_RETRIES = 3
MAX_PAGES = 5  # max pagination pages to follow per category
HISTORY_KEEP = 60  # rolling count of snapshot CSVs retained in output/history

# Daraz category grids are bot-check blocked; the only SSR data is the
# /catalog/ flash-sale strip, which is non-grocery noise. Disabled by
# default; run `python main.py daraz` to force it.
DARAZ_ENABLED = False

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
}

# --- Chaldal ---
CHALDAL_BASE = "https://chaldal.com"
CHALDAL_CATEGORIES = [
    "/fresh-fruit",
    "/fresh-vegetable",
    "/rices",
    "/oil",
    "/spices",
    "/noodles",
    "/soft-drinks",
    "/laundry",
]

# --- Shwapno ---
SHWAPNO_BASE = "https://www.shwapno.com"
SHWAPNO_CATEGORIES = [
    "/oil",
    "/soybean-oil",
    "/rice",
    "/spices",
    "/fish",
    "/meat",
    "/dairy",
    "/frozen-snacks-others",
]

# --- Daraz ---
DARAZ_BASE = "https://www.daraz.com.bd"
DARAZ_CATEGORIES = [
    "/fruits-meat-frozen/",
    "/breakfast/",
    "/cooking-ingredients/",
    "/snacks-beverages/",
    "/dairy-eggs/",
    "/herbs-spices-sauces/",
    "/laundry-household/",
]

# --- Othoba ---
OTHOBA_BASE = "https://www.othoba.com"
OTHOBA_CATEGORIES = [
    "/household-essentials",
    "/daily-bazar",
]
