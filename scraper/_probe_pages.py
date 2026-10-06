"""Throwaway probe: raw per-page yields + HTTP status for pagination debugging."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import requests
from config import HEADERS, OTHOBA_BASE, DARAZ_BASE
from scraper_othoba import scrape_othoba_page
from scraper_daraz import scrape_daraz_page

s = requests.Session()
s.headers.update(HEADERS)

print("--- OTHOBA ---")
for label, url in [
    ("page1", OTHOBA_BASE + "/grocery"),
    ("page=2", OTHOBA_BASE + "/grocery?page=2"),
    ("pagenumber=2", OTHOBA_BASE + "/grocery?pagenumber=2"),
]:
    try:
        r = s.get(url, timeout=30)
        status, size = r.status_code, len(r.text)
    except requests.RequestException as e:
        print(f"{label}: REQUEST ERROR {e}")
        continue
    prods = scrape_othoba_page(url, s)
    first = prods[0]["title"][:40] if prods else "-"
    print(f"{label}: http={status} bytes={size} raw_products={len(prods)} first={first!r}")

print("--- DARAZ ---")
for label, url in [
    ("catalog p1", DARAZ_BASE + "/catalog/"),
    ("catalog p2", DARAZ_BASE + "/catalog/?page=2"),
    ("fruits p1", DARAZ_BASE + "/fruits-meat-frozen/"),
]:
    try:
        r = s.get(url, timeout=30)
        low = r.text.lower()
        flag = "botcheck" if ("captcha" in low or "punish" in low or "verify" in low) else "ok"
        status, size = r.status_code, len(r.text)
    except requests.RequestException as e:
        print(f"{label}: REQUEST ERROR {e}")
        continue
    prods = scrape_daraz_page(url, s)
    first = prods[0]["title"][:40] if prods else "-"
    print(f"{label}: http={status} bytes={size} flag={flag} raw_products={len(prods)} first={first!r}")
print("PROBE_DONE")
