# Third-party Libraries
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

# Local Libraries
from src.modules.preprocessing.service import TabularPreprocessor


def test_tabular_preprocessing_and_training_flow(sample_classification_df):
    """
    Test End-to-End Pipeline: Raw DataFrame -> Preprocessing -> Model Training -> Inference
    """
    # 1. Preprocessing
    (X_train, y_train), holdout_data, cv_strategy, feature_names, preprocessor = (
        TabularPreprocessor.prepare_data(
            sample_classification_df,
            target_col="target",
            problem_type="classification"
        )
    )

    assert preprocessor.problem_type == "classification"
    assert len(feature_names) == 3
    assert X_train.shape[0] == 50
    assert y_train.shape[0] == 50

    # 2. Train a baseline classifier
    clf = RandomForestClassifier(n_estimators=10, random_state=42)
    clf.fit(X_train, y_train)

    # 3. Predict on new batch
    new_data = pd.DataFrame({
        "feature_num1": [0.5, -1.2],
        "feature_num2": [50.0, 80.0],
        "feature_cat": ["A", "B"]
    })
    X_new = preprocessor.transform(new_data)
    preds = clf.predict(X_new)

    assert len(preds) == 2
    assert set(preds).issubset({0, 1})

    # 4. Inverse transform predictions
    target_labels = preprocessor.inverse_transform_target(preds)
    assert len(target_labels) == 2
