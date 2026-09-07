"""Central logging setup.

Call ``configure_logging()`` once at startup (see ``main.py``). Adds a console
handler plus a rotating file handler under ``LOG_DIR`` (default ``logs/``).

Env vars:
  LOG_LEVEL  - root log level, default INFO
  LOG_DIR    - directory for birdle.log, default "logs"
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_configured = False

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging() -> None:
    global _configured
    if _configured:
        return

    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    formatter = logging.Formatter(_FORMAT)

    root = logging.getLogger()
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    log_dir = Path(os.environ.get("LOG_DIR", "logs"))
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "birdle.log", maxBytes=5_000_000, backupCount=5
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        root.warning("file logging disabled: could not write to %s", log_dir)

    _configured = True
