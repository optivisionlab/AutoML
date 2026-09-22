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
from src.modules.models import MODEL_CLASS_MAP, ModelService
from src.modules.preprocessing import CVStrategyConfig
from src.modules.trainings.executor import (
    build_cv_splitter,
    tune_and_fit_model,
    evaluate_trained_model,
    package_task_result,
)


# Suppress sklearn convergence & fit warnings on worker nodes
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
) -> dict[str, Any]:
    """
    Distributed Task executed on PyMapReduce Worker Node.
    Orchestrates the 4-stage pipeline for training, tuning, and evaluating a single model.
    """
    start_time = time.time()

    # Unpack data & resolve Estimator Class
    X_train, y_train = pickle.loads(train_data_bytes)
    model_cls = MODEL_CLASS_MAP.get(model_name)
    if not model_cls:
        raise ValueError(f"Model '{model_name}' is not in MODEL_CLASS_MAP.")

    # Stage 1: Build Cross-Validation Splitter
    cv = build_cv_splitter(cv_config)

    # Build Scorers
    scoring = ModelService.build_scoring_dict(metric_list)

    # Stage 2: Tune and Fit Model
    best_estimator, best_params, grid_search = tune_and_fit_model(
        model_cls=model_cls,
        param_grid=param_grid,
        cv=cv,
        scoring=scoring,
        metric_sort=metric_sort,
        X_train=X_train,
        y_train=y_train,
    )

    # Stage 3: Evaluate Model
    scores, primary_score = evaluate_trained_model(
        best_estimator=best_estimator,
        grid_search=grid_search,
        test_data_bytes=test_data_bytes,
        metric_list=metric_list,
        metric_sort=metric_sort,
    )

    # Stage 4: Package Result & Serialize
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
