# Standard Libraries
import pickle
import logging
from typing import Any

# Third-party Libraries
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    r2_score,
    mean_squared_error,
    mean_absolute_error,
    mean_absolute_percentage_error,
    root_mean_squared_error,
    make_scorer,
)

# Local Libraries
from src.shared import search_space


# Logging
logger = logging.getLogger(__name__)


LOWER_IS_BETTER_METRICS = {
    "mse",
    "mae",
    "mape",
    "rmse",
    "mean_squared_error",
    "mean_absolute_error",
    "mean_absolute_percentage_error",
    "root_mean_squared_error",
}


class ModelService:
    @staticmethod
    def build_scoring_dict(
        metric_list: list[str] | None = None,
        problem_type: str = "classification"
    ) -> dict[str, Any]:
        metrics = (
            metric_list
            or (search_space.REGRESSION_METRIC_LIST if problem_type == "regression" else search_space.CLASSIFICATION_METRIC_LIST)
        )
        scoring: dict[str, Any] = {}

        for metric in metrics:
            metric_clean = metric.lower().strip().replace(" ", "_")
            match metric_clean:
                # Classification
                case "accuracy":
                    scoring["accuracy"] = make_scorer(accuracy_score)
                case "f1":
                    scoring["f1"] = make_scorer(f1_score, average="macro", zero_division=0)
                case "precision":
                    scoring["precision"] = make_scorer(precision_score, average="macro", zero_division=0)
                case "recall":
                    scoring["recall"] = make_scorer(recall_score, average="macro", zero_division=0)

                # Regression
                case "r2":
                    scoring["r2"] = make_scorer(r2_score)
                case "mse":
                    scoring["mse"] = make_scorer(mean_squared_error, greater_is_better=False)
                case "mae":
                    scoring["mae"] = make_scorer(mean_absolute_error, greater_is_better=False)
                case "mape":
                    scoring["mape"] = make_scorer(mean_absolute_percentage_error, greater_is_better=False)
                case "rmse":
                    scoring["rmse"] = make_scorer(root_mean_squared_error, greater_is_better=False)
                case _:
                    logger.warning(f"Unsupported metric '{metric}', skipping.")

        if not scoring:
            if problem_type == "regression":
                scoring["r2"] = make_scorer(r2_score)
            else:
                scoring["accuracy"] = make_scorer(accuracy_score)

        return scoring

    @staticmethod
    def evaluate_holdout(
        model: Any,
        X_test: np.ndarray,
        y_test: np.ndarray,
        metric_list: list[str] | None = None,
        problem_type: str = "classification"
    ) -> dict[str, float]:
        if problem_type == "regression":
            metrics = metric_list or search_space.REGRESSION_METRIC_LIST
        else:
            metrics = metric_list or search_space.CLASSIFICATION_METRIC_LIST

        y_pred = model.predict(X_test)
        results: dict[str, float] = {}

        for metric in metrics:
            metric_clean = metric.lower().strip().replace(" ", "_")
            match metric_clean:
                # Classification metrics
                case "accuracy":
                    results["accuracy"] = float(accuracy_score(y_test, y_pred))
                case "f1":
                    results["f1"] = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
                case "precision":
                    results["precision"] = float(precision_score(y_test, y_pred, average="macro", zero_division=0))
                case "recall":
                    results["recall"] = float(recall_score(y_test, y_pred, average="macro", zero_division=0))

                # Regression metrics
                case "r2":
                    results["r2"] = float(r2_score(y_test, y_pred))
                case "mse":
                    results["mse"] = float(mean_squared_error(y_test, y_pred))
                case "mae":
                    results["mae"] = float(mean_absolute_error(y_test, y_pred))
                case "mape":
                    results["mape"] = float(mean_absolute_percentage_error(y_test, y_pred))
                case "rmse":
                    results["rmse"] = float(root_mean_squared_error(y_test, y_pred))

        return results

    @staticmethod
    def serialize_model(model: Any) -> bytes:
        return pickle.dumps(model)

    @staticmethod
    def deserialize_model(data_bytes: bytes) -> Any:
        return pickle.loads(data_bytes)
