# Standard Libraries
import logging
from typing import Any

# Third-party Libraries
import yaml

# Local Libraries
from src.config import settings

logger = logging.getLogger(__name__)


def _load_classification_config() -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """
    Read model configuration from YAML file
    """
    target_path = settings.BASE_DIR / "assets" / "classification.yml"

    if not target_path.exists():
        logger.error(f"Configuration file not found at: {target_path}")
        raise FileNotFoundError(f"Configuration file not found at: {target_path}")

    with open(target_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    classification_models_raw = data.get("Classification_models", {})
    metrics = data.get("metric_list", [])

    models: dict[str, list[dict[str, Any]]] = {
        model_info["model"]: model_info.get("params", [])
        for model_info in classification_models_raw.values()
        if isinstance(model_info, dict) and "model" in model_info
    }

    return models, metrics


# Automatically load into RAM
CLASSIFICATION_MODELS, METRIC_LIST = _load_classification_config()
