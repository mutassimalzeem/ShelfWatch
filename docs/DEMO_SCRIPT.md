# ShelfWatch — 90-second demo

Use the live dashboard at
[shelfwatch-weld.vercel.app](https://shelfwatch-weld.vercel.app). Production
counts can change after each scheduled collection, so describe the numbers
shown on screen rather than memorizing old totals.

## Before recording

- Open the production dashboard and wait for listings to load.
- Check that the retailer selector and product search work.
- Choose a product that has a history link.

## 0:00–0:20 — What it does

**Show:** The dashboard overview.

**Say:** “ShelfWatch collects public grocery listings from Bangladesh and
keeps dated records of prices and availability. This dashboard makes the
latest collected data easier to explore.”

## 0:20–0:45 — Explore listings

**Show:** Current product count, retailer summary, search box, and retailer
filter.

**Do:** Search for a familiar product and select a retailer.

**Say:** “I can search the latest listings and narrow them by retailer.
Prices and stock are what the site showed at collection time; they are not a
promise of live store inventory.”

## 0:45–1:05 — Look at history

**Do:** Open a product's price-history details.

**Say:** “Each collection adds a dated observation. History helps us notice
changes, but unusual values still need checking against the original listing.”

## 1:05–1:25 — Explain the model honestly

**Say:** “The stock-out model is experimental. Its current scores come from
synthetic test data only, not real grocery predictions. We need more verified
stock-out examples before a real performance score is meaningful.”

## 1:25–1:30 — Close

**Say:** “ShelfWatch turns public listings into a growing record for
exploration. The focus now is better data and trustworthy comparisons.”

## If something fails

- Refresh once and check the API at `/api/health`.
- Check GitHub **Actions → Scrape and ingest grocery listings** for collection
  status.
- Use [the runbook](runbook.md) for troubleshooting. Do not show secrets or
  connection strings on screen.
