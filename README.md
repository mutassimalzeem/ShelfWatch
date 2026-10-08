# ShelfWatch

**Price and shelf-availability intelligence for Bangladesh grocery retail.**

ShelfWatch collects publicly visible product listings from selected Bangladeshi
retail websites, keeps timestamped snapshots, and provides a live dashboard
for exploring listings and their history. Data collection and the dashboard
are running in production. Product matching and predictive alerts are still
experimental or planned.

![Project status: live data dashboard](https://img.shields.io/badge/status-live%20dashboard-brightgreen)
![Market: Bangladesh](https://img.shields.io/badge/market-Bangladesh-006a4e)
![Python: 3.12](https://img.shields.io/badge/Python-3.12-blue)

## At a glance

| Area | Current state |
|---|---|
| Product collection | Scrapers are present for Chaldal, Shwapno, Daraz BD, and Othoba |
| Default enabled sources | Chaldal, Shwapno, and Othoba; Daraz is opt-in |
| Production data checked | 1,901 observations and 597 current listings across Chaldal and Shwapno (Oct 8, 2026) |
| Snapshot history | Timestamped CSV snapshots; configured to retain up to 60 |
| Storage | Local SQLite or hosted PostgreSQL; content-hash ingestion deduplication |
| Analysis | A basic data-audit script and a standalone pack-size parser are present |
| Modeling | An offline stock-out baseline; no measured real-data score yet |
| Automated tests | 26 unit, API, and storage tests |
| API layer | FastAPI dashboard and read-only listing/history/alert endpoints |
| Production deployment | Live on Vercel, backed by Neon; GitHub Actions collects data every six hours |

Production counts are a point-in-time snapshot and change after collection
runs. Your local SQLite database may contain different data.

## Demo

Watch the [ShelfWatch demo video](demo.mp4).

<video src="demo.mp4" controls width="100%">
  Your browser does not support embedded video. [Watch the demo](demo.mp4).
</video>

## Live dashboard

Open [shelfwatch-weld.vercel.app](https://shelfwatch-weld.vercel.app) to browse
current listings, filter by retailer or availability, and inspect price
history. Prices and availability are observations from retailer websites, not
a guarantee of live store inventory.

The production API and database were checked after the first hosted
collection:

| Check | Result |
|---|---:|
| API health | OK |
| Stored observations | 1,901 |
| Current listings | 597 |
| Retailers with data | 2 |
| Current out-of-stock listings | 0 |
| First hosted scraper run | Success; added 651 observations |

## Model scores, explained

The baseline stock-out model has only been tested on **synthetic data** (data
created for a test). This checks that training and scoring run; it does not
show how well the model predicts real stock-outs.

| Synthetic time-ordered fold | PR-AUC | F2 |
|---|---:|---:|
| 1 | 0.774 | 0.806 |
| 2 | 0.796 | 0.790 |
| 3 | 0.816 | 0.801 |
| **Average** | **0.795** | **0.799** |

- **PR-AUC** measures how well the model ranks likely stock-outs above other
  listings. Higher is better.
- **F2** combines precision and recall, giving more weight to finding
  stock-outs. Higher is better.
- The real production data had **0 out-of-stock labels in 1,901 observations**
  at the time of this check. There is not enough labeled data to calculate a
  real model score or train a useful predictor. See the
  [model card](docs/model_card.md) for details.

## What ShelfWatch does

ShelfWatch collects publicly visible grocery listings, saves timestamped price
and availability observations, and shows them in a dashboard. The hosted
collection runs every six hours. Matching the same product across retailers
and reliable forecasting are future goals, not current features.

## Data sources and collection methods

| Source | Collection approach | Current status |
|---|---|---|
| [Chaldal](https://chaldal.com) | HTTP requests and BeautifulSoup; prefers embedded product data and falls back to page parsing | Enabled by default |
| [Shwapno](https://www.shwapno.com) | Playwright for client-rendered listings, with an HTTP fallback | Enabled by default |
| [Daraz Bangladesh](https://www.daraz.com.bd) | HTTP and page-data parsing | Disabled by default because category listings are bot-check blocked and reachable catalog data can include irrelevant products; can be forced for an individual run |
| [Othoba](https://www.othoba.com) | HTTP requests and BeautifulSoup | Enabled by default, but currently returns no usable products because its grid is client-rendered |

The configured category paths are maintained in [`scraper/config.py`](scraper/config.py).
Scraper-specific notes and limitations are in [`scraper/README.md`](scraper/README.md).

## Getting started

### Requirements

- Python 3.12 is the version used for the current local development snapshot.
- Internet access to the target sites is needed to scrape live data.
- Playwright's Chromium browser is optional but recommended for fuller Shwapno
  results.

### Install dependencies

Run these commands from the repository root.

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r scraper\requirements.txt
```

The small root requirements file is for the API and hosted deployment. To
install the full modelling and development environment as well:

```powershell
python -m pip install -r requirements-project.txt
```

To enable the Playwright browser used by Shwapno:

```powershell
python -m playwright install chromium
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r scraper/requirements.txt
python -m playwright install chromium  # optional, for Shwapno
```

Install `requirements-project.txt` as well when using the modelling or full
development toolchain.

## Run it locally

After installing the dependencies above, run the default collection:

```bash
python scraper/main.py
```

To start the dashboard and API:

```bash
uvicorn src.api.main:app --reload
```

Open `http://127.0.0.1:8000`. The dashboard reads saved data; it does not
scrape retailers when a page is opened. The technical guide covers storage,
individual scraper commands, and the optional local scheduler.

## What is ready—and what is not

- **Ready:** retailer collection, timestamped history, SQLite/PostgreSQL
  storage, a live dashboard, and read-only API endpoints.
- **Experimental:** the offline stock-out model and possible pack-size alerts.
- **Not ready:** reliable cross-retailer product matching or real-world stock
  forecasts. Retailer availability can be stale, and some sites change their
  pages or block automated requests.

## Tests

Run the smoke tests from the repository root:

```bash
python -m unittest discover -s tests -v
```

Install `requirements-project.txt` for the full test and modelling
dependencies.

`python src/models/train_baseline.py --selftest` exercises the modelling
pipeline end-to-end on a deterministic synthetic fixture (no retailer
contact, no database needed). When the stored snapshots contain too few
stock-out events the trainer exits gracefully with guidance instead of
raising a single-class error.

Tests do not need to contact retailer websites.

## API

A FastAPI application serves the dashboard and read-only API. It uses SQLite
locally or PostgreSQL when `DATABASE_URL` is set. The main endpoints are:

`/api/health`, `/api/overview`, `/api/products`, and product history. See
`/docs` in the running app for the full interactive API reference.

## Production setup

ShelfWatch is already deployed. The Vercel project is connected to this
repository's `main` branch. Vercel serves the dashboard and API from
`api/index.py`; Neon stores production observations. GitHub Actions scrapes
and ingests data every six hours. The first hosted run succeeded and the
current production check is summarized above.

To create your own deployment:

1. Create a Neon PostgreSQL database and copy its pooled PostgreSQL connection
   string (including `sslmode=require`).
2. Add that value as the `DATABASE_URL` GitHub Actions secret in
   **Settings → Secrets and variables → Actions**. Add the same environment
   variable to the Vercel project for Production (and Preview if desired).
   Never commit or paste the connection string into source control.
3. With the full project dependencies installed, copy local history into a
   **new, empty** Neon database from PowerShell:

   ```powershell
   $env:DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DB?sslmode=require"
   python -m src.storage.migrate_to_postgres
   Remove-Item Env:DATABASE_URL
   ```

   The migration refuses to run if the destination already contains snapshot
   rows. Do not run this migration against the live production database.
4. Link the GitHub repository to a Vercel project. The Vercel Python function
   is `api/index.py`; `vercel.json` routes dashboard, API, and asset requests
   through FastAPI. Add `DATABASE_URL` as a Vercel Production (and Preview,
   if needed) secret before deploying.
5. Merge the deployment branch into the repository's default branch. Run
   **Actions → Scrape and ingest grocery listings → Run workflow** to verify
   collection and ingestion.

The scheduled workflow requires the `DATABASE_URL` Actions secret and stops
if collection produces no snapshot. Scraping runs in GitHub Actions, not
inside Vercel functions.

## Project documentation

Project guides:

- [`docs/PROJECT_DOCUMENTATION.md`](docs/PROJECT_DOCUMENTATION.md) — technical
  reference for architecture, data, commands, deployment, and limitations.
- [`docs/CASE_STUDY.md`](docs/CASE_STUDY.md) — dated narrative of the problems
  faced during development and how they were resolved.
- [`docs/model_card.md`](docs/model_card.md) — what the model can and cannot
  currently tell us.
- [`docs/runbook.md`](docs/runbook.md) — practical steps for checking common
  collection and deployment problems.
- [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) — short walkthrough of the live
  dashboard.
- [`docs/GIT_WORKFLOW.md`](docs/GIT_WORKFLOW.md) — branch and release basics.

## Responsible collection

ShelfWatch is intended to collect public product-listing information only.
Respect each site's current terms, robots directives, rate limits, and
applicable law before running or extending a scraper. The project configures a
three-second delay between requests; do not remove or reduce it without
reviewing the impact. Foodpanda is excluded from the configured sources.

The technical guide has the full architecture, data-field definitions,
commands, roadmap, and limitations.

## Contributing

Changes to scrapers should preserve the common output fields, polite request
behavior, and UTF-8 handling. Run the tests and inspect the resulting diff
before submitting changes. The repository's branch and commit conventions are
documented in [`docs/GIT_WORKFLOW.md`](docs/GIT_WORKFLOW.md).

## License

No license is currently declared in this repository. Contact the project
maintainer before redistributing or reusing the code.
