# Standard Libraries
import time
import pickle
import logging
from typing import Any
import warnings

# Third-party Libraries
import pymapreduce
from sklearn.exceptions import ConvergenceWarning

# Local Libraries
from src.shared import constants
from src.modules.models import MODEL_CLASS_MAP, ModelService
from src.modules.preprocessing import CVStrategyConfig
from src.modules.trainings.executor import (
    build_cv_splitter,
    tune_and_fit_model,
    evaluate_trained_model,
    package_task_result,
)

warnings.filterwarnings("ignore", category=ConvergenceWarning)
warnings.filterwarnings("ignore", category=UserWarning)


# Logging
logger = logging.getLogger(__name__)


@pymapreduce.remote
def train_single_model_task(
    model_name: str,
    param_grid: list[dict[str, Any]] | dict[str, Any],
    train_data_bytes: bytes,
    test_data_bytes: bytes | None,
    cv_config: CVStrategyConfig | dict[str, Any],
    metric_list: list[str],
    metric_sort: str,
    problem_type: str = constants.ProblemType.CLASSIFICATION,
    search_algorithm: str = constants.SearchAlgorithm.GRIDSEARCH,
) -> dict[str, Any]:
    start_time = time.time()

    X_train, y_train = pickle.loads(train_data_bytes)
    model_cls = MODEL_CLASS_MAP.get(model_name)
    if not model_cls:
        raise ValueError(f"Model '{model_name}' is not in MODEL_CLASS_MAP.")

    cv = build_cv_splitter(cv_config, problem_type=problem_type)
    scoring = ModelService.build_scoring_dict(metric_list, problem_type=problem_type)

    best_estimator, best_params, grid_search = tune_and_fit_model(
        model_cls=model_cls,
        param_grid=param_grid,
        cv=cv,
        scoring=scoring,
        metric_sort=metric_sort,
        X_train=X_train,
        y_train=y_train,
        search_algorithm=search_algorithm,
    )

    scores, primary_score = evaluate_trained_model(
        best_estimator=best_estimator,
        grid_search=grid_search,
        test_data_bytes=test_data_bytes,
        metric_list=metric_list,
        metric_sort=metric_sort,
        problem_type=problem_type,
    )

    task_result = package_task_result(
        model_name=model_name,
        best_estimator=best_estimator,
        best_params=best_params,
        scores=scores,
        primary_score=primary_score,
        metric_sort=metric_sort,
        start_time=start_time,
    )

    return task_result.model_dump()
