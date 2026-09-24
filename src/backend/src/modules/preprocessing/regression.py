# Third-party Libraries
import numpy as np
import pandas as pd
from sklearn.model_selection import (
    BaseCrossValidator,
    StratifiedKFold,
    RepeatedStratifiedKFold,
    KFold,
    RepeatedKFold,
    train_test_split,
)
from sklearn.compose import ColumnTransformer

# Local Libraries
from src.modules.preprocessing.utils import detect_column_types, build_feature_column_transformer
from src.modules.preprocessing.schemas import CVStrategyConfig


def create_target_bins(y: np.ndarray, n_bins: int | None = None) -> np.ndarray:
    y_arr = np.asarray(y).ravel()
    n_samples = len(y_arr)
    if n_samples < 4:
        return np.zeros(n_samples, dtype=int)

    if n_bins is None:
        sturges = int(np.floor(1 + np.log2(n_samples)))
        n_bins = max(2, min(10, sturges, n_samples // 3))

    try:
        bins = pd.qcut(y_arr, q=n_bins, labels=False, duplicates="drop")
        if isinstance(bins, pd.Series):
            bins = bins.to_numpy()
        if len(np.unique(bins)) < 2:
            ranks = pd.Series(y_arr).rank(method="first").to_numpy()
            bins = pd.qcut(ranks, q=n_bins, labels=False, duplicates="drop").to_numpy()
    except Exception:
        ranks = pd.Series(y_arr).rank(method="first").to_numpy()
        bins = pd.qcut(ranks, q=n_bins, labels=False, duplicates="drop").to_numpy()

    return np.asarray(bins, dtype=int)


class ContinuousStratifiedKFold(BaseCrossValidator):
    def __init__(
        self,
        n_splits: int = 5,
        shuffle: bool = True,
        random_state: int = 42,
        n_bins: int | None = None,
    ):
        self.n_splits = n_splits
        self.shuffle = shuffle
        self.random_state = random_state
        self.n_bins = n_bins

    def get_n_splits(self, X=None, y=None, groups=None) -> int:
        return self.n_splits

    def split(self, X, y=None, groups=None):
        if y is None:
            kf = KFold(n_splits=self.n_splits, shuffle=self.shuffle, random_state=self.random_state)
            yield from kf.split(X)
            return

        bins = create_target_bins(y, self.n_bins)
        _, counts = np.unique(bins, return_counts=True)
        if len(counts) >= 2 and counts.min() >= self.n_splits:
            skf = StratifiedKFold(n_splits=self.n_splits, shuffle=self.shuffle, random_state=self.random_state)
            yield from skf.split(X, bins)
        else:
            kf = KFold(n_splits=self.n_splits, shuffle=self.shuffle, random_state=self.random_state)
            yield from kf.split(X, y)


class ContinuousRepeatedStratifiedKFold(BaseCrossValidator):
    def __init__(
        self,
        n_splits: int = 5,
        n_repeats: int = 5,
        random_state: int = 42,
        n_bins: int | None = None,
    ):
        self.n_splits = n_splits
        self.n_repeats = n_repeats
        self.random_state = random_state
        self.n_bins = n_bins

    def get_n_splits(self, X=None, y=None, groups=None) -> int:
        return self.n_splits * self.n_repeats

    def split(self, X, y=None, groups=None):
        if y is None:
            rkf = RepeatedKFold(n_splits=self.n_splits, n_repeats=self.n_repeats, random_state=self.random_state)
            yield from rkf.split(X)
            return

        bins = create_target_bins(y, self.n_bins)
        _, counts = np.unique(bins, return_counts=True)

        if len(counts) >= 2 and counts.min() >= self.n_splits:
            rskf = RepeatedStratifiedKFold(
                n_splits=self.n_splits,
                n_repeats=self.n_repeats,
                random_state=self.random_state,
            )
            yield from rskf.split(X, bins)
        else:
            rkf = RepeatedKFold(
                n_splits=self.n_splits,
                n_repeats=self.n_repeats,
                random_state=self.random_state,
            )
            yield from rkf.split(X, y)


def preprocess_regression_data(
    list_feature: list[str],
    target: str,
    data: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, ColumnTransformer | None, None, list[str]]:
    features = [f for f in list_feature if f != target]
    if not features:
        features = [col for col in data.columns if col != target]

    if not features:
        raise ValueError("No valid feature columns specified for regression.")

    if target not in data.columns:
        raise KeyError(f"Target '{target}' does not exist in dataset columns.")

    y_series = pd.to_numeric(data[target], errors="coerce")
    valid_mask = y_series.notna()
    if not valid_mask.any():
        raise ValueError(f"Target column '{target}' contains no valid numeric values for regression.")

    data_clean = data.loc[valid_mask].reset_index(drop=True)
    y_processed = y_series.loc[valid_mask].to_numpy(dtype=np.float64)

    data_process = data_clean[features].copy()
    numeric_cols, categorical_cols, text_cols = detect_column_types(data_process)
    preprocessor = build_feature_column_transformer(numeric_cols, categorical_cols, text_cols)

    if preprocessor is None:
        X_processed = data_process.to_numpy(dtype=np.float64)
    else:
        X_processed = preprocessor.fit_transform(data_process)

    if hasattr(X_processed, "toarray"):
        X_processed = X_processed.toarray()

    return np.asarray(X_processed), np.asarray(y_processed), preprocessor, None, features


def determine_regression_cv_tier(n_rows: int) -> CVStrategyConfig:
    safe_splits = 5 if n_rows >= 20 else max(2, n_rows // 4)

    if n_rows <= 500:
        return CVStrategyConfig(
            tier=1,
            name="ContinuousRepeatedStratifiedKFold",
            n_splits=safe_splits,
            n_repeats=5,
            has_holdout=False,
            description=f"Tier 1 (<= 500 rows): Continuous Repeated Stratified K-Fold ({safe_splits} splits, 5 repeats)"
        )
    elif n_rows <= 10000:
        return CVStrategyConfig(
            tier=2,
            name="ContinuousStratifiedKFold",
            n_splits=safe_splits,
            has_holdout=False,
            description=f"Tier 2 (501 - 10,000 rows): Continuous Stratified K-Fold ({safe_splits} splits)"
        )
    else:
        return CVStrategyConfig(
            tier=3,
            name="ContinuousStratifiedTrainTestSplit+ContinuousStratifiedKFold",
            test_size=0.2,
            n_splits=safe_splits,
            has_holdout=True,
            description=f"Tier 3 (> 10,000 rows): Continuous Stratified Train-Test Split (80/20) + Continuous Stratified K-Fold ({safe_splits} splits)"
        )


def prepare_regression_data(
    df: pd.DataFrame,
    target_col: str,
    feature_cols: list[str] | None = None,
    random_state: int = 42,
) -> tuple[tuple[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray] | None, CVStrategyConfig, list[str], ColumnTransformer | None, None]:
    data = df.copy()

    if target_col not in data.columns:
        raise ValueError(f"Target column '{target_col}' not found in dataset columns: {list(data.columns)}")

    if not feature_cols:
        feature_cols = [col for col in data.columns if col != target_col]
    else:
        feature_cols = [col for col in feature_cols if col in data.columns and col != target_col]

    if not feature_cols:
        raise ValueError("No valid feature columns specified for training.")

    y_series = pd.to_numeric(data[target_col], errors="coerce")
    valid_mask = y_series.notna()
    if not valid_mask.any():
        raise ValueError(f"Target column '{target_col}' contains no valid numeric values for regression.")

    data_clean = data.loc[valid_mask].reset_index(drop=True)
    y = y_series.loc[valid_mask].to_numpy(dtype=np.float64)

    data_process = data_clean[feature_cols].copy()
    numeric_cols, categorical_cols, text_cols = detect_column_types(data_process)
    preprocessor = build_feature_column_transformer(numeric_cols, categorical_cols, text_cols)

    cv_config = determine_regression_cv_tier(len(data_clean))

    if cv_config.has_holdout:
        test_size = cv_config.test_size or 0.2
        target_bins = create_target_bins(y)
        _, counts = np.unique(target_bins, return_counts=True)
        stratify_arg = target_bins if (len(counts) >= 2 and counts.min() >= 2) else None

        X_train_df, X_test_df, y_train, y_test = train_test_split(
            data_process,
            y,
            test_size=test_size,
            random_state=random_state,
            stratify=stratify_arg,
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

    return (np.asarray(X_train), np.asarray(y_train)), test_data, cv_config, feature_cols, preprocessor, None
