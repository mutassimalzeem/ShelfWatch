# Model card: stock-out baseline

## What it is for

ShelfWatch includes an experimental logistic-regression model to explore
whether listing details can help identify stock-out observations. It is an
offline baseline only. It is not part of the live dashboard and does not
produce forecasts or seven-day stock-out probabilities.

## What the model learns from

The current training label is `1` when a stored row has
`stock_flag == "out_of_stock"` and `0` otherwise. The model uses retailer,
category, discount, price, listing rank, weekday, and missing-price features.
Its evaluation uses three time-ordered folds so older records are used before
newer records.

Training requires at least 1,000 rows and 20 positive stock-out labels. The
guard prevents the model from failing or reporting misleading metrics when
the data contains only one label class.

## Scores that have actually been measured

The baseline's self-test uses a deterministic, **synthetic** 4,000-row
dataset with a deliberately planted relationship between input features and
stock-out labels. On the checked run:

| Fold | PR-AUC | F2 |
|---|---:|---:|
| 1 | 0.774 | 0.806 |
| 2 | 0.796 | 0.790 |
| 3 | 0.816 | 0.801 |
| **Mean** | **0.795** | **0.799** |

- **PR-AUC** summarizes how well the model ranks positive stock-out examples
  above other examples. It ranges from 0 to 1; higher is better. The score
  depends on how common positive examples are.
- **F2** summarizes precision and recall, weighting recall more heavily. It
  ranges from 0 to 1; higher is better. It rewards finding more stock-outs,
  while still penalizing false alarms.

These results only test that the code can learn the artificial signal. They
are **not a measure of expected production accuracy**.

## Real-world score: not available yet

A read-only query of the production `snapshots` table on 2026-10-08 found
1,901 observations, all marked `in_stock`. The required 20 positive labels
have not been observed, so the model cannot yet be meaningfully trained or
scored against real data. No real-world PR-AUC, F2, accuracy, or recall is
reported.

## Limits and risks

- Retailer stock flags describe what the page showed when scraped. They do not
  guarantee live inventory.
- The current target treats every flag other than `out_of_stock` as a
  negative; missing or unknown labels may therefore be mislabeled.
- Product rows are not yet reliably matched across retailers or between
  snapshots.
- A historical price outlier is recorded in the case study; noisy input can
  mislead later analysis.
- The separate advanced random-forest and SHAP scripts are not validated for
  production use. See the open issues in
  [project documentation](PROJECT_DOCUMENTATION.md#10-known-limitations--open-items).
- The checked local self-test emitted a non-blocking scikit-learn
  `OptimizeWarning` about an unknown `iprint` solver option. The exact
  dependency-level cause has not been confirmed.

## Reproduce the pipeline check

From the repository root:

```bash
python src/models/train_baseline.py --selftest
```

The command does not contact retailers or use production data.
