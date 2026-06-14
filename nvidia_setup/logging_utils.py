"""
Logging utilities for the nvidia_setup library.

Provides a single :func:`setup_logging` helper that configures the root
``nvidia_setup`` logger with sensible defaults (coloured console output and
optional file handler).

Usage:
    >>> from nvidia_setup.logging_utils import setup_logging
    >>> setup_logging(level="DEBUG", log_file="/tmp/nvidia_setup.log")
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional


# ANSI colour codes for terminal output
_ANSI_RESET = "\033[0m"
_ANSI_COLOURS = {
    logging.DEBUG: "\033[36m",     # Cyan
    logging.INFO: "\033[32m",      # Green
    logging.WARNING: "\033[33m",   # Yellow
    logging.ERROR: "\033[31m",     # Red
    logging.CRITICAL: "\033[35m",  # Magenta
}


class _ColouredFormatter(logging.Formatter):
    """Logging formatter that prepends ANSI colour codes to the level name.

    Only applies colours when the target stream is a TTY to avoid polluting
    pipe/file output.
    """

    def __init__(self, stream: object = sys.stderr, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._is_tty = hasattr(stream, "isatty") and stream.isatty()  # type: ignore[union-attr]

    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        if self._is_tty:
            colour = _ANSI_COLOURS.get(record.levelno, _ANSI_RESET)
            record.levelname = f"{colour}{record.levelname:8s}{_ANSI_RESET}"
        return super().format(record)


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str | Path] = None,
    *,
    propagate: bool = False,
) -> logging.Logger:
    """Configure and return the ``nvidia_setup`` package logger.

    Args:
        level: Logging level name (DEBUG, INFO, WARNING, ERROR).
        log_file: Optional path to a log file.  If ``None``, logs go to
            ``stderr`` only.
        propagate: Whether to propagate messages to the root logger.

    Returns:
        Configured :class:`logging.Logger` instance for ``nvidia_setup``.
    """
    pkg_logger = logging.getLogger("nvidia_setup")
    pkg_logger.setLevel(level.upper())
    pkg_logger.propagate = propagate

    # Avoid duplicate handlers on repeated calls
    if pkg_logger.handlers:
        pkg_logger.handlers.clear()

    fmt = "%(asctime)s %(levelname)-8s %(name)s — %(message)s"
    datefmt = "%H:%M:%S"

    # Console handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(
        _ColouredFormatter(stream=sys.stderr, fmt=fmt, datefmt=datefmt)
    )
    pkg_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file is not None:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, mode="a", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
        pkg_logger.addHandler(file_handler)
        pkg_logger.debug("Logging to file: %s", path)

    return pkg_logger
