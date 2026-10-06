"""
Daraz BD Scraper - Hybrid Rendering
Uses requests + BeautifulSoup; falls back to text parsing.
"""
import re, os, time, json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
from config import (DARAZ_BASE, DARAZ_CATEGORIES, HEADERS,
                    REQUEST_TIMEOUT, CRAWL_DELAY, OUTPUT_DIR)


def parse_price(price_text):
    if not price_text:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(price_text).replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


def scrape_daraz_page(url, session):
    products = []
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [ERROR] {url}: {e}")
        return products

    soup = BeautifulSoup(resp.text, "lxml")

    # 1. Try embedded JSON
    for script in soup.find_all("script"):
        text = script.string or ""
        if "listItems" in text:
            m = re.search(r'"listItems"\s*:\s*(\[.+?\])\s*[,}]', text, re.DOTALL)
            if m:
                try:
                    items = json.loads(m.group(1))
                    for rank, it in enumerate(items, 1):
                        products.append({
                            "source": "daraz",
                            "title": it.get("name", ""),
                            "price": parse_price(str(it.get("price", ""))),
                            "list_price": parse_price(str(it.get("originalPrice", ""))),
                            "discount_percent": it.get("discount"),
                            "stock_flag": "in_stock",
                            "category_path": "",
                            "category_rank": rank,
                            "url": urljoin(DARAZ_BASE, it.get("itemUrl", ""))})
                except json.JSONDecodeError:
                    pass
    if products:
        return products

    # 2. Parse visible text: Name price original -X%
    text = soup.get_text()
    pattern = r"(.{10,120}?)\s*৳\s*([\d,]+)\s*৳\s*([\d,]+)\s*-(\d+)%"
    for rank, m in enumerate(re.finditer(pattern, text), 1):
        title = m.group(1).strip()
        price = parse_price(m.group(2))
        list_price = parse_price(m.group(3))
        disc = int(m.group(4))
        if title and price:
            products.append({
                "source": "daraz", "title": title, "price": price,
                "list_price": list_price, "discount_percent": disc,
                "stock_flag": "in_stock", "category_path": "",
                "category_rank": rank, "url": url})
    return products


def scrape_daraz(categories=None):
    if categories is None:
        categories = DARAZ_CATEGORIES
    session = requests.Session()
    session.headers.update(HEADERS)
    all_products = []
    print(f"[DARAZ] Scraping {len(categories)} categories + catalog...")

    # Catalog page has SSR flash sale products
    catalog = f"{DARAZ_BASE}/catalog/"
    print(f"  {catalog}")
    prods = scrape_daraz_page(catalog, session)
    all_products.extend(prods)
    print(f"    -> {len(prods)} products")
    time.sleep(CRAWL_DELAY)

    for cat in categories:
        url = urljoin(DARAZ_BASE, cat)
        print(f"  {url}")
        prods = scrape_daraz_page(url, session)
        all_products.extend(prods)
        print(f"    -> {len(prods)} products")
        time.sleep(CRAWL_DELAY)

    df = pd.DataFrame(all_products)
    if not df.empty:
        out = os.path.join(OUTPUT_DIR, "daraz_products.csv")
        df.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"[DARAZ] Saved {len(df)} -> {out}")
    return df


if __name__ == "__main__":
    df = scrape_daraz()
    print(f"\nTotal: {len(df)}")
    if not df.empty:
        print(df.head(5).to_string())

