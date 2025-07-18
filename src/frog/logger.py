"""Set up the program's logger."""

import logging
import os
from pathlib import Path

from platformdirs import user_log_path

from frog import config
from frog.hardware.plugins.time import get_current_time

log_file: Path


def get_log_path():
    """Return the user log path."""
    log_path = user_log_path(config.APP_NAME, config.APP_AUTHOR)
    log_path.mkdir(parents=True, exist_ok=True)
    return log_path


def initialise_logging() -> None:
    """Configure the program's logger."""
    global log_file
    log_file = get_log_path() / f"{get_current_time().strftime('%Y%m%d_%H-%M-%S')}.log"

    # Allow user to set log level with environment variable
    log_level = (os.environ.get("FROG_LOG_LEVEL") or "INFO").upper()
    if not hasattr(logging, log_level):
        raise ValueError(f"Invalid log level: {log_level}")

    # Log to console and file
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
    )
