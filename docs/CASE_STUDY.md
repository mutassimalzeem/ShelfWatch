# ShelfWatch — Case Study (2026-10-06 → 2026-10-08)

> **Living document.** This file narrates, in date order, the problems the
> project actually hit and how they were solved. Append new entries using the
> template in Appendix A whenever something noteworthy happens; keep entries
> honest — failed attempts and open issues are part of the record.
> Technical reference: [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md).

## Abstract

Over three days a four-source grocery scraper was turned from a crashing
script into a tested, scheduled, documented data-collection pipeline with a
baseline modelling layer and an explainability path (calibrated random forest
+ SHAP). The dominant theme: **most failures were data and environment
problems, not algorithm problems** — broken prices, missing timestamps,
single-class labels, bot checks, Windows encodings, and a cloud-drive file
lock. Each was converted into a guard, a test, or a documented limitation.

## 1. Context and goals

The project aims at price and shelf-availability intelligence for Bangladesh
grocery retail: repeated snapshots of public listings → stock-out labels →
predictive models. Starting point (Oct 6): four scrapers, no timestamps, a
non-idempotent DB ingest, no tests, no docs, and a first run that crashed.

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
`--selftest` fixture whose logistic signal made all folds learnable
(PR-AUC 0.77–0.82). Lesson: guard degenerate data; keep the pipeline
testable before real events exist.

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

## 3. State as of 2026-10-08

1,250 DB rows over 2 timepoints; 648-row latest snapshot; 619/1250 rows carry
a pack unit; 17/17 tests green; 3 merged PRs; docs: README + 3 docs files.
Models cannot train on real data yet (0 positives) — by design this is
reported, not crashed.

## 4. Lessons learned (process)

1. Validate against live sites; configs rot faster than code.
2. Idempotency and UTC timestamps are prerequisites for time series.
3. Guards + synthetic selftests keep ML code honest before labels exist.
4. Tests and README are part of the definition of done.
5. Branch-per-concern made every fix reviewable and revertible.
6. Environment quirks (Drive locks, cp1252, missing `gh`) deserve docs, not
   tribal memory.

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
fix) · `684b1ac` baseline model · PR #2 `1e57b4c` · PR #3 `4735a5d` RF+SHAP.