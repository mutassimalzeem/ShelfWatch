# src/models/train_baseline.py
"""Stock-out baseline model (regularized logistic regression).

Guards against degenerate training data: with only a handful of snapshots
every observed row is ``in_stock``, so ``target_stockout`` is single-class and
LogisticRegression cannot fit. Instead of a raw ValueError we now report what
is missing and how to proceed. ``--selftest`` runs the full pipeline against a
deterministic synthetic fixture so the modelling code stays validated even
before real stock-out events exist.
"""
import sys

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import average_precision_score, fbeta_score, classification_report
from build_features import load_and_prep_data

MIN_ROWS = 1000
MIN_POSITIVES = 20  # stock-out events needed for a stable baseline fit

CATEGORICAL_FEATURES = ['source', 'category_path', 'discount_depth']
NUMERIC_FEATURES = ['price', 'list_price', 'category_rank', 'weekday', 'price_is_missing']


def build_model_pipeline():
    """Regularized logistic regression baseline with L2 penalty."""
    preprocessor = ColumnTransformer(
        transformers=[
            ('cat', OneHotEncoder(handle_unknown='ignore'), CATEGORICAL_FEATURES),
            ('num', StandardScaler(), NUMERIC_FEATURES)
        ])
    return Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('classifier', LogisticRegression(penalty='l2', class_weight='balanced', max_iter=500))
    ])


def _synthetic_fixture(n_rows=4000, positive_rate=0.12, seed=7):
    """Deterministic fixture mirroring the schema of load_and_prep_data().

    Stock-out probability depends on category_rank, price_is_missing and
    discount_depth so the pipeline has real signal to recover. Used by
    --selftest and the unit tests; never mixed with production data.
    """
    rng = np.random.default_rng(seed)
    days = 10
    rows = []
    for i in range(n_rows):
        rank = int(rng.integers(1, 51))
        missing = int(rng.random() < 0.15)
        price = None if missing else round(float(rng.uniform(20, 1500)), 1)
        if price is None or rng.random() < 0.4:
            list_price = None
        else:
            list_price = round(price * float(rng.uniform(1.0, 1.6)), 1)
        if price is None or list_price is None:
            disc = 0.0
        else:
            disc = round((1 - price / list_price) * 100, 1)
        depth = ('none' if disc <= 0 else 'low' if disc <= 10 else
                 'medium' if disc <= 25 else 'high' if disc <= 50 else 'clearance')
        # Logistic signal, linear in the features the model actually sees,
        # so the baseline pipeline has recoverable structure.
        if positive_rate <= 0:
            base = -50.0  # degenerate single-class fixture for guard tests
        else:
            base = np.log(positive_rate / (1 - positive_rate)) - 1.2
        logit = base + 0.18 * (rank - 25) + 2.2 * missing + 1.0 * (depth == 'none')
        p = 1.0 / (1.0 + np.exp(-logit))
        rows.append({
            'source': str(rng.choice(['chaldal', 'shwapno'])),
            'category_path': str(rng.choice(['Food > Rices', 'Food > Oil',
                                             'Home > Cleaning'])),
            'discount_depth': depth,
            'price': price,
            'list_price': list_price,
            'category_rank': rank,
            'weekday': int(i % 7),
            'price_is_missing': missing,
            'scraped_at': pd.Timestamp('2026-09-01', tz='UTC')
                          + pd.Timedelta(days=int(i * days / n_rows)),
            'target_stockout': int(rng.random() < p),
        })
    return pd.DataFrame(rows)


def run_baseline(df=None):
    """Train/evaluate the baseline over time-ordered folds.

    Returns a list of per-fold metric dicts, or None when training is not
    yet possible (too few rows or too few stock-out positives).
    """
    if df is None:
        df = load_and_prep_data()
    df = df.copy()

    if len(df) < MIN_ROWS:
        print(f"Not enough historical data to train yet ({len(df)} rows < {MIN_ROWS}). "
              "Let the scraper run for a few days!!")
        return None

    positives = int(df['target_stockout'].sum())
    if positives < MIN_POSITIVES:
        print(f"[BASELINE] Cannot train: target_stockout holds only {positives} positive "
              f"row(s) out of {len(df)}; LogisticRegression needs samples of at least "
              f"2 classes (>= {MIN_POSITIVES} events for a stable fit).")
        print("[BASELINE] Every ingested snapshot currently reports in_stock. Stock-out "
              "labels appear once products flip to out_of_stock or disappear between "
              "snapshots, so keep the scheduler running to accumulate timepoints.")
        print("[BASELINE] Meanwhile validate the pipeline with: "
              "python src/models/train_baseline.py --selftest")
        return None

    # Handle missing numeric data simply for the baseline (e.g., list price)
    df[NUMERIC_FEATURES] = df[NUMERIC_FEATURES].fillna(-1)

    X = df[CATEGORICAL_FEATURES + NUMERIC_FEATURES]
    y = df['target_stockout']

    model_pipeline = build_model_pipeline()

    # Time-based splitting (never random)
    tscv = TimeSeriesSplit(n_splits=3)

    metrics = []
    y_test = y_pred = None
    for fold, (train_index, test_index) in enumerate(tscv.split(X), 1):
        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test_fold = y.iloc[train_index], y.iloc[test_index]

        if y_train.nunique() < 2:
            print(f"[BASELINE] Fold {fold} skipped: training window contains only "
                  f"class {int(y_train.iloc[0])}.")
            continue

        model_pipeline.fit(X_train, y_train)
        y_pred = model_pipeline.predict(X_test)
        y_prob = model_pipeline.predict_proba(X_test)[:, 1]

        if y_test_fold.nunique() < 2:
            print(f"[BASELINE] Fold {fold}: test window has a single class "
                  f"({int(y_test_fold.iloc[0])}); metrics skipped.")
            y_test = y_test_fold
            continue

        # Metrics: PR-AUC and F-beta (beta=2 favors recall, avoiding missed stock-outs)
        pr_auc = average_precision_score(y_test_fold, y_prob)
        f2 = fbeta_score(y_test_fold, y_pred, beta=2)
        metrics.append({'fold': fold, 'pr_auc': pr_auc, 'f2': f2})
        y_test = y_test_fold
        print(f"Fold {fold} | PR-AUC: {pr_auc:.3f} | F2-Score: {f2:.3f}")

    if not metrics:
        print("[BASELINE] No fold could be evaluated (single-class windows).")
        return None

    if y_test is not None and y_pred is not None and y_test.nunique() == 2:
        print("\nFinal Split Classification Report:")
        print(classification_report(y_test, y_pred))
    return metrics


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        run_baseline(_synthetic_fixture())
    else:
        run_baseline()

