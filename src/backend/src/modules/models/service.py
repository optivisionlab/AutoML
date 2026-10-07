# Standard Libraries
import pickle
import logging
from typing import Any

# Third-party Libraries
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
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
from src.shared import search_space, constants


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
        problem_type: str = constants.ProblemType.CLASSIFICATION
    ) -> dict[str, Any]:
        metrics = metric_list or search_space.get_metric_list(problem_type)
        scoring: dict[str, Any] = {}

        for metric in metrics:
            metric_clean = metric.lower().strip().replace(" ", "_")
            match metric_clean:
                # Classification
                case "accuracy":
                    scoring["accuracy"] = make_scorer(accuracy_score)
                case "balanced_accuracy":
                    scoring["balanced_accuracy"] = make_scorer(balanced_accuracy_score)
                case "f1" | "f1_macro":
                    scoring[metric_clean] = make_scorer(f1_score, average="macro", zero_division=0)
                case "f1_weighted":
                    scoring["f1_weighted"] = make_scorer(f1_score, average="weighted", zero_division=0)
                case "precision" | "precision_macro":
                    scoring[metric_clean] = make_scorer(precision_score, average="macro", zero_division=0)
                case "precision_weighted":
                    scoring["precision_weighted"] = make_scorer(precision_score, average="weighted", zero_division=0)
                case "recall" | "recall_macro":
                    scoring[metric_clean] = make_scorer(recall_score, average="macro", zero_division=0)
                case "recall_weighted":
                    scoring["recall_weighted"] = make_scorer(recall_score, average="weighted", zero_division=0)

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
            if problem_type in (constants.ProblemType.REGRESSION, constants.ProblemType.TIME_SERIES):
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
        problem_type: str = constants.ProblemType.CLASSIFICATION
    ) -> dict[str, float]:
        metrics = metric_list or search_space.get_metric_list(problem_type)

        y_pred = model.predict(X_test)
        results: dict[str, float] = {}

        for metric in metrics:
            metric_clean = metric.lower().strip().replace(" ", "_")
            match metric_clean:
                # Classification metrics
                case "accuracy":
                    results["accuracy"] = float(accuracy_score(y_test, y_pred))
                case "balanced_accuracy":
                    results["balanced_accuracy"] = float(balanced_accuracy_score(y_test, y_pred))
                case "f1" | "f1_macro":
                    results[metric_clean] = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
                case "f1_weighted":
                    results["f1_weighted"] = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))
                case "precision" | "precision_macro":
                    results[metric_clean] = float(precision_score(y_test, y_pred, average="macro", zero_division=0))
                case "precision_weighted":
                    results["precision_weighted"] = float(precision_score(y_test, y_pred, average="weighted", zero_division=0))
                case "recall" | "recall_macro":
                    results[metric_clean] = float(recall_score(y_test, y_pred, average="macro", zero_division=0))
                case "recall_weighted":
                    results["recall_weighted"] = float(recall_score(y_test, y_pred, average="weighted", zero_division=0))

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
