"""
Causal tabular features for observed-history, one-step time series forecasting.

Nothing is fitted here. Learned preprocessing lives in the model Pipeline, which
cross-validation clones and fits separately on each train fold.
"""
# Third-party Libraries
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.impute import SimpleImputer
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Local Libraries
from src.modules.preprocessing.schemas import CVStrategyConfig, TimeSeriesConfig


# Prefix of every engineered column, and of the Pipeline step that holds the estimator
FEATURE_PREFIX = "__forecast_"
MODEL_STEP = "model"


def _positive_ints(values, name: str, minimum: int = 1) -> tuple[int, ...]:
    values = tuple(values)
    if any(isinstance(v, bool) or not isinstance(v, int) or v < minimum for v in values):
        raise ValueError(f"{name} must contain integers >= {minimum}")
    return tuple(dict.fromkeys(values))


def make_time_series_table(
    data: pd.DataFrame,
    target: str,
    time_column: str,
    list_feature: list[str] | tuple[str, ...] = (),
    lags: list[int] | tuple[int, ...] = (1, 7),
    rolling_windows: list[int] | tuple[int, ...] = (7,),
    *,
    predict_next: bool = False,
) -> tuple[pd.DataFrame, pd.Series | None]:
    """
    Sort a single regularly sampled series and create X(t) from y(<t).

    Exogenous list_feature columns must be known at prediction time. No target imputation
    or resampling is performed. For next-step prediction, append one row with the next
    timestamp and a missing target, and set predict_next=True.
    """
    lags = _positive_ints(lags, "lags")
    windows = _positive_ints(rolling_windows, "rolling_windows", minimum=2)
    if not lags:
        raise ValueError("At least one lag is required")
    if target == time_column:
        raise ValueError("time_column and target must differ")

    features = list(dict.fromkeys(c for c in list_feature if c not in (target, time_column)))
    if any(str(c).startswith(FEATURE_PREFIX) for c in features):
        raise ValueError(f"Exogenous columns cannot use the reserved {FEATURE_PREFIX} prefix")

    required = [time_column, target, *features]
    missing = set(required) - set(data.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    frame = data[required].copy()
    frame[time_column] = pd.to_datetime(frame[time_column], errors="raise")
    frame = frame.sort_values(time_column, kind="stable").reset_index(drop=True)
    timestamps = frame[time_column]
    if timestamps.isna().any() or timestamps.duplicated().any():
        raise ValueError("Timestamps must be non-null and unique for a single series")
    intervals = timestamps.diff().dropna()
    if len(intervals) == 0 or intervals.nunique() != 1:
        raise ValueError("Timestamps must be equally spaced; resample explicitly before training")

    y = pd.to_numeric(frame[target], errors="raise").astype(float)
    observed = y.iloc[:-1] if predict_next else y
    if not np.isfinite(observed).all():
        raise ValueError("Observed target values must be finite; missing target rows cannot be dropped")
    if predict_next and not pd.isna(y.iloc[-1]):
        raise ValueError("The final row must have a missing target for next-step prediction")

    warmup = max((*lags, *windows))
    if len(frame) <= warmup:
        raise ValueError(f"Need more than {warmup} rows for the requested history")

    X = frame[features].copy()
    for col in features:
        if pd.api.types.is_numeric_dtype(X[col]):
            if np.isinf(X[col].astype(float)).any():
                raise ValueError(f"Exogenous column {col} contains infinity")
        else:
            X[col] = X[col].map(lambda v: str(v) if pd.notna(v) else np.nan)

    for lag in lags:
        X[f"{FEATURE_PREFIX}lag_{lag}"] = y.shift(lag)
    history = y.shift(1)
    for window in windows:
        roll = history.rolling(window, min_periods=window)
        X[f"{FEATURE_PREFIX}mean_{window}"] = roll.mean()
        X[f"{FEATURE_PREFIX}std_{window}"] = roll.std()
    X[f"{FEATURE_PREFIX}dow"] = timestamps.dt.dayofweek
    X[f"{FEATURE_PREFIX}month"] = timestamps.dt.month
    X[f"{FEATURE_PREFIX}is_weekend"] = (timestamps.dt.dayofweek >= 5).astype(int)

    X.index = pd.DatetimeIndex(timestamps, name=time_column)
    y.index = X.index
    if predict_next:
        return X.iloc[[-1]], None
    return X.iloc[warmup:], y.iloc[warmup:]


def build_time_series_pipeline(estimator: BaseEstimator) -> Pipeline:
    """
    Wrap an estimator with leak-free preprocessing; its params are addressed as model__<param>
    """
    numeric = Pipeline([
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("scaler", StandardScaler()),
    ])
    categorical = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent", keep_empty_features=True)),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    preprocessor = ColumnTransformer([
        ("num", numeric, make_column_selector(dtype_include=np.number)),
        ("cat", categorical, make_column_selector(dtype_exclude=np.number)),
    ], remainder="drop", sparse_threshold=0)
    return Pipeline([("preprocessor", preprocessor), (MODEL_STEP, estimator)])


def determine_time_series_cv_tier(n_rows: int, config: TimeSeriesConfig) -> CVStrategyConfig:
    splitter = TimeSeriesSplit(
        n_splits=config.n_splits,
        test_size=config.test_size,
        gap=config.gap,
        max_train_size=config.max_train_size,
    )
    # Fail early on insufficient samples / invalid configuration
    list(splitter.split(np.zeros(n_rows)))

    return CVStrategyConfig(
        tier=2,
        name="TimeSeriesSplit",
        n_splits=config.n_splits,
        gap=config.gap,
        max_train_size=config.max_train_size,
        fold_test_size=config.test_size,
        has_holdout=False,
        description=f"Expanding-window TimeSeriesSplit with {config.n_splits} chronological folds (gap={config.gap})",
    )


def prepare_time_series_data(
    df: pd.DataFrame,
    target_col: str,
    feature_cols: list[str] | None,
    time_series_config: TimeSeriesConfig | dict | None,
) -> tuple[tuple[pd.DataFrame, np.ndarray], None, CVStrategyConfig, list[str]]:
    if time_series_config is None:
        raise ValueError("time_series config with a time_column is required for time_series problems")
    config = TimeSeriesConfig.model_validate(time_series_config)

    X, y = make_time_series_table(
        df, target_col, config.time_column, feature_cols or [],
        config.lags, config.rolling_windows,
    )
    cv_config = determine_time_series_cv_tier(len(X), config)

    return (X, y.to_numpy()), None, cv_config, list(X.columns)


def predict_time_series(
    model: BaseEstimator,
    df: pd.DataFrame,
    target_col: str,
    config: TimeSeriesConfig | dict,
    list_feature: list[str],
) -> list[float | None]:
    """
    Predict aligned with the rows of df (None where no prediction is possible).

    If the last observation (in time order) has a missing target, only that next step is
    predicted; otherwise every row beyond the lag/rolling warm-up is predicted.
    """
    config = TimeSeriesConfig.model_validate(config)
    if config.time_column not in df.columns:
        raise ValueError(f"Missing required time column: {config.time_column}")

    timestamps = pd.to_datetime(df[config.time_column], errors="raise")
    predict_next = target_col in df.columns and pd.isna(df[target_col].iloc[int(np.argmax(timestamps.to_numpy()))])

    X, _ = make_time_series_table(
        df, target_col, config.time_column, list_feature,
        config.lags, config.rolling_windows, predict_next=predict_next,
    )
    predictions = pd.Series(np.asarray(model.predict(X)).ravel(), index=X.index)

    aligned = timestamps.map(predictions)
    return [None if pd.isna(v) else float(v) for v in aligned]
