# Third-party Libraries
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.compose import ColumnTransformer

# Local Libraries
from src.modules.preprocessing.utils import detect_column_types, build_feature_column_transformer
from src.modules.preprocessing.schemas import CVStrategyConfig


def preprocess_classification_data(
    list_feature: list[str],
    target: str,
    data: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, ColumnTransformer | None, LabelEncoder, list[str]]:
    features = [f for f in list_feature if f != target]
    if not features:
        features = [col for col in data.columns if col != target]

    if not features:
        raise ValueError("No valid feature columns specified for classification.")

    if target not in data.columns:
        raise KeyError(f"Target '{target}' does not exist in dataset columns.")

    data_clean = data.copy()
    y_raw = data_clean[target]
    valid_mask = y_raw.notna()
    if not valid_mask.all():
        data_clean = data_clean[valid_mask].reset_index(drop=True)

    le_target = LabelEncoder()
    y_processed = le_target.fit_transform(data_clean[target].astype(str))

    data_process = data_clean[features].copy()
    numeric_cols, categorical_cols, text_cols = detect_column_types(data_process)
    preprocessor = build_feature_column_transformer(numeric_cols, categorical_cols, text_cols)

    if preprocessor is None:
        X_processed = data_process.to_numpy(dtype=np.float64)
    else:
        X_processed = preprocessor.fit_transform(data_process)

    if hasattr(X_processed, "toarray"):
        X_processed = X_processed.toarray()

    return np.asarray(X_processed), np.asarray(y_processed), preprocessor, le_target, features


def determine_classification_cv_tier(n_rows: int, min_class_count: int = 5) -> CVStrategyConfig:
    safe_splits = max(2, min(5, min_class_count))

    if n_rows <= 500:
        return CVStrategyConfig(
            tier=1,
            name="RepeatedStratifiedKFold",
            n_splits=safe_splits,
            n_repeats=5,
            has_holdout=False,
            description=f"Tier 1 (30 - 500 rows): RepeatedStratifiedKFold ({safe_splits} splits, 5 repeats)"
        )
    elif n_rows <= 10000:
        return CVStrategyConfig(
            tier=2,
            name="StratifiedKFold",
            n_splits=safe_splits,
            has_holdout=False,
            description=f"Tier 2 (501 - 10,000 rows): StratifiedKFold ({safe_splits} splits)"
        )
    else:
        return CVStrategyConfig(
            tier=3,
            name="TrainTestSplit+StratifiedKFold",
            test_size=0.2,
            n_splits=safe_splits,
            has_holdout=True,
            description=f"Tier 3 (> 10,000 rows): Train-Test Split (80/20) + StratifiedKFold ({safe_splits} splits)"
        )


def prepare_classification_data(
    df: pd.DataFrame,
    target_col: str,
    feature_cols: list[str] | None = None,
    random_state: int = 42,
) -> tuple[tuple[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray] | None, CVStrategyConfig, list[str], ColumnTransformer | None, LabelEncoder]:
    data = df.copy()

    if target_col not in data.columns:
        raise ValueError(f"Target column '{target_col}' not found in dataset columns: {list(data.columns)}")

    if not feature_cols:
        feature_cols = [col for col in data.columns if col != target_col]
    else:
        feature_cols = [col for col in feature_cols if col in data.columns and col != target_col]

    if not feature_cols:
        raise ValueError("No valid feature columns specified for training.")

    y_raw = data[target_col]
    valid_mask = y_raw.notna()
    if not valid_mask.all():
        data = data[valid_mask].reset_index(drop=True)

    le_target = LabelEncoder()
    y = le_target.fit_transform(data[target_col].astype(str))

    unique_classes, class_counts = np.unique(y, return_counts=True)
    min_class_count = int(np.min(class_counts)) if len(class_counts) > 0 else 5

    data_process = data[feature_cols].copy()
    numeric_cols, categorical_cols, text_cols = detect_column_types(data_process)
    preprocessor = build_feature_column_transformer(numeric_cols, categorical_cols, text_cols)

    cv_config = determine_classification_cv_tier(len(data), min_class_count)

    if cv_config.has_holdout:
        test_size = cv_config.test_size or 0.2
        try:
            X_train_df, X_test_df, y_train, y_test = train_test_split(
                data_process, y,
                test_size=test_size,
                stratify=y,
                random_state=random_state,
            )
        except ValueError:
            X_train_df, X_test_df, y_train, y_test = train_test_split(
                data_process, y,
                test_size=test_size,
                random_state=random_state,
            )

        if preprocessor is not None:
            X_train = preprocessor.fit_transform(X_train_df)
            X_test = preprocessor.transform(X_test_df)
            if hasattr(X_train, "toarray"):
                X_train = X_train.toarray()
            if hasattr(X_test, "toarray"):
                X_test = X_test.toarray()
        else:
            X_train = X_train_df.to_numpy(dtype=np.float64)
            X_test = X_test_df.to_numpy(dtype=np.float64)

        test_data = (np.asarray(X_test), np.asarray(y_test))
    else:
        if preprocessor is not None:
            X_train = preprocessor.fit_transform(data_process)
            if hasattr(X_train, "toarray"):
                X_train = X_train.toarray()
        else:
            X_train = data_process.to_numpy(dtype=np.float64)

        y_train = y
        test_data = None

    return (np.asarray(X_train), np.asarray(y_train)), test_data, cv_config, feature_cols, preprocessor, le_target
