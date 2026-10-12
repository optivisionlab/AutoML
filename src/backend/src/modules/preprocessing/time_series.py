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
from sklearn.preprocessing import OneHotEncoder, StandardScaler, FunctionTransformer

# Local Libraries
from src.modules.preprocessing.schemas import TimeSeriesConfig


# Prefix of every engineered column, and of the Pipeline step that holds the estimator
FEATURE_PREFIX = "__forecast_"
MODEL_STEP = "model"

# Sampling interval -> seasonal period, used for the lag and rolling window
SEASONAL_PERIODS = {pd.Timedelta(days=1): 7, pd.Timedelta(hours=1): 24}

# Longest span of future steps one prediction request may ask for
MAX_FORECAST_STEPS = 365


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


def determine_time_series_cv_tier(
    n_rows: int,
    time_column: str,
    lags: list[int],
    rolling_windows: list[int],
) -> TimeSeriesConfig:
    """
    Pick the chronological CV by the number of usable rows, like the regression and classification tiers
    """
    tier, n_splits = (1, 3) if n_rows < 200 else (2, 5)
    # Fail early on insufficient samples
    list(TimeSeriesSplit(n_splits=n_splits).split(np.zeros(n_rows)))

    return TimeSeriesConfig(
        tier=tier,
        name="TimeSeriesSplit",
        n_splits=n_splits,
        time_column=time_column,
        lags=lags,
        rolling_windows=rolling_windows,
        description=f"Expanding-window TimeSeriesSplit with {n_splits} chronological folds",
    )


def _find_time_column(df: pd.DataFrame, feature_cols: list[str]) -> str:
    # ponytail: a text column counts as a date when every value parses, so a text column of bare numbers can be mistaken for one
    candidates = [
        col for col in feature_cols
        if pd.api.types.is_datetime64_any_dtype(df[col])
        or (df[col].dtype == object and pd.to_datetime(df[col], errors="coerce", format="mixed").notna().all())
    ]
    if len(candidates) != 1:
        raise ValueError(f"Time series needs exactly one datetime column among the features, found {candidates}")
    return candidates[0]


def prepare_time_series_data(
    df: pd.DataFrame,
    target_col: str,
    feature_cols: list[str] | None = None,
) -> tuple[tuple[pd.DataFrame, np.ndarray], None, TimeSeriesConfig, list[str], FunctionTransformer, None]:
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found in dataset columns: {list(df.columns)}")

    if not feature_cols:
        feature_cols = [col for col in df.columns if col != target_col]
    else:
        feature_cols = [col for col in feature_cols if col in df.columns and col != target_col]

    time_column = _find_time_column(df, feature_cols)
    interval = pd.to_datetime(df[time_column]).sort_values().diff().median()
    period = SEASONAL_PERIODS.get(interval)
    lags, rolling_windows = ([1, period], [period]) if period else ([1], [])

    X, y = make_time_series_table(
        df, target_col, time_column,
        [col for col in feature_cols if col != time_column],
        lags, rolling_windows,
    )
    cv_config = determine_time_series_cv_tier(len(X), time_column, lags, rolling_windows)

    # The time series model reads the raw feature columns itself, so the preprocessor only passes them through
    return (X, y.to_numpy()), None, cv_config, feature_cols, FunctionTransformer(), None


class TimeSeriesForecaster:
    """
    Fitted pipeline plus the tail of the training series. It forecasts the steps that follow the training data
    one at a time, feeding each forecast back in as the newest history (recursive forecasting).
    """

    def __init__(
        self,
        pipeline: Pipeline,
        config: TimeSeriesConfig,
        df: pd.DataFrame,
        target_col: str,
        feature_cols: list[str],
    ):
        self.pipeline = pipeline
        self.time_column = config.time_column
        self.target_col = target_col
        self.feature_cols = feature_cols
        self.exogenous = [col for col in feature_cols if col != config.time_column]
        self.numeric = [col for col in self.exogenous if pd.api.types.is_numeric_dtype(df[col])]
        self.lags = config.lags
        self.rolling_windows = config.rolling_windows

        series = pd.DataFrame({
            "time": pd.to_datetime(df[config.time_column]),
            "target": pd.to_numeric(df[target_col]).astype(float),
        }).sort_values("time")
        self.last_time = series["time"].iloc[-1]
        self.interval = series["time"].diff().median()
        self.history = series["target"].to_list()[-max((*config.lags, *config.rolling_windows)):]

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """
        X holds the feature columns of the future timestamps to forecast, in any order
        """
        df = X if isinstance(X, pd.DataFrame) else pd.DataFrame(X, columns=self.feature_cols)
        df = df.reset_index(drop=True)

        steps = (pd.to_datetime(df[self.time_column]) - self.last_time) / self.interval
        if not ((steps >= 1) & (steps % 1 == 0)).all():
            raise ValueError("Timestamps must come after the last training timestamp, on the same regular interval")
        steps = steps.astype(int)
        horizon = int(steps.max())
        if horizon > MAX_FORECAST_STEPS:
            raise ValueError(f"Cannot forecast more than {MAX_FORECAST_STEPS} steps after the training data")

        # Exogenous values of steps that were not requested stay missing and are imputed by the pipeline
        exogenous = df[self.exogenous].set_axis(steps)
        exogenous = exogenous[~exogenous.index.duplicated(keep="last")].reindex(range(1, horizon + 1))
        for col in self.numeric:
            exogenous[col] = pd.to_numeric(exogenous[col], errors="coerce")
        padding = pd.DataFrame(index=range(len(self.history)), columns=exogenous.columns).astype(exogenous.dtypes)

        history = list(self.history)
        forecasts = {}
        for step in range(1, horizon + 1):
            frame = pd.concat([
                pd.DataFrame({
                    self.time_column: pd.date_range(
                        end=self.last_time + step * self.interval, periods=len(history) + 1, freq=self.interval
                    ),
                    self.target_col: [*history, np.nan],
                }),
                pd.concat([padding, exogenous.iloc[[step - 1]]], ignore_index=True),
            ], axis=1)
            X_step, _ = make_time_series_table(
                frame, self.target_col, self.time_column, self.exogenous,
                self.lags, self.rolling_windows, predict_next=True,
            )
            forecasts[step] = float(self.pipeline.predict(X_step)[0])
            history = [*history[1:], forecasts[step]]

        return np.array([forecasts[step] for step in steps])
