# ShelfWatch — Case Study (2026-10-06 → 2026-10-08)

> **Living document.** This file narrates, in date order, the problems the
> project actually hit and how they were solved. Append new entries using the
> template in Appendix A whenever something noteworthy happens; keep entries
> honest — failed attempts and open issues are part of the record.
> Technical reference: [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md).

## Abstract

Over three days, ShelfWatch grew from a fragile scraper into a tested,
scheduled collection pipeline with a live dashboard. The main problems were
data and environment issues—not advanced machine learning: bad prices,
missing timestamps, blocked retailer pages, Windows encoding, cloud-drive
file locks, and deployment routing. The fixes added checks and clearer
limitations. The model is still experimental because production data does not
yet include enough stock-out examples.

## 1. Context and goals

The project aims at price and shelf-availability intelligence for Bangladesh
grocery retail: repeated snapshots of public listings → useful history →
careful analysis. Starting point (Oct 6): four scrapers, no timestamps, a
non-idempotent database ingest, no tests, and a first run that crashed.

## 2. Timeline — problems and solutions

**E1 · Oct 6 · First run crashes: Playwright browsers missing.**
Symptom: `BrowserType.launch: Executable doesn't exist … headless_shell.exe`.
Root cause: `playwright` pip package installed but browser binaries never
downloaded. Fix: catch the launch error, fall back to HTTP scraping with an
actionable message; `playwright install chromium` run separately. Lesson:
heavy dependencies need graceful degradation in a pipeline that must survive
unattended scheduler runs.

**E2 · Oct 6 · Half the Chaldal categories 404 or empty.**
Symptom: `/frozen-food`, `/baby-care` 404; `/meat-fish`, `/dairy`, `/snacks`
returned 0 products. Root cause: guessed URLs; parent categories render
products via JS only. Fix: probed the live site and kept 8 validated leaf
categories (`/noodles`, `/soft-drinks`, `/laundry`, …). Lesson: verify URLs
against the live site before trusting config.

**E3 · Oct 6 · Read timeouts on Chaldal.**
Fix: exponential backoff retries (`MAX_RETRIES=3`, waits 2 s/4 s). Lesson:
polite retries belong in the fetch layer, not ad hoc.

**E4 · Oct 6 · No time axis: combined CSV overwritten each run.**
Requirement: time-series modelling needs history. Fix: UTC `scraped_at` on
every row plus an append-only `output/history/` snapshot ledger, pruned to
`HISTORY_KEEP=60`. Lesson: timestamp at creation, never retroactively.

**E5 · Oct 6 · Shwapno prices glued together (500485.0, 25102310.0).**
Root cause: whole-card `inner_text()` ("৳ 500 ৳ 485") fed to a digit-stripping
parser. Fix: query only *leaf* price nodes, treat `del`/`s` as list price;
de-duplicate nested cards by title. Verified live: 485/500, 2310/2510, 330/380.
Lesson: never regex-concatenate multi-value text blobs; validate with a live
sample after any parsing change.

**E6 · Oct 6 · Othoba junk titles and stuck pagination.**
Symptom: titles like "Buy Now Rose & Ceramide Face Cream"; `?page=2` returned
byte-identical pages. Fix: `_clean_title()` nav-blob sanitizer and pager-href
discovery from the nopCommerce pager. Residual: the grid itself is
JS-rendered, so Othoba currently contributes 0 rows — documented honestly
instead of shipping garbage. Lesson: a scraper that returns *nothing* is
better than one that returns *noise*.

**E7 · Oct 6 · Daraz bot checks and non-grocery noise.**
Symptom: category grids served captcha/verify pages; only the `/catalog/`
flash-sale strip (wallets, phone stands…) was reachable. Fix: `DARAZ_ENABLED
= False` gate, force with `python main.py daraz`. Lesson: disable a source
cleanly rather than polluting the dataset.

**E8 · Oct 6 · UnicodeEncodeError risk on Windows (cp1252).**
Symptom risk: Bengali text and `৳` crash redirected stdout. Fix: reconfigure
stdout/stderr to UTF-8 in `main.py`; scheduler sets `PYTHONUTF8=1` /
`PYTHONIOENCODING=utf-8`. Lesson: encoding is a deployment concern; fix it at
the boundary.

**E9 · Oct 6 · DB ingestion duplicated rows and re-stamped time.**
Symptom: 1,201 rows = two appends of nearly the same CSV; local naive
`scraped_at` overwrote UTC stamps. Fix: SHA-256 `run_id` idempotency table,
UTC preservation, one-time rebuild to a clean ledger. Lesson: ingestion must
be idempotent before a scheduler exists.

**E10 · Oct 6 · Debug scratch files committed to git.**
Fix: `git rm --cached` the 13 `_*.py/_*.txt/_*.bat` files, extend
`.gitignore`, keep files on disk. Lesson: ignore early; untrack late is ugly.

**E11 · Oct 7 · Test suite red after parser API rewrite.**
The pack parser was rewritten (`parse_pack_size` /
`calculate_normalized_price`) while tests imported the old names. Fix:
re-aligned tests (14 green) and corrected README claims to match reality.
Lesson: the README is a contract — update it in the same commit as behaviour.

**E12 · Oct 7 · Backfill + manual verification of parsed weights.**
Added pack features at ingestion with an `ALTER TABLE` migration; backfilled
1,250 rows; then manually re-parsed a 50-row systematic sample: **0
exceptions, 0 mismatches** (24 with unit / 26 legitimately NULL). Lesson: a
hand-checked sample catches regex pathology that aggregate stats miss.

**E13 · Oct 7 · `ValueError: … only one class: np.int64(0)`.**
Root cause: data, not code — every observed row is `in_stock`, so the target
is single-class. Fix: pre-flight guards (≥1000 rows, ≥20 positives) with
actionable messages, per-fold single-class skips, and a deterministic
`--selftest` fixture whose planted logistic signal made all folds learnable.
The checked synthetic folds scored PR-AUC 0.774/0.796/0.816 and F2
0.806/0.790/0.801. These are pipeline-test scores, not real-world model
performance. Lesson: guard degenerate data; keep the pipeline testable before
real events exist.

**E14 · Oct 7 · "My label definitions vanished!" after `git checkout main`.**
Root cause: branch isolation — the work lived on the feature branch; local
`main` was also 2 commits behind GitHub, where PR #1 had already merged it.
Resolution: explanation + fast-forward procedure + this doc set. Lesson:
"missing code" is usually "wrong branch"; teach the mental model.

**E15 · Oct 7 · Push rejected (non-fast-forward).**
Fix: pull/merge before push, documented in GIT_WORKFLOW.md. Lesson: read the
hint; the remote is part of the state.

**E16 · Oct 7 · `imgs/` permission denied broke merge and push.**
Symptom: `error: cannot stat 'imgs': Permission denied` during merge; ACL
tools fail ("no support for ACLs") because the repo sits on Google Drive,
whose sync client holds the folder. Attempts: takeown/icacls/rd/robocopy/
rename — all denied. Resolution: plumbing merge (`git merge-tree
--write-tree` → `commit-tree` → `update-ref`), push, then `skip-worktree` on
the locked path. The folder remains locked on disk; git no longer cares.
Lesson: when the filesystem fights back, move the work into git's object
store; document the workaround (`S` bit in `git ls-files -v`).

**E17 · Oct 7–8 · User-led PRs: guidance docs, then explainability.**
PR #2 clarified baseline training guidance. PR #3 added a calibrated random
forest + SHAP explainer to answer "why does the model say so?". Review
recorded open issues (wrong column name `stockout`, single-fold return,
deprecated `base_estimator`) in PROJECT_DOCUMENTATION §10 rather than
silently leaving them. Lesson: explainability tooling belongs in the repo
from the start; known defects must be written down.

**E18 · Oct 8 · FastAPI query layer added; unterminated string crash.**
Symptom: `uvicorn src.api.main:app --reload` failed with `SyntaxError:
unterminated triple-quoted string literal (detected at line 53)`. Root cause:
the shrinkflation SQL query was left incomplete — the file ended mid-CTE
without closing the triple-quote or adding the outer SELECT / response logic.
Fix: completed the CTE, added the outer SELECT filtering
`normalized_amount < prev_amount` (window-function LAG comparison), and wired
the pandas read + 404 guard + JSON response mirroring the stockouts endpoint
pattern. Two endpoints now live: `/api/stockouts/current` (NULL
normalized_amount proxy) and `/api/shrinkflation/alerts` (pack-size shrink
detection). Lesson: multi-line SQL strings are fragile; always syntax-check
(`py_compile`) before starting a server, and keep endpoint bodies small and
uniform.

**E19 · Oct 8 · Neon CLI setup hit Google Drive package-install errors.**
Symptom: npm reported extraction and file-operation errors (`EBADF` and
`TAR_ENTRY_ERROR`) in the Google Drive-backed project folder. Root cause:
the synced drive interfered with package installation. Resolution: install and
run the Neon configuration tooling from a normal local folder, while keeping
the project configuration in the repository. Lesson: run build tools on a
filesystem they support; never work around the issue by committing local
credentials or generated package files.

**E20 · Oct 8 · Production database started empty.**
Resolution: migrated the 1,250-row local SQLite history into Neon using the
one-time migration. The migration preserves snapshot IDs and refuses to copy
into a non-empty target. Lesson: check the destination before moving data and
keep the local database as a backup.

**E21 · Oct 8 · First Vercel deployment served the wrong entry point.**
Symptom: the root Python file was delivered as text and API routes returned
404. Root cause: Vercel did not treat the root `index.py` as a Python
function. Fix: moved the function entry point to `api/index.py` and routed
dashboard, API, and asset requests through FastAPI with `vercel.json`. The
change was merged in PR #8; the resulting production deployment became Ready.
Lesson: verify the actual deployed routes, not just a successful build.

**E22 · Oct 8 · Vercel could not see the GitHub repository.**
Symptom: the repository did not appear in the Vercel Git settings. Root
cause: the Vercel GitHub App did not yet have access to ShelfWatch. Fix:
granted access to this repository and connected it to the Vercel project.
After PR #8 merged, Vercel automatically deployed commit `a0253e2` from
`main`. Lesson: project credentials and Git-provider permissions are separate
setup steps.

**E23 · Oct 8 · First hosted collection took several minutes.**
The GitHub Actions run installed Chromium, collected listings, verified that
the output was non-empty, and ingested the snapshot into Neon. It completed
successfully with 651 new observations. Production then reported 1,901
observations and 597 current listings across Chaldal and Shwapno. Lesson:
wait for the browser-based scraper to finish, then verify both the workflow
and the live API.

**E24 · Oct 8 · History revealed an implausible price.**
The production product-history endpoint showed a historical price of
৳1,000,900 for Golden Harvest Chicken Momo 1kg, followed by ৳900 records.
This outlier has not been corrected or traced to its source, so it remains a
data-quality warning rather than a confirmed retailer price. Lesson: inspect
the history behind surprising values before using it for analysis.

**E25 · Oct 8 · Synthetic model check printed a solver warning.**
The local baseline self-test completed and reported all three fold scores, but
scikit-learn printed `OptimizeWarning: Unknown solver options: iprint` during
the run. The warning did not stop the test; its exact dependency-level cause
has not been confirmed. Lesson: record warnings as well as exit status, and
check dependency compatibility before treating the model environment as clean.

## 3. State as of 2026-10-08

The production API reported 1,901 observations, 597 current listings, and
two retailers after the first hosted scrape; the new run added 651
observations to the 1,250-row migration. The API and dashboard are live on
Vercel backed by Neon. The GitHub Actions scraper completed successfully.
The test suite has 26 tests. The baseline has no real performance score:
all 1,901 stored production observations were marked `in_stock`, below the
model's requirement of 20 positive labels. Its synthetic self-test averaged
PR-AUC 0.795 and F2 0.799; these scores only show that the pipeline runs on
artificial data.

## 4. Lessons learned (process)

1. Validate against live sites; configs rot faster than code.
2. Idempotency and UTC timestamps are prerequisites for time series.
3. Guards + synthetic selftests keep ML code honest before labels exist.
4. Tests and README are part of the definition of done.
5. Branch-per-concern made every fix reviewable and revertible.
6. Environment quirks (Drive locks, Windows encoding, missing command-line
   tools, and GitHub permissions) deserve docs, not tribal memory.

## Appendix A — Entry template

```
**E<n> · <YYYY-MM-DD> · <short title>.**
Symptom: … Root cause: … Fix: … (files/commits) Lesson: …
```

## Appendix B — Command cheat-sheet

See PROJECT_DOCUMENTATION §7; git commands live in GIT_WORKFLOW.md.

## Appendix C — Commit / PR reference

`4be3bb6` scraper correctness merge · `b75a91e` README/parser realignment ·
PR #1 `69c1e0c` labels+imgs · `693bd81` plumbing merge (pack features, db
fix) · `684b1ac` baseline model · PR #2 `1e57b4c` · PR #3 `4735a5d` RF+SHAP
(experimental) · PR #8 routing and Neon config.