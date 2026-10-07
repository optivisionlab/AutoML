# Standard Libraries
import logging
from typing import Any

# Third-party Libraries
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import LabelEncoder

# Local Libraries
from src.shared import constants
from src.modules.preprocessing.schemas import CVStrategyConfig
from src.modules.preprocessing.regression import (
    prepare_regression_data,
    determine_regression_cv_tier,
)
from src.modules.preprocessing.time_series import prepare_time_series_data
from src.modules.preprocessing.classification import (
    prepare_classification_data,
    determine_classification_cv_tier,
)


# Logging
logger = logging.getLogger(__name__)


class FittedPreprocessor:
    def __init__(
        self,
        feature_names: list[str],
        target_name: str,
        problem_type: str = constants.ProblemType.CLASSIFICATION,
        preprocessor: ColumnTransformer | None = None,
        target_encoder: LabelEncoder | None = None,
    ):
        self.feature_names = feature_names
        self.target_name = target_name
        self.problem_type = problem_type
        self.preprocessor = preprocessor
        self.target_encoder = target_encoder

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        df_features = df.copy()

        if self.preprocessor is not None:
            for col in self.feature_names:
                if col not in df_features.columns:
                    df_features[col] = np.nan
            X_out = self.preprocessor.transform(df_features[self.feature_names])
            if hasattr(X_out, "toarray"):
                X_out = X_out.toarray()
            return np.asarray(X_out)

        return df_features[self.feature_names].to_numpy(dtype=np.float64)

    def inverse_transform_target(self, y_pred: np.ndarray | list[Any]) -> list[Any]:
        if self.problem_type == constants.ProblemType.CLASSIFICATION and self.target_encoder is not None:
            try:
                y_arr = np.asarray(y_pred)
                return self.target_encoder.inverse_transform(y_arr.astype(int)).tolist()
            except Exception:
                pass

        return [
            int(p) if isinstance(p, (np.integer, int))
            else round(float(p), 4) if isinstance(p, (np.floating, float))
            else p
            for p in y_pred
        ]


class TabularPreprocessor:
    @staticmethod
    def determine_cv_tier(
        n_rows: int,
        problem_type: str = constants.ProblemType.CLASSIFICATION,
        min_class_count: int = 5,
    ) -> CVStrategyConfig:
        if problem_type == constants.ProblemType.TIME_SERIES:
            raise ValueError("Time series CV depends on its TimeSeriesConfig; use prepare_time_series_data")
        if problem_type == constants.ProblemType.REGRESSION:
            return determine_regression_cv_tier(n_rows)
        return determine_classification_cv_tier(n_rows, min_class_count)

    @classmethod
    def prepare_data(
        cls,
        df: pd.DataFrame,
        target_col: str,
        feature_cols: list[str] | None = None,
        problem_type: str = constants.ProblemType.CLASSIFICATION,
        random_state: int = 42,
        time_series_config: dict[str, Any] | None = None,
    ) -> tuple[tuple[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray] | None, CVStrategyConfig, list[str], FittedPreprocessor]:
        if problem_type == constants.ProblemType.TIME_SERIES:
            # Learned preprocessing stays inside the model Pipeline (fitted per CV fold), so there is nothing to fit here
            (X_train, y_train), test_data, cv_config, features = prepare_time_series_data(
                df=df,
                target_col=target_col,
                feature_cols=feature_cols,
                time_series_config=time_series_config,
            )
            preprocessor, target_encoder = None, None
        elif problem_type == constants.ProblemType.REGRESSION:
            (X_train, y_train), test_data, cv_config, features, preprocessor, target_encoder = prepare_regression_data(
                df=df,
                target_col=target_col,
                feature_cols=feature_cols,
                random_state=random_state,
            )
        else:
            (X_train, y_train), test_data, cv_config, features, preprocessor, target_encoder = prepare_classification_data(
                df=df,
                target_col=target_col,
                feature_cols=feature_cols,
                random_state=random_state,
            )

        fitted_preprocessor = FittedPreprocessor(
            feature_names=features,
            target_name=target_col,
            problem_type=problem_type,
            preprocessor=preprocessor,
            target_encoder=target_encoder,
        )

        return (X_train, y_train), test_data, cv_config, features, fitted_preprocessor
