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
)

# Local Libraries
from src.shared import constants
from src.modules.hpo import (
    BaseSearchCV,
    GridSearch,
    RandomSearch,
    BayesianSearch,
    GeneticAlgorithmSearch,
)
from src.modules.models import ModelService, LOWER_IS_BETTER_METRICS
from src.modules.preprocessing import CVStrategyConfig, ContinuousStratifiedKFold, ContinuousRepeatedStratifiedKFold
from src.modules.trainings.schemas import ModelTaskResult


# Logging
logger = logging.getLogger(__name__)


def build_cv_splitter(
    cv_config: CVStrategyConfig | dict[str, Any],
    problem_type: str = constants.ProblemType.CLASSIFICATION
) -> BaseCrossValidator:
    if isinstance(cv_config, dict):
        tier = cv_config.get("tier", 2)
        n_splits = cv_config.get("n_splits", 5)
        n_repeats = cv_config.get("n_repeats", 5)
        name = cv_config.get("name", "")
    else:
        tier = cv_config.tier
        n_splits = cv_config.n_splits
        n_repeats = cv_config.n_repeats or 5
        name = cv_config.name

    if problem_type == constants.ProblemType.REGRESSION:
        if tier == 1 or "Repeated" in name:
            return ContinuousRepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=42)
        return ContinuousStratifiedKFold(n_splits=n_splits, random_state=42)

    if tier == 1 or "Repeated" in name:
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
    search_algorithm: str = constants.SearchAlgorithm.GRIDSEARCH,
) -> tuple[BaseEstimator, dict[str, Any], BaseSearchCV]:
    model = model_cls()

    match search_algorithm:
        case constants.SearchAlgorithm.RANDOMSEARCH:
            searcher = RandomSearch(
                estimator=model,
                param_grid=param_grid,
                cv=cv,
                scoring=scoring,
                refit=metric_sort,
                n_jobs=1,
            )
        case constants.SearchAlgorithm.BAYESIANSEARCH:
            searcher = BayesianSearch(
                estimator=model,
                param_grid=param_grid,
                cv=cv,
                scoring=scoring,
                refit=metric_sort,
                n_jobs=1,
            )
        case constants.SearchAlgorithm.GENETICALGORITHM:
            searcher = GeneticAlgorithmSearch(
                estimator=model,
                param_grid=param_grid,
                cv=cv,
                scoring=scoring,
                refit=metric_sort,
                n_jobs=1,
            )
        case _:
            searcher = GridSearch(
                estimator=model,
                param_grid=param_grid,
                cv=cv,
                scoring=scoring,
                refit=metric_sort,
                n_jobs=1,
            )

    searcher.fit(X_train, y_train)

    return searcher.best_estimator_, searcher.best_params_, searcher


def evaluate_trained_model(
    best_estimator: BaseEstimator,
    grid_search: BaseSearchCV,
    test_data_bytes: bytes | None,
    metric_list: list[str],
    metric_sort: str,
    problem_type: str = constants.ProblemType.CLASSIFICATION
) -> tuple[dict[str, float], float]:
    metric_clean = metric_sort.lower().strip().replace(" ", "_")

    if test_data_bytes is not None:
        X_test, y_test = pickle.loads(test_data_bytes)
        scores = ModelService.evaluate_holdout(
            best_estimator,
            X_test,
            y_test,
            metric_list,
            problem_type=problem_type,
        )
        primary_score = scores.get(metric_clean, 0.0)
    else:
        scores = {}
        for m in metric_list:
            m_clean = m.lower().strip().replace(" ", "_")
            key = f"mean_test_{m_clean}"
            if key in grid_search.cv_results_:
                val = float(grid_search.cv_results_[key][grid_search.best_index_])
                if m_clean in LOWER_IS_BETTER_METRICS and val < 0:
                    val = abs(val)
                scores[m_clean] = val
            else:
                scores[m_clean] = 0.0
        primary_score = scores.get(metric_clean, float(grid_search.best_score_))

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
