"""
Shwapno Scraper - Client-Side Rendered (SPA)
Requires Playwright for full product data.
Fallback: HTTP with limited extraction.
"""
import re, os, time, json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
from config import (SHWAPNO_BASE, SHWAPNO_CATEGORIES, HEADERS,
                    REQUEST_TIMEOUT, CRAWL_DELAY, OUTPUT_DIR)


def parse_price(price_text):
    if not price_text:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(price_text).replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


def scrape_shwapno(categories=None):
    if categories is None:
        categories = SHWAPNO_CATEGORIES
    try:
        from playwright.sync_api import sync_playwright
        return _scrape_playwright(categories)
    except ImportError:
        print("[SHWAPNO] Playwright not found. Using HTTP fallback.")
        print("  Install with: pip install playwright && playwright install chromium")
        return _scrape_http(categories)
    except Exception as e:
        err_msg = str(e)
        if "Executable doesn't exist" in err_msg or "browserType.launch" in err_msg:
            print(f"[SHWAPNO] Playwright browsers not installed. Using HTTP fallback.")
            print("  Fix with: playwright install chromium")
        else:
            print(f"[SHWAPNO] Playwright error: {e}. Using HTTP fallback.")
        return _scrape_http(categories)


def _scrape_playwright(categories):
    from playwright.sync_api import sync_playwright
    all_products = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"])
        for cat in categories:
            url = urljoin(SHWAPNO_BASE, cat)
            print(f"  [PW] {url}")
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(3000)
                bc = page.query_selector_all("nav a, .breadcrumb a")
                cat_path = " > ".join(el.inner_text() for el in bc if el.inner_text().strip())
                # Find product cards
                cards = page.query_selector_all("[class*='product'], [class*='card']")
                for rank, card in enumerate(cards, start=1):
                    try:
                        t_el = card.query_selector("[class*='name'], [class*='title'], h3, h4, a")
                        title = t_el.inner_text().strip() if t_el else None
                        p_el = card.query_selector("[class*='price']")
                        price = parse_price(p_el.inner_text()) if p_el else None
                        o_el = card.query_selector("del, s, [class*='old'], [class*='original']")
                        list_price = parse_price(o_el.inner_text()) if o_el else None
                        txt = card.inner_text().lower()
                        stock = "out_of_stock" if "out of stock" in txt or "sold" in txt else "in_stock"
                        disc = None
                        if list_price and price and list_price > price:
                            disc = round((1 - price / list_price) * 100)
                        if title and price:
                            all_products.append({
                                "source": "shwapno", "title": title, "price": price,
                                "list_price": list_price, "discount_percent": disc,
                                "stock_flag": stock, "category_path": cat_path,
                                "category_rank": rank, "url": url})
                    except Exception:
                        continue
                print(f"    -> {len(cards)} cards found")
            except Exception as e:
                print(f"    [ERROR] {e}")
            page.wait_for_timeout(int(CRAWL_DELAY * 1000))
        browser.close()
    df = pd.DataFrame(all_products)
    if not df.empty:
        out = os.path.join(OUTPUT_DIR, "shwapno_products.csv")
        df.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"[SHWAPNO] Saved {len(df)} -> {out}")
    return df


def _scrape_http(categories):
    """HTTP fallback - limited data since Shwapno is CSR."""
    session = requests.Session()
    session.headers.update(HEADERS)
    all_products = []
    for cat in categories:
        url = urljoin(SHWAPNO_BASE, cat)
        print(f"  [HTTP] {url}")
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"    [ERROR] {e}")
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        bc = soup.select("nav a, .breadcrumb a")
        cat_path = " > ".join(el.get_text(strip=True) for el in bc if el.get_text(strip=True))
        # Look for embedded JSON with product data
        for script in soup.find_all("script"):
            text = script.string or ""
            if "product" in text.lower() and "price" in text.lower():
                matches = re.findall(r'\{[^{}]*"(?:name|title|productName)"[^{}]*\}', text)
                for jm in matches[:100]:
                    try:
                        d = json.loads(jm)
                        name = d.get("name") or d.get("title") or d.get("productName")
                        price = d.get("price") or d.get("sellingPrice")
                        if name and price:
                            all_products.append({
                                "source": "shwapno", "title": str(name),
                                "price": float(price) if price else None,
                                "list_price": None, "discount_percent": None,
                                "stock_flag": "unknown",
                                "category_path": cat_path or cat,
                                "category_rank": len(all_products) + 1,
                                "url": url})
                    except (json.JSONDecodeError, ValueError):
                        continue
        time.sleep(CRAWL_DELAY)
    df = pd.DataFrame(all_products)
    if not df.empty:
        out = os.path.join(OUTPUT_DIR, "shwapno_products.csv")
        df.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"[SHWAPNO] Saved {len(df)} -> {out}")
    else:
        print("[SHWAPNO] No products via HTTP. Install playwright for full data:")
        print("  pip install playwright && playwright install chromium")
    return df


if __name__ == "__main__":
    df = scrape_shwapno()
    print(f"\nTotal: {len(df)}")
    if not df.empty:
        print(df.head(5).to_string())
