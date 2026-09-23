import numpy as np
import pandas as pd
from typing import Any
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from src.modules.preprocessing.schemas import CVStrategyConfig


class FittedPreprocessor:
    """
    Self-contained preprocessor capturing fitted state (encoders, imputers, scalers)
    for seamless, consistent inference without training-serving skew.
    """
    def __init__(
        self,
        feature_names: list[str],
        target_name: str,
        problem_type: str = "classification",
        categorical_cols: list[str] | None = None,
        numerical_cols: list[str] | None = None,
        imputers: dict[str, Any] | None = None,
        feature_encoders: dict[str, LabelEncoder] | None = None,
        scaler: StandardScaler | None = None,
        target_encoder: LabelEncoder | None = None,
    ):
        self.feature_names = feature_names
        self.target_name = target_name
        self.problem_type = problem_type
        self.categorical_cols = categorical_cols or []
        self.numerical_cols = numerical_cols or []
        self.imputers = imputers or {}
        self.feature_encoders = feature_encoders or {}
        self.scaler = scaler
        self.target_encoder = target_encoder

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        df_proc = pd.DataFrame(index=df.index)

        for col in self.categorical_cols:
            fill_val = self.imputers.get(col, "missing")
            series = df[col].fillna(fill_val).astype(str) if col in df.columns else pd.Series(fill_val, index=df.index, dtype=str)
            encoder = self.feature_encoders.get(col)
            if encoder is not None and len(encoder.classes_) > 0:
                known_classes = set(encoder.classes_)
                default_class = encoder.classes_[0]
                safe_series = series.apply(lambda v: v if v in known_classes else default_class)
                df_proc[col] = encoder.transform(safe_series)
            else:
                df_proc[col] = pd.to_numeric(series, errors="coerce").fillna(0.0)

        for col in self.numerical_cols:
            fill_val = self.imputers.get(col, 0.0)
            series = df[col] if col in df.columns else pd.Series(fill_val, index=df.index)
            df_proc[col] = pd.to_numeric(series, errors="coerce").fillna(fill_val)

        X_proc = df_proc[self.feature_names]
        if self.scaler is not None:
            return self.scaler.transform(X_proc)
        return X_proc.to_numpy(dtype=np.float64)

    def inverse_transform_target(self, y_pred: np.ndarray | list[Any]) -> list[Any]:
        if self.target_encoder is not None:
            try:
                y_arr = np.asarray(y_pred)
                return self.target_encoder.inverse_transform(y_arr.astype(int)).tolist()
            except Exception:
                pass

        return [
            int(p) if isinstance(p, (np.integer, int))
            else float(p) if isinstance(p, (np.floating, float))
            else p
            for p in y_pred
        ]


class TabularPreprocessor:
    """
    Service for tabular data cleaning, encoding, scaling, and CV tier preparation.
    """
    @staticmethod
    def determine_cv_tier(n_rows: int, min_class_count: int = 5) -> CVStrategyConfig:
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

    @classmethod
    def prepare_data(
        cls,
        df: pd.DataFrame,
        target_col: str,
        feature_cols: list[str] | None = None,
        random_state: int = 42
    ) -> tuple[tuple[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray] | None, CVStrategyConfig, list[str], FittedPreprocessor]:
        data = df.copy()

        if target_col not in data.columns:
            raise ValueError(f"Target column '{target_col}' not found in dataset columns: {list(data.columns)}")

        if not feature_cols:
            feature_cols = [col for col in data.columns if col != target_col]
        else:
            feature_cols = [col for col in feature_cols if col in data.columns and col != target_col]

        if not feature_cols:
            raise ValueError("No valid feature columns specified for training.")

        # Target encoding
        y_raw = data[target_col]
        valid_mask = ~y_raw.isna()
        if not valid_mask.all():
            data = data[valid_mask].reset_index(drop=True)
            y_raw = data[target_col]

        target_encoder = LabelEncoder()
        y = target_encoder.fit_transform(y_raw)

        unique_classes, class_counts = np.unique(y, return_counts=True)
        min_class_count = int(np.min(class_counts)) if len(class_counts) > 0 else 5

        # Feature processing
        X_df = data[feature_cols].copy()
        categorical_cols: list[str] = []
        numerical_cols: list[str] = []
        imputers: dict[str, Any] = {}
        feature_encoders: dict[str, LabelEncoder] = {}

        for col in feature_cols:
            if X_df[col].dtype == "object" or X_df[col].dtype.name == "category":
                categorical_cols.append(col)
                mode_val = X_df[col].mode()
                fill_val = mode_val.iloc[0] if not mode_val.empty else "missing"
                imputers[col] = fill_val
                X_df[col] = X_df[col].fillna(fill_val)

                le = LabelEncoder()
                X_df[col] = le.fit_transform(X_df[col].astype(str))
                feature_encoders[col] = le
            else:
                numerical_cols.append(col)
                median_val = X_df[col].median()
                fill_val = float(median_val) if not pd.isna(median_val) else 0.0
                imputers[col] = fill_val
                X_df[col] = X_df[col].fillna(fill_val)

        cv_config = cls.determine_cv_tier(len(data), min_class_count)

        if cv_config.has_holdout:
            test_size = cv_config.test_size or 0.2
            try:
                X_train_df, X_test_df, y_train, y_test = train_test_split(
                    X_df, y,
                    test_size=test_size,
                    stratify=y,
                    random_state=random_state
                )
            except ValueError:
                X_train_df, X_test_df, y_train, y_test = train_test_split(
                    X_df, y,
                    test_size=test_size,
                    random_state=random_state
                )

            scaler = StandardScaler()
            X_train = scaler.fit_transform(X_train_df)
            X_test = scaler.transform(X_test_df)
            test_data = (X_test, y_test)
        else:
            scaler = StandardScaler()
            X_train = scaler.fit_transform(X_df)
            y_train = y
            test_data = None

        fitted_preprocessor = FittedPreprocessor(
            feature_names=feature_cols,
            target_name=target_col,
            problem_type="classification",
            categorical_cols=categorical_cols,
            numerical_cols=numerical_cols,
            imputers=imputers,
            feature_encoders=feature_encoders,
            scaler=scaler,
            target_encoder=target_encoder,
        )

        return (X_train, y_train), test_data, cv_config, feature_cols, fitted_preprocessor
