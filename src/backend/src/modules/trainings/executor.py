# Standard Libraries
import time
import pickle
import logging
from typing import Any, Type

# Third-party Libraries
import numpy as np
from sklearn.base import BaseEstimator
from sklearn.model_selection import (
    BaseCrossValidator,
    StratifiedKFold,
    RepeatedStratifiedKFold,
    GridSearchCV,
)

# Local Libraries
from src.modules.models import ModelService
from src.modules.preprocessing import CVStrategyConfig
from src.modules.trainings.schemas import ModelTaskResult


# Logging
logger = logging.getLogger(__name__)


def build_cv_splitter(cv_config: CVStrategyConfig | dict[str, Any]) -> BaseCrossValidator:
    """
    Stage 1: Setup Cross-Validation Splitter according to CV Tier strategy.
    """
    if isinstance(cv_config, dict):
        tier = cv_config.get("tier", 2)
        n_splits = cv_config.get("n_splits", 5)
        n_repeats = cv_config.get("n_repeats", 5)
    else:
        tier = cv_config.tier
        n_splits = cv_config.n_splits
        n_repeats = cv_config.n_repeats or 5

    if tier == 1:
        return RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=42)
    return StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)


def tune_and_fit_model(
    model_cls: Type[BaseEstimator],
    param_grid: list[dict[str, Any]] | dict[str, Any],
    cv: BaseCrossValidator,
    scoring: dict[str, Any],
    metric_sort: str,
    X_train: np.ndarray,
    y_train: np.ndarray,
) -> tuple[BaseEstimator, dict[str, Any], GridSearchCV]:
    """
    Stage 2: Perform Hyperparameter Tuning and Model Fitting via GridSearchCV.
    """
    model = model_cls()

    # Ensure metric_sort is valid
    if metric_sort not in scoring:
        metric_sort = "accuracy"

    grid_search = GridSearchCV(
        estimator=model,
        param_grid=param_grid,
        cv=cv,
        scoring=scoring,
        refit=metric_sort,
        error_score=0.0,
        n_jobs=1,  # Parallelism handled by PyMapReduce across worker cores
    )

    grid_search.fit(X_train, y_train)

    return grid_search.best_estimator_, grid_search.best_params_, grid_search


def evaluate_trained_model(
    best_estimator: BaseEstimator,
    grid_search: GridSearchCV,
    test_data_bytes: bytes | None,
    metric_list: list[str],
    metric_sort: str,
) -> tuple[dict[str, float], float]:
    """
    Stage 3: Calculate evaluation metrics on holdout test set (Tier 3) or CV results (Tier 1/2).
    """
    if test_data_bytes is not None:
        # Tier 3: Evaluate on holdout test set
        X_test, y_test = pickle.loads(test_data_bytes)
        scores = ModelService.evaluate_holdout(best_estimator, X_test, y_test, metric_list)
        primary_score = scores.get(metric_sort, 0.0)
    else:
        # Tier 1 & Tier 2: Extract mean test scores from GridSearchCV cv_results_
        scores = {}
        for m in metric_list:
            key = f"mean_test_{m}"
            if key in grid_search.cv_results_:
                scores[m] = float(grid_search.cv_results_[key][grid_search.best_index_])
            else:
                scores[m] = 0.0
        primary_score = float(grid_search.best_score_)

    return scores, primary_score


def package_task_result(
    model_name: str,
    best_estimator: BaseEstimator,
    best_params: dict[str, Any],
    scores: dict[str, float],
    primary_score: float,
    metric_sort: str,
    start_time: float,
) -> ModelTaskResult:
    """
    Stage 4: Serialize model and package training metadata into ModelTaskResult schema.
    """
    model_bytes = ModelService.serialize_model(best_estimator)
    latency = time.time() - start_time

    return ModelTaskResult(
        model_name=model_name,
        best_params=best_params,
        scores=scores,
        primary_score=primary_score,
        metric_sort=metric_sort,
        model_bytes=model_bytes,
        latency=round(latency, 4),
    )
