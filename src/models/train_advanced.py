import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import average_precision_score, fbeta_score, classification_report
from build_features import load_and_prep_data
from sklearn.calibration import CalibratedClassifierCV
import os


CATEGORICAL_FEATURES = ['source', 'category_path', 'discount_depth']
NUMERIC_FEATURES = ['price', 'list_price', 'category_rank', 'weekday', 'price_is_missing']

MIN_ROWS = 1000
MIN_POSITIVES = 20  # stock-out events needed for a stable baseline fit

def run_advanced_model():
    df = load_and_prep_data()

    if len(df) < MIN_ROWS:
        print("Waiting for more data to accumulate before training the model.")
        return

    df['numeric_features'] = df[NUMERIC_FEATURES].fillna(-1)

    X = df[CATEGORICAL_FEATURES + ['numeric_features']]
    y = df['stockout']


    preprocessor = ColumnTransformer(
        transformers=[
            ('cat', OneHotEncoder(handle_unknown='ignore'), CATEGORICAL_FEATURES),
            ('num', 'passthrough', ['numeric_features'])
        ]
    )

    rf_model = RandomForestClassifier(n_estimators=100, random_state=42,
                                       class_weight='balanced', max_depth=10, oob_score = True)


    calibrated_rf = CalibratedClassifierCV(base_estimator=rf_model, method='isotonic', cv=5)

    tscv = TimeSeriesSplit(n_splits=3)

    for train_index, test_index in tscv.split(X):
        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test = y.iloc[train_index], y.iloc[test_index]

        pipeline = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('classifier', calibrated_rf)
        ])

        pipeline.fit(X_train, y_train)

        y_pred_proba = pipeline.predict_proba(X_test)[:, 1]
        y_pred = (y_pred_proba >= 0.35).astype(int)



        print("Average Precision Score:", average_precision_score(y_test, y_pred_proba))
        print("F-beta Score (beta=2):", fbeta_score(y_test, y_pred, beta=2))
        print(classification_report(y_test, y_pred))

        return pipeline, X_train


if __name__ == "__main__":
    run_advanced_model()