from __future__ import annotations

import logging
import os

DEFAULT_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging() -> None:
    """Configure global logging settings if they are not yet configured."""

    if logging.getLogger().handlers:
        return

    level_name = os.getenv("ESTIMATE_AUTOMATION_LOG_LEVEL", "INFO")
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(level=level, format=DEFAULT_FORMAT)
