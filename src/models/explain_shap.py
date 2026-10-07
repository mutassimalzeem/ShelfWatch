import shap
import pandas as pd
from train_advanced import run_advanced_model, CATEGORICAL_FEATURES, NUMERIC_FEATURES


def generate_explanations():
    print("Training model to generate SHAP values...")

    pipeline, X_train = run_advanced_model()

    if pipeline is None or X_train is None:
        print("Model training failed. Cannot generate SHAP values.")
        return

    # Extract the preprocessor and the fitted Random Forest (from inside the CalibratedClassifierCV)
    preprocessor = pipeline.named_steps['preprocessor']

    
    # Transform a sample of data for SHAP
    X_train_transformed = preprocessor.transform(X_train.head(100))


    
    # Get feature names after OneHotEncoding
    cat_features = preprocessor.named_transformers_['cat'].get_feature_names_out()
    num_features = ['price', 'list_price', 'category_rank', 'weekday', 'price_is_missing']
    all_features = list(cat_features) + num_features


    # Convert sparse matrix to dense DataFrame for SHAP
    if hasattr(X_train_transformed, "toarray"):
        X_train_transformed = X_train_transformed.toarray()
        
    X_shap = pd.DataFrame(X_train_transformed, columns=all_features)

    # Note: SHAP expects the base estimator. We extract the first fitted RF from the CalibratedClassifierCV
    base_rf = pipeline.named_steps['classifier'].calibrated_classifiers_[0].estimator
    
    explainer = shap.TreeExplainer(base_rf)
    shap_values = explainer.shap_values(X_shap)

    print("\nSHAP values calculated successfully. In a notebook, you would run:")
    print("shap.summary_plot(shap_values[1], X_shap)")

if __name__ == "__main__":
    generate_explanations()