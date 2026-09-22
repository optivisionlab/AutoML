# Standard Libraries
import pickle
import logging
from typing import Any

# Third-party Libraries
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, make_scorer

# Local Libraries
from src.shared import search_space


# Logging
logger = logging.getLogger(__name__)


class ModelService:
    """
    Service for model evaluation, metrics creation, and model serialization.
    """
    @staticmethod
    def build_scoring_dict(metric_list: list[str] | None = None) -> dict[str, Any]:
        """
        Build dictionary of scorers for GridSearchCV with safe macro averaging and zero_division=0.
        """
        metrics = metric_list or search_space.METRIC_LIST
        scoring: dict[str, Any] = {}

        for metric in metrics:
            metric_clean = metric.lower().strip()
            if metric_clean == "accuracy":
                scoring["accuracy"] = make_scorer(accuracy_score)
            elif metric_clean == "f1":
                scoring["f1"] = make_scorer(f1_score, average="macro", zero_division=0)
            elif metric_clean == "precision":
                scoring["precision"] = make_scorer(precision_score, average="macro", zero_division=0)
            elif metric_clean == "recall":
                scoring["recall"] = make_scorer(recall_score, average="macro", zero_division=0)
            else:
                logger.warning(f"Unsupported metric '{metric}', skipping.")

        if not scoring:
            scoring["accuracy"] = make_scorer(accuracy_score)

        return scoring

    @staticmethod
    def evaluate_holdout(
        model: Any,
        X_test: np.ndarray,
        y_test: np.ndarray,
        metric_list: list[str] | None = None
    ) -> dict[str, float]:
        """
        Evaluate a trained model on a holdout test set across all specified metrics.
        """
        metrics = metric_list or search_space.METRIC_LIST
        y_pred = model.predict(X_test)
        results: dict[str, float] = {}

        for metric in metrics:
            metric_clean = metric.lower().strip()
            if metric_clean == "accuracy":
                results["accuracy"] = float(accuracy_score(y_test, y_pred))
            elif metric_clean == "f1":
                results["f1"] = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
            elif metric_clean == "precision":
                results["precision"] = float(precision_score(y_test, y_pred, average="macro", zero_division=0))
            elif metric_clean == "recall":
                results["recall"] = float(recall_score(y_test, y_pred, average="macro", zero_division=0))

        return results

    @staticmethod
    def serialize_model(model: Any) -> bytes:
        """
        Serialize model object to bytes using pickle.
        """
        return pickle.dumps(model)

    @staticmethod
    def deserialize_model(data_bytes: bytes) -> Any:
        """
        Deserialize model object from bytes.
        """
        return pickle.loads(data_bytes)
