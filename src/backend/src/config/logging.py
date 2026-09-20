#Standard Libraries
import logging
import logging.config
import sys
from typing import Any

# Local Libraries
from src.config.settings import settings


def setup_logging() -> None:
    """
    General rules for log format across the entire system.
    (display time, error, module name, message)
    """
    is_development = settings.PROJECT.ENVIRONMENT == "development"

    logging_config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "[%(asctime)s] - %(levelname)s - %(name)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": "[%(asctime)s] - %(levelname)s - %(name)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG" if is_development else "INFO",
                "formatter": "standard",
                "stream": sys.stdout,
            },
        },
        "root": {
            "level": "DEBUG" if is_development else "INFO",
            "handlers": ["console"],
        },
        # Minimize logs from third-party libraries
        "loggers": {
            "pymongo": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "asyncio": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "aiokafka": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
            "kafka": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
            "miniopy_async": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
            "aiomqtt": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(logging_config)

    # Create logger to notify setup success
    logger = logging.getLogger(__name__)
    logger.info("Logging configured successfully.")
