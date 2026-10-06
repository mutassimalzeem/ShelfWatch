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
                    REQUEST_TIMEOUT, CRAWL_DELAY, OUTPUT_DIR, MAX_PAGES)


def parse_price(price_text):
    if not price_text:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(price_text).replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


NAV_JUNK = ("EMI Policy", "Call us at", "Hot Deals", "More Products", "Buy Now",
            "Sign In", "Subscribe To", "Full Store Directory")


def _clean_title(raw):
    """Strip navigation/footer fragments that glue onto fallback titles."""
    if not raw:
        return None
    t = re.sub(r"\s+", " ", raw).strip()
    changed = True
    while changed:
        changed = False
        cut_end = -1
        for marker in NAV_JUNK:
            idx = t.find(marker)
            if idx != -1 and idx + len(marker) > cut_end:
                cut_end = idx + len(marker)
        if cut_end != -1:
            t = t[cut_end:].strip()
            changed = True
    t = re.sub(r"\(\d+\s*reviews?\)\s*$", "", t, flags=re.I).strip()
    t = re.sub(r"\|\s*Free delivery$", "", t, flags=re.I).strip()
    if not t or len(t) < 3 or len(t) > 150:
        return None
    return t


def _fetch_soup(url, session):
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [ERROR] {url}: {e}")
        return None
    return BeautifulSoup(resp.text, "lxml")


def scrape_othoba_page(url, session):
    soup = _fetch_soup(url, session)
    if soup is None:
        return []
    return _products_from_soup(soup, url)


def _products_from_soup(soup, url):
    products = []
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
            raw = t_el.get_text(strip=True) if t_el else None
            if not raw:
                t_el = card.select_one("h2, h3, [class*='title']")
                raw = t_el.get_text(strip=True) if t_el else None
            title = _clean_title(raw)
            if not title:
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
        title = _clean_title(m.group(1))
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
            title = _clean_title(m.group(1))
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


def _pager_urls(soup, base_url):
    """nopCommerce renders real pager hrefs; follow those, not guessed params."""
    urls = []
    for a in soup.select(".pager a, [class*='pager'] a, [class*='pagination'] a"):
        href = a.get("href") or ""
        if "page=" in href or "pagenumber=" in href:
            full = urljoin(base_url, href)
            if full not in urls:
                urls.append(full)
    return urls


def scrape_othoba_paginated(base_url, session, max_pages=MAX_PAGES):
    """Follow discovered pager hrefs until a page adds no new products."""
    products = []
    seen = set()
    queue = [base_url]
    visited = set()
    for page in range(1, max_pages + 1):
        url = None
        while queue:
            cand = queue.pop(0)
            if cand not in visited:
                visited.add(cand)
                url = cand
                break
        if url is None:
            break
        soup = _fetch_soup(url, session)
        if soup is None:
            break
        prods = _products_from_soup(soup, url)
        new = []
        for p in prods:
            key = (p.get("title"), p.get("price"))
            if key not in seen:
                seen.add(key)
                new.append(p)
        if not new:
            break
        products.extend(new)
        print(f"    -> page {page}: {len(new)} new products (total {len(products)})")
        queue.extend(u for u in _pager_urls(soup, base_url) if u not in visited)
        time.sleep(CRAWL_DELAY)
    return products


def scrape_othoba(categories=None, max_pages=MAX_PAGES):
    if categories is None:
        categories = OTHOBA_CATEGORIES
    session = requests.Session()
    session.headers.update(HEADERS)
    all_products = []
    print(f"[OTHOBA] Scraping {len(categories)} categories...")
    for cat in categories:
        url = urljoin(OTHOBA_BASE, cat)
        print(f"  {url}")
        prods = scrape_othoba_paginated(url, session, max_pages=max_pages)
        for rank, p in enumerate(prods, 1):
            p["category_rank"] = rank
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

