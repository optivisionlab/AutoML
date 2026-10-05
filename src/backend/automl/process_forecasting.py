"""Causal tabular features for observed-history, one-step forecasting.

This module does not fit anything. Learned preprocessing belongs to the model
Pipeline, which cross-validation clones and fits separately in each train fold.
"""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


CACHE_TARGET = "__forecast_target__"


def _positive_ints(values, name, minimum=1):
    values = tuple(values)
    if any(isinstance(v, bool) or not isinstance(v, int) or v < minimum for v in values):
        raise ValueError(f"{name} must contain integers >= {minimum}")
    return tuple(dict.fromkeys(values))


def make_forecasting_table(data, target, time_column, list_feature=(),
                           lags=(1, 7), rolling_windows=(7,), *, predict_next=False):
    """Sort a single regularly sampled series and create X(t) from y(<t).

    Exogenous list_feature columns must be known at prediction time. No target
    imputation or resampling is performed. For next-step prediction, append one
    row with the next timestamp and a missing target, and set predict_next=True.
    """
    lags = _positive_ints(lags, "lags")
    windows = _positive_ints(rolling_windows, "rolling_windows", minimum=2)
    if not lags:
        raise ValueError("At least one lag is required")
    if target == time_column:
        raise ValueError("time_column and target must differ")
    features = list(dict.fromkeys(c for c in list_feature if c not in (target, time_column)))
    if any(str(c).startswith("__forecast_") for c in features):
        raise ValueError("Exogenous columns cannot use the reserved __forecast_ prefix")
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
        X[f"__forecast_lag_{lag}"] = y.shift(lag)
    history = y.shift(1)
    for window in windows:
        roll = history.rolling(window, min_periods=window)
        X[f"__forecast_mean_{window}"] = roll.mean()
        X[f"__forecast_std_{window}"] = roll.std()
    X["__forecast_dow"] = timestamps.dt.dayofweek
    X["__forecast_month"] = timestamps.dt.month
    X["__forecast_is_weekend"] = (timestamps.dt.dayofweek >= 5).astype(int)
    X.index = pd.DatetimeIndex(timestamps, name=time_column)
    y.index = X.index
    if predict_next:
        return X.iloc[[-1]], None
    return X.iloc[warmup:], y.iloc[warmup:]


def preprocess_data(list_feature, target, data, config):
    options = config.get("forecasting", {})
    if options.get("horizon", 1) != 1:
        raise ValueError("Only observed-history one-step forecasting (horizon=1) is supported")
    if not options.get("time_column"):
        raise ValueError("forecasting.time_column is required")
    X, y = make_forecasting_table(
        data, target, options["time_column"], list_feature,
        options.get("lags", [1, 7]), options.get("rolling_windows", [7]),
    )
    # Pipeline owns preprocessing; no separate fitted artifact is needed.
    return X, y.to_numpy(), None, None


def build_pipeline(estimator):
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
    return Pipeline([("preprocessor", preprocessor), ("model", estimator)])


def write_cache(buffer, X, y):
    frame = X.copy()
    frame[CACHE_TARGET] = np.asarray(y)
    frame.to_parquet(buffer, index=True)


def read_cache(buffer):
    frame = pd.read_parquet(buffer)
    y = frame.pop(CACHE_TARGET).to_numpy()
    return frame, y
