# ShelfWatch runbook

Use this guide to check the live service and its collection workflow. Never
paste database connection strings or other credentials into logs, issues, or
screenshots.

## Check the live service

Open the [ShelfWatch dashboard](https://shelfwatch-weld.vercel.app) and check:

1. The overview numbers load.
2. Product search and retailer filters return listings.
3. A product's history opens.
4. The API responds at `/api/health` and `/api/overview`.

The deployed dashboard is served by Vercel and reads production data from
Neon. The API is read-only. A response with HTTP 200 means the endpoint
responded; check its data before concluding that a scrape was complete.

## Check a scheduled collection

1. In GitHub, open **Actions → Scrape and ingest grocery listings**.
2. Open the latest run and check each step, especially **Collect product
   listings**, **Verify the collection produced data**, and **Ingest the
   snapshot into Neon**.
3. If the workflow failed because `DATABASE_URL` is missing, check that the
   GitHub Actions secret exists. Do not print or copy its value.
4. If browser setup or scraping fails, check the error output and the retailer
   site before retrying. Shwapno uses Playwright/Chromium and collection can
   take several minutes.
5. After a successful run, verify `/api/health` and `/api/overview` on the
   live site.

The scheduled job runs every six hours. It stops before ingestion if the
scraper did not produce a combined snapshot. Re-running ingestion for the
same CSV content is safe because the database uses a content hash to avoid
duplicate ingestion.

## Local development checks

Run from the repository root:

```powershell
python -m unittest discover -s tests -v
python scraper\main.py
python src\storage\db.py
uvicorn src.api.main:app --reload
```

For Shwapno in a local environment, install its browser once:

```powershell
python -m playwright install chromium
```

If the dashboard/API fails locally, inspect the terminal output and confirm
that the expected database is selected. Without `DATABASE_URL`, local runs
use `shelfwatch.db`.

## Common problems

### Scraper returns no data

- Check whether the retailer site is reachable.
- Check for site markup, bot-check, or browser errors in the workflow logs.
- Confirm `scraper/output/all_products_combined.csv` was generated locally.
- Do not ingest an empty or obviously invalid snapshot.
- Othoba currently returns no usable products because its product grid is
  client-rendered; Daraz is opt-in and its category pages are bot-check
  blocked.

### Prices look implausible

- Compare the product's listing and historical rows with the retailer page.
- Keep the observed raw record for investigation; do not silently rewrite
  historical data.
- Record the URL, scrape time, and corrected parser behavior if a defect is
  confirmed.
- A known unverified outlier is documented in
  [the case study](CASE_STUDY.md#3-state-as-of-2026-10-08).

### A deployment does not update after a merge

- Confirm the Vercel project is connected to this GitHub repository.
- Check that the commit reached `main`.
- Check Vercel **Deployments** for build errors.
- Confirm Vercel's production `DATABASE_URL` is set without exposing it.
- Verify the deployed `/api/health` and `/api/overview` endpoints.

The Vercel function entry point is `api/index.py`; `vercel.json` routes the
dashboard, API, and static files to FastAPI. Do not move the entry point back
to the repository root.

### GitHub cannot list the repository in Vercel

Open the GitHub App installation settings and grant the Vercel app access to
the ShelfWatch repository, then retry the connection in the Vercel project
settings.

### Google Drive blocks a package install or Git operation

The project folder is on a synced drive. If a tool reports file locks or
archive extraction errors, run that tool from a normal local folder when
possible. Do not remove or overwrite files to force the operation; check
`git status` first and preserve unrelated local changes.
