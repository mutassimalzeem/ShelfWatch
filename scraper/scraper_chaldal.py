"""
Chaldal Scraper - Server-Side Rendered
Products are fully rendered in HTML. Uses requests + BeautifulSoup.
"""
import re, os, time, json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
from config import (CHALDAL_BASE, CHALDAL_CATEGORIES, HEADERS,
                    REQUEST_TIMEOUT, CRAWL_DELAY, OUTPUT_DIR, MAX_RETRIES)


def parse_price(price_text: str):
    if not price_text:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(price_text).replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


def scrape_category_page(url, session, max_retries=MAX_RETRIES):
    products = []
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            break
        except requests.RequestException as e:
            if attempt == max_retries:
                print(f"  [ERROR] {url}: {e} (after {max_retries} attempts)")
                return products
            wait = 2 ** attempt
            print(f"  [RETRY {attempt}/{max_retries}] {url}: {e}. Waiting {wait}s...")
            time.sleep(wait)

    soup = BeautifulSoup(resp.text, "lxml")
    # Breadcrumb
    bc = soup.select("nav a, .breadcrumb a, [class*='breadcrumb'] a")
    category_path = " > ".join(el.get_text(strip=True) for el in bc if el.get_text(strip=True))
    if not category_path:
        t = soup.find("title")
        category_path = t.get_text(strip=True).split("|")[0].strip() if t else url

    # Try JSON in script tags first
    products = _extract_json(soup, category_path, url)
    if products:
        return products

    # Fallback: parse visible text
    products = _parse_text(soup, category_path, url)
    return products


def _extract_json(soup, category_path, url):
    products = []
    for script in soup.find_all("script"):
        text = script.string or ""
        if not text or "product" not in text.lower():
            continue
        # Try window.__X = {...}
        m = re.search(r"window\.__\w+\s*=\s*(\{.+?\});\s*$", text, re.DOTALL | re.MULTILINE)
        if m:
            try:
                data = json.loads(m.group(1))
                products.extend(_recurse_json(data, category_path))
            except json.JSONDecodeError:
                pass
        # Try application/json
        if script.get("type") == "application/json":
            try:
                data = json.loads(text)
                products.extend(_recurse_json(data, category_path))
            except json.JSONDecodeError:
                pass
    return products


def _recurse_json(data, category_path):
    products = []
    def recurse(obj):
        if isinstance(obj, dict):
            if any(k in obj for k in ("name", "title", "productName")):
                name = obj.get("name") or obj.get("title") or obj.get("productName", "")
                price = obj.get("price") or obj.get("sellingPrice") or obj.get("currentPrice")
                orig = obj.get("originalPrice") or obj.get("regularPrice") or obj.get("listPrice")
                if name and price:
                    products.append({
                        "source": "chaldal", "title": str(name),
                        "price": float(price) if price else None,
                        "list_price": float(orig) if orig else None,
                        "discount_percent": obj.get("discount") or obj.get("discountPercent"),
                        "stock_flag": "in_stock",
                        "category_path": category_path,
                        "category_rank": len(products) + 1, "url": ""})
            else:
                for v in obj.values():
                    recurse(v)
        elif isinstance(obj, list):
            for item in obj:
                recurse(item)
    recurse(data)
    return products


def _parse_text(soup, category_path, url):
    """Parse Chaldal SSR text: ৳ price [৳ orig] Name unit delivery_time"""
    products = []
    text = soup.get_text()
    pattern = (r"৳\s*([\d,]+)(?:\s*৳\s*([\d,]+))?\s*(.{3,80}?)"
               r"\s*(?:\d+\s*(?:kg|gm|ml|ltr|pcs|each|dozen|pack|pc)|±\s*\d+\s*gm)?"
               r"\s*(?:1 hr|Next Day)")
    for rank, m in enumerate(re.finditer(pattern, text), 1):
        price = parse_price(m.group(1))
        list_price = parse_price(m.group(2)) if m.group(2) else None
        title = m.group(3).strip()
        if title and price:
            disc = round((1 - price / list_price) * 100) if list_price and list_price > price else None
            products.append({
                "source": "chaldal", "title": title, "price": price,
                "list_price": list_price, "discount_percent": disc,
                "stock_flag": "in_stock", "category_path": category_path,
                "category_rank": rank, "url": url})
    return products



def scrape_chaldal(categories=None):
    if categories is None:
        categories = CHALDAL_CATEGORIES
    session = requests.Session()
    session.headers.update(HEADERS)
    all_products = []
    print(f"[CHALDAL] Scraping {len(categories)} categories...")
    for cat in categories:
        url = urljoin(CHALDAL_BASE, cat)
        print(f"  {url}")
        prods = scrape_category_page(url, session)
        all_products.extend(prods)
        print(f"    -> {len(prods)} products")
        time.sleep(CRAWL_DELAY)
    df = pd.DataFrame(all_products)
    if not df.empty:
        out = os.path.join(OUTPUT_DIR, "chaldal_products.csv")
        df.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"[CHALDAL] Saved {len(df)} -> {out}")
    return df


if __name__ == "__main__":
    df = scrape_chaldal()
    print(f"\nTotal: {len(df)}")
    if not df.empty:
        print(df.head(5).to_string())

