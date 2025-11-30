"""
Gunicorn configuration for production deployment.

This module configures Gunicorn to run the FastAPI application with:
- Multiple workers based on CPU count
- Uvicorn worker class for async support
- Environment loading before workers start
"""

import multiprocessing
import os

from dotenv import load_dotenv

from logging_config import configure_logging
from util import get_env_file_path

env_file = get_env_file_path()
load_dotenv(env_file)

logger = configure_logging(os.getenv("APP_LOG_FILE", ""))


def on_starting(server) -> None:
    """
    Gunicorn hook: runs once in master process before workers start.

    Validates environment configuration.
    """
    endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
    if not endpoint:
        logger.warning(
            "AZURE_AI_PROJECT_ENDPOINT not set. Workers may fail to initialize."
        )
    else:
        logger.info("Environment validated. Starting workers...")


# Server binding
bind = "0.0.0.0:50505"

# Worker configuration
workers = (multiprocessing.cpu_count() * 2) + 1
worker_class = "uvicorn.workers.UvicornWorker"

# Timeout for worker responses (seconds)
timeout = 120
