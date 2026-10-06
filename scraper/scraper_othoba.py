"""
Othoba Scraper - Server-Side Rendered (nopCommerce)
Best alternative: full SSR with prices visible in HTML.
"""
import re, os, time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
from config import (OTHOBA_BASE, OTHOBA_CATEGORIES, HEADERS,
                    REQUEST_TIMEOUT, CRAWL_DELAY, OUTPUT_DIR)


def parse_price(price_text):
    if not price_text:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(price_text).replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


def scrape_othoba_page(url, session):
    products = []
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [ERROR] {url}: {e}")
        return products

    soup = BeautifulSoup(resp.text, "lxml")
    bc = soup.select(".breadcrumb a, [class*='breadcrumb'] a")
    cat_path = " > ".join(el.get_text(strip=True) for el in bc if el.get_text(strip=True))
    if not cat_path:
        t = soup.find("title")
        cat_path = t.get_text(strip=True).split("|")[0].strip() if t else url

    # nopCommerce product cards
    selectors = [".product-item", ".item-box", "[class*='product-item']",
                 ".product-box", ".products-grid .item"]
    cards = []
    for sel in selectors:
        cards = soup.select(sel)
        if cards:
            break

    if cards:
        for rank, card in enumerate(cards, start=1):
            t_el = card.select_one("h2 a, h3 a, .product-title a, [class*='title'] a")
            title = t_el.get_text(strip=True) if t_el else None
            if not title:
                t_el = card.select_one("h2, h3, [class*='title']")
                title = t_el.get_text(strip=True) if t_el else None
            if not title or len(title) < 3:
                continue
            # Prices
            p_els = card.select("[class*='price']")
            prices = [parse_price(el.get_text(strip=True)) for el in p_els]
            prices = [p for p in prices if p is not None]
            price = min(prices) if prices else None
            list_price = max(prices) if len(prices) > 1 else None
            disc = round((1 - price / list_price) * 100) if list_price and price and list_price > price else None
            stock = "out_of_stock" if "out of stock" in card.get_text().lower() else "in_stock"
            link = card.select_one("a[href]")
            purl = urljoin(OTHOBA_BASE, link["href"]) if link else url
            products.append({
                "source": "othoba", "title": title, "price": price,
                "list_price": list_price, "discount_percent": disc,
                "stock_flag": stock, "category_path": cat_path,
                "category_rank": rank, "url": purl})
    else:
        # Fallback text parsing
        products = _parse_text(soup, cat_path, url)
    return products


def _parse_text(soup, cat_path, url):
    """Fallback text parsing: ProductName Tk price Tk original"""
    products = []
    text = soup.get_text()
    pat = r"(.{10,150}?)\s*\(\d+\s*Reviews?\)\s*Tk\s*([\d,]+)(?:\s*Tk\s*([\d,]+))?"
    for rank, m in enumerate(re.finditer(pat, text), 1):
        title = m.group(1).strip()
        price = parse_price(m.group(2))
        list_price = parse_price(m.group(3)) if m.group(3) else None
        if title and price:
            disc = round((1 - price / list_price) * 100) if list_price and list_price > price else None
            products.append({
                "source": "othoba", "title": title, "price": price,
                "list_price": list_price, "discount_percent": disc,
                "stock_flag": "in_stock", "category_path": cat_path,
                "category_rank": rank, "url": url})
    if not products:
        pat2 = r"(.{10,150}?)\s*Tk\s*([\d,]+)\s*Tk\s*([\d,]+)"
        for rank, m in enumerate(re.finditer(pat2, text), 1):
            title = m.group(1).strip()
            price = parse_price(m.group(2))
            list_price = parse_price(m.group(3))
            if title and price:
                disc = round((1 - price / list_price) * 100) if list_price > price else None
                products.append({
                    "source": "othoba", "title": title, "price": price,
                    "list_price": list_price, "discount_percent": disc,
                    "stock_flag": "in_stock", "category_path": cat_path,
                    "category_rank": rank, "url": url})
    return products


def scrape_othoba(categories=None):
    if categories is None:
        categories = OTHOBA_CATEGORIES
    session = requests.Session()
    session.headers.update(HEADERS)
    all_products = []
    print(f"[OTHOBA] Scraping {len(categories)} categories...")
    for cat in categories:
        url = urljoin(OTHOBA_BASE, cat)
        print(f"  {url}")
        prods = scrape_othoba_page(url, session)
        all_products.extend(prods)
        print(f"    -> {len(prods)} products")
        time.sleep(CRAWL_DELAY)
    df = pd.DataFrame(all_products)
    if not df.empty:
        out = os.path.join(OUTPUT_DIR, "othoba_products.csv")
        df.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"[OTHOBA] Saved {len(df)} -> {out}")
    return df


if __name__ == "__main__":
    df = scrape_othoba()
    print(f"\nTotal: {len(df)}")
    if not df.empty:
        print(df.head(5).to_string())

