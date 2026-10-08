# ShelfWatch — Project Documentation

> **Living document.** Last updated 2026-10-08 against `main` @ `4735a5d`.
> Companions: [CASE_STUDY.md](CASE_STUDY.md) (problems & lessons narrative) ·
> [GIT_WORKFLOW.md](GIT_WORKFLOW.md) (branch/commit/push conventions) ·
> root [README.md](../README.md) (overview & roadmap).
> **Update rule:** any commit that changes pipeline behaviour must also update
> the relevant section here and append a line to §9 Changelog; notable
> incidents additionally get a CASE_STUDY entry (template in its Appendix A).

## 1. Purpose and scope

ShelfWatch collects publicly visible product listings (title, price, list
price, discount, stock flag, category path, rank, URL) from Bangladeshi
grocery retailers, stores immutable timestamped snapshots, and derives
features and labels for stock-out modelling and price intelligence.
Cross-retailer product matching and forecasting are roadmap items, not
delivered features.

## 2. Architecture

```text
Chaldal (SSR)   Shwapno (CSR)    Daraz (opt-in)   Othoba (SSR)
     \              |                 |               /
      scraper/main.py — per-source try/except isolation, UTF-8 stdout
        |-- output/<source>_products.csv
        |-- output/all_products_combined.csv     every row UTC `scraped_at`
        |-- output/history/snapshot_<UTC>.csv    ledger, pruned to HISTORY_KEEP
      src/storage/db.py — idempotent SQLite/PostgreSQL ingest
        |-- shelfwatch.db (local) or Neon PostgreSQL (production)
      src/features/label_definitions.sql — stock-out label views
      src/models/ build_features -> train_baseline / train_advanced -> explain_shap
      run_crawler_scheduler.py — 6 h scrape->ingest cycle, lock file, UTF-8 env
      src/api/main.py — Vercel FastAPI dashboard/API; DATABASE_URL selects PostgreSQL
      .github/workflows/scrape-and-ingest.yml — six-hour scraper -> Neon workflow
```

Design principles: (1) snapshots are append-only; time travels via
`scraped_at`. (2) Every ingest/merge is idempotent or explicit. (3) Degrade
gracefully (fallbacks, guards) instead of crashing mid-pipeline. (4) Collected
data stays in a git-ignored local database or a separately configured hosted
database; credentials and datasets do not travel through Git.

## 3. Repository map

| Path | Role |
|---|---|
| `scraper/config.py` | URLs, categories, headers, knobs: `CRAWL_DELAY=3`, `MAX_RETRIES=3`, `MAX_PAGES=5`, `HISTORY_KEEP=60`, `DARAZ_ENABLED=False` |
| `scraper/main.py` | Orchestrates sources; stamps rows; writes combined CSV + history ledger; prunes ledger |
| `scraper/scraper_chaldal.py` | SSR parse: embedded JSON first, text-regex fallback; retry/backoff |
| `scraper/scraper_shwapno.py` | Playwright card extraction with leaf price nodes; HTTP fallback |
| `scraper/scraper_daraz.py` | Catalog strip + Playwright/HTTP pagination; disabled by default |
| `scraper/scraper_othoba.py` | nopCommerce cards; title sanitizer; pager-href discovery |
| `src/storage/db.py` | SQLite/PostgreSQL schema and idempotent snapshot ingestion |
| `src/storage/migrate_to_postgres.py` | One-time migration from local SQLite to an empty hosted database |
| `src/features/pack_parser.py` | `parse_pack_size`, `calculate_normalized_price` |
| `src/features/label_definitions.sql` | `sku_status_history`, `valid_stockouts` views |
| `src/models/build_features.py` | Loads snapshots; temporal/discount/missing features; `target_stockout` |
| `src/models/train_baseline.py` | L2 logistic regression, TimeSeriesSplit, data guards, `--selftest` |
| `src/models/train_advanced.py` | Calibrated random forest (isotonic, cv=5), threshold 0.35 |
| `src/models/explain_shap.py` | TreeExplainer over the RF; prints plotting instructions |
| `src/api/main.py` | FastAPI app and dashboard; summary, latest products, product history, stock-out and pack-size-alert endpoints |
| `src/api/static/` | Same-origin ShelfWatch market desk (HTML, CSS, vanilla JavaScript) |
| `src/eda/audit_snapshot.py` | Quick audit of the combined CSV |
| `run_crawler_scheduler.py` | 6 h loop with `scheduler.lock` |
| `tests/` | `test_smoke.py` (14) + `test_train_baseline.py` (3) + `test_api.py` (7) + `test_storage.py` (2) = 26 tests |
| `docs/` | This file, CASE_STUDY.md, GIT_WORKFLOW.md |

## 4. Data model

### 4.1 `snapshots`
`id` PK · `source` · `title` · `price` · `list_price` · `discount_percent` ·
`stock_flag` (`in_stock`/`out_of_stock`/`unknown`) · `category_path` ·
`category_rank` · `url` · `scraped_at` (UTC, NOT NULL). Optional
`normalized_unit`, `normalized_amount`, and `price_per_100` columns may be
present in older SQLite databases. The active storage schema indexes
`(source, url)`, `(source, title)`, and `(scraped_at)`.

### 4.2 `ingest_log`
`run_id` = SHA-256 of the CSV bytes (PK), `csv_path`, `rows`, `ingested_at`.
Re-ingesting identical content is a no-op, which makes scheduler retries and
manual re-runs safe.

### 4.3 History ledger
`output/history/snapshot_<YYYYmmdd_HHMMSS>.csv`; oldest files pruned beyond
`HISTORY_KEEP` (60). The ledger is the on-disk time-series source of truth;
the DB is the queryable copy.

### 4.4 Label views (`label_definitions.sql`)
`sku_status_history`: per `url`, LAG-1/LAG-2 of `stock_flag` ordered by
`scraped_at`. `valid_stockouts`: rows whose current **and** previous flag are
`out_of_stock` (a de-bounced "true" stock-out). The training path currently
builds `target_stockout` directly from `stock_flag`; the views define the
agreed label semantics for future work.

### 4.5 Time semantics
All pipeline stamps are UTC. Legacy local-naive stamps were a bug (5–6 h
skew) and were removed; do not reintroduce `pd.Timestamp.now()` in ingestion.

## 5. Collection layer

| Source | Method | Status / limitation |
|---|---|---|
| Chaldal | requests+BS4; JSON then text regex | Enabled; 8 validated leaf categories; parent pages are JS/404 |
| Shwapno | Playwright (leaf price nodes) + HTTP fallback | Enabled; fallback yields less data |
| Daraz | Playwright/HTTP over `/catalog/` + categories | Opt-in only; category grids bot-check blocked |
| Othoba | requests+BS4 nopCommerce | Enabled but 0 rows currently (grid is JS-rendered) |

Politeness: 3 s crawl delay, browser-like User-Agent, Foodpanda excluded
(robots). See `scraper/README.md` for per-site compliance notes.

## 6. Modelling layer

- `build_features.load_and_prep_data()`: reads `snapshots` ordered by time;
  adds `weekday`, `hour_of_day`, `discount_depth` bins
  (`none/low/medium/high/clearance` at 0/10/25/50/100 %), `price_is_missing`,
  and `target_stockout = (stock_flag == 'out_of_stock')`.
- `train_baseline.py`: L2 logistic regression, `class_weight='balanced'`;
  guards `MIN_ROWS=1000`, `MIN_POSITIVES=20`; single-class train folds are
  skipped; metrics are PR-AUC and F2 (recall-weighted). `--selftest` runs a
  deterministic synthetic fixture (seed 7) with a logistic signal in the
  model's own features — a pipeline check, not a performance estimate.
- `train_advanced.py`: RandomForest (100 trees, depth 10, balanced, OOB)
  wrapped in isotonic `CalibratedClassifierCV(cv=5)`; predicts positive at
  probability >= 0.35. Known issues are listed in §10.
- `explain_shap.py`: `shap.TreeExplainer` on the first calibrated RF over a
  100-row transformed sample; prints how to plot in a notebook.

## 7. Operations

```bash
python scraper/main.py [source...]        # scrape (all or one source)
python src/storage/db.py                  # ingest combined CSV (idempotent)
python run_crawler_scheduler.py           # 6 h scrape->ingest loop
python -m unittest discover -s tests -v   # 26 tests, including API/storage contracts
python src/models/train_baseline.py [--selftest]
python src/models/train_advanced.py       # needs >=1000 rows & 20 positives
python src/models/explain_shap.py
python src/eda/audit_snapshot.py
uvicorn src.api.main:app --reload       # Dashboard + API on :8000
```

Production deployment uses the root `index.py` FastAPI entrypoint on Vercel,
with Neon PostgreSQL selected through `DATABASE_URL`. The
`.github/workflows/scrape-and-ingest.yml` workflow runs on a six-hour schedule;
add `DATABASE_URL` as a GitHub Actions secret before enabling it. To seed the
hosted database, set `DATABASE_URL` in the local shell and run
`python -m src.storage.migrate_to_postgres`. The one-time migration preserves
snapshot IDs and refuses to overwrite a non-empty destination. The full setup
is documented in the root README.

Windows notes: run Python with `-X utf8` (or `PYTHONUTF8=1`) when output is
redirected; PowerShell surfaces native stderr as `NativeCommandError` noise —
check the actual log text before treating it as failure.

## 8. Git & release conventions

Branch prefixes `fix/ feat/ docs/ chore/`; small typed commits
(`feat:`, `fix:`, `docs:`, `test:`, `chore:`); tests green before merging;
merge via GitHub PR (web UI) or plain git (`gh` CLI not installed); delete
branches locally and remotely after merge. Never commit `output/**`,
`*.db`, `_*.py`, `_*.txt`, `_*.bat`, `scheduler.lock`. The `imgs/` path carries
a `skip-worktree` bit (`git ls-files -v` shows `S`) because Google Drive locks
the folder on disk — see CASE_STUDY entry E16.

## 9. Changelog

| Date | Change | Reference |
|---|---|---|
| 2026-10-06 | Scraper suite: retries, category validation, Playwright fallback, `scraped_at` + history ledger, Shwapno price fix, Othoba sanitizer/pager, Daraz gate, idempotent UTC ingestion, scratch cleanup | `4be3bb6` merge |
| 2026-10-06 | README expansion + pack-parser API realignment + tests | `b75a91e` |
| 2026-10-06 | Pack-size parser + stock-out label views | PR #1 (`69c1e0c`) |
| 2026-10-07 | Pack features at ingestion + schema migration + 1250-row backfill + 50-row manual verification | `ca7d997`, `87db4c6` (plumbing merge `693bd81`) |
| 2026-10-07 | Baseline model with single-class guards + `--selftest` + tests | `684b1ac` |
| 2026-10-07 | Docs: baseline training guidance | PR #2 (`1e57b4c`) |
| 2026-10-08 | Calibrated random forest + SHAP explainer | PR #3 (`4735a5d`) |
| 2026-10-08 | Living docs: PROJECT_DOCUMENTATION.md + CASE_STUDY.md | this commit |
| 2026-10-08 | FastAPI query API: stock-out & shrinkflation endpoints over shelfwatch.db | `src/api/main.py` |
| 2026-10-08 | Same-origin market dashboard, product search/history, and API contract tests | `src/api/static/`, `tests/test_api.py` |
| 2026-10-08 | Neon PostgreSQL support, safe SQLite history migration, and scheduled GitHub Actions collection for Vercel | `src/storage/`, `.github/workflows/` |

## 10. Known limitations & open items

1. New snapshots use the core retailer fields; the hosted migration does not
   copy legacy normalized-pack columns. The dashboard derives potential
   pack-size changes from listing titles, which should be reviewed rather than
   treated as confirmed shrinkflation.
2. `train_advanced.py` reads `df['stockout']` but features define
   `target_stockout` (KeyError if run); `return` inside the fold loop evaluates
   only fold 1; no single-class guard; `base_estimator=` is deprecated in newer
   scikit-learn (rename to `estimator=`).
3. `explain_shap.py` prints plotting instructions instead of saving artifacts;
   `calibrated_classifiers_[0].estimator` is version-sensitive.
4. Othoba yields 0 rows (JS grid); Daraz opt-in only; coverage is therefore
   Chaldal+Shwapno for now.
5. `stock_flag` is almost always `in_stock`; positives are sparse and the
   label views are not yet wired into training.
6. `imgs/` remains locked on disk by Google Drive sync (hidden from git via
   skip-worktree); `git status` may warn "could not open directory 'imgs/'".
7. Selectors/regexes are markup-sensitive; no license declared yet.
8. The read-only API is public when deployed and has no application-level
   rate limiting. Keep database credentials server-side and use Vercel's
   platform-level abuse protections before promoting high-traffic use.