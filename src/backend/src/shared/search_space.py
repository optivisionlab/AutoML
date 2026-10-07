# Standard Libraries
import yaml
import logging
from typing import Any

# Local Libraries
from src.config import settings
from src.shared import constants


# Logging
logger = logging.getLogger(__name__)


def _load_model_config(problem_type: str) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    match problem_type:
        case constants.ProblemType.CLASSIFICATION:
            target_path = settings.BASE_DIR / "assets" / "classification.yml"
        case constants.ProblemType.REGRESSION:
            target_path = settings.BASE_DIR / "assets" / "regression.yml"
        case constants.ProblemType.TIME_SERIES:
            target_path = settings.BASE_DIR / "assets" / "time_series.yml"
        case _:
            logger.error(f"Invalid problem type: {problem_type}")
            raise ValueError(f"Invalid problem type: {problem_type}")

    if not target_path.exists():
        logger.error(f"Configuration file not found at: {target_path}")
        raise FileNotFoundError(f"Configuration file not found at: {target_path}")

    with open(target_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    models_raw = data.get("Classification_models") or data.get("Regression_models") or data.get("Time_series_models") or data.get("models") or {}
    metrics = data.get("metric_list", [])

    models: dict[str, list[dict[str, Any]]] = {
        model_info["model"]: model_info.get("params", [])
        for model_info in models_raw.values()
        if isinstance(model_info, dict) and "model" in model_info
    }

    return models, metrics


CLASSIFICATION_MODELS, CLASSIFICATION_METRIC_LIST = _load_model_config("classification")
REGRESSION_MODELS, REGRESSION_METRIC_LIST = _load_model_config("regression")
TIME_SERIES_MODELS, TIME_SERIES_METRIC_LIST = _load_model_config("time_series")


def get_models(problem_type: str) -> dict[str, list[dict[str, Any]]]:
    match problem_type:
        case constants.ProblemType.REGRESSION:
            return REGRESSION_MODELS
        case constants.ProblemType.TIME_SERIES:
            return TIME_SERIES_MODELS
        case _:
            return CLASSIFICATION_MODELS


def get_metric_list(problem_type: str) -> list[str]:
    match problem_type:
        case constants.ProblemType.REGRESSION:
            return REGRESSION_METRIC_LIST
        case constants.ProblemType.TIME_SERIES:
            return TIME_SERIES_METRIC_LIST
        case _:
            return CLASSIFICATION_METRIC_LIST
