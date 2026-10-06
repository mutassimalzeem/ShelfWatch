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
                    REQUEST_TIMEOUT, CRAWL_DELAY, OUTPUT_DIR, MAX_PAGES)


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


def _paginated_url(base_url, page):
    """Lazada/Daraz listing pages accept ?page=N."""
    if page <= 1:
        return base_url
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}page={page}"


def scrape_daraz_paginated(base_url, session, max_pages=MAX_PAGES):
    """Follow ?page=N until a page returns no new products."""
    products = []
    seen = set()
    for page in range(1, max_pages + 1):
        url = _paginated_url(base_url, page)
        prods = scrape_daraz_page(url, session)
        if not prods:
            break
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
        time.sleep(CRAWL_DELAY)
    return products


def _daraz_targets(categories):
    # Catalog page has SSR flash sale products; categories need JS rendering
    return [f"{DARAZ_BASE}/catalog/"] + [urljoin(DARAZ_BASE, c) for c in categories]


def _save_daraz(df):
    if not df.empty:
        out = os.path.join(OUTPUT_DIR, "daraz_products.csv")
        df.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"[DARAZ] Saved {len(df)} -> {out}")
    return df


def _extract_pw_products(page, url):
    """Prefer Lazada's embedded pageData JSON; fall back to rendered DOM cards."""
    products = []
    data = None
    try:
        data = page.evaluate(
            "() => (window.pageData && window.pageData.mods && window.pageData.mods.listItems)"
            " ? window.pageData.mods.listItems : null")
    except Exception:
        data = None
    for it in data or []:
        if not isinstance(it, dict):
            continue
        products.append({
            "source": "daraz",
            "title": it.get("name", ""),
            "price": parse_price(str(it.get("price", ""))),
            "list_price": parse_price(str(it.get("originalPrice", ""))),
            "discount_percent": it.get("discount"),
            "stock_flag": "in_stock",
            "category_path": "",
            "category_rank": 0,
            "url": urljoin(DARAZ_BASE, it.get("itemUrl", "")) or url})
    if products:
        return products
    cards = page.query_selector_all(
        "[data-qa-qa-name='listItem'], [class*='listItem'], .Bm3ON")
    for card in cards:
        try:
            t_el = card.query_selector("[class*='title'], a[title]")
            title = None
            if t_el:
                title = t_el.inner_text().strip() or t_el.get_attribute("title")
            p_el = card.query_selector("[class*='price']")
            price = parse_price(p_el.inner_text()) if p_el else None
            o_el = card.query_selector("[class*='originPrice'], del, s")
            list_price = parse_price(o_el.inner_text()) if o_el else None
            disc = None
            if list_price and price and list_price > price:
                disc = round((1 - price / list_price) * 100)
            if title and price:
                products.append({
                    "source": "daraz", "title": title, "price": price,
                    "list_price": list_price, "discount_percent": disc,
                    "stock_flag": "in_stock", "category_path": "",
                    "category_rank": 0, "url": url})
        except Exception:
            continue
    return products


def _scrape_playwright(categories, max_pages):
    from playwright.sync_api import sync_playwright
    all_products = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"])
        for base in _daraz_targets(categories):
            print(f"  [PW] {base}")
            seen = set()
            cat_products = []
            for pg in range(1, max_pages + 1):
                url = _paginated_url(base, pg)
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(4000)
                    prods = _extract_pw_products(page, url)
                except Exception as e:
                    print(f"    [ERROR] page {pg}: {e}")
                    break
                new = []
                for pr in prods:
                    key = (pr.get("title"), pr.get("price"))
                    if key not in seen:
                        seen.add(key)
                        new.append(pr)
                if not new:
                    break
                cat_products.extend(new)
                print(f"    -> page {pg}: {len(new)} new products (total {len(cat_products)})")
                page.wait_for_timeout(int(CRAWL_DELAY * 1000))
            for rank, pr in enumerate(cat_products, 1):
                pr["category_rank"] = rank
            all_products.extend(cat_products)
            print(f"    -> {len(cat_products)} products")
        browser.close()
    return _save_daraz(pd.DataFrame(all_products))


def _scrape_http(categories, max_pages):
    session = requests.Session()
    session.headers.update(HEADERS)
    all_products = []
    print(f"[DARAZ] Scraping {len(_daraz_targets(categories))} targets via HTTP...")
    for url in _daraz_targets(categories):
        print(f"  {url}")
        prods = scrape_daraz_paginated(url, session, max_pages=max_pages)
        for rank, p in enumerate(prods, 1):
            p["category_rank"] = rank
        all_products.extend(prods)
        print(f"    -> {len(prods)} products")
        time.sleep(CRAWL_DELAY)
    return _save_daraz(pd.DataFrame(all_products))


def scrape_daraz(categories=None, max_pages=MAX_PAGES):
    if categories is None:
        categories = DARAZ_CATEGORIES
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return _scrape_playwright(categories, max_pages)
    except ImportError:
        print("[DARAZ] Playwright not found. Using HTTP fallback.")
        return _scrape_http(categories, max_pages)
    except Exception as e:
        print(f"[DARAZ] Playwright error: {e}. Using HTTP fallback.")
        return _scrape_http(categories, max_pages)


if __name__ == "__main__":
    df = scrape_daraz()
    print(f"\nTotal: {len(df)}")
    if not df.empty:
        print(df.head(5).to_string())

