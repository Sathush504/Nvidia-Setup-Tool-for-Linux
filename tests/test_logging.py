"""Unit tests for nvidia_setup.logging_utils."""

import logging
from pathlib import Path
from unittest.mock import MagicMock

from nvidia_setup.logging_utils import _ColouredFormatter, setup_logging


def test_coloured_formatter_tty() -> None:
    stream = MagicMock()
    stream.isatty.return_value = True
    formatter = _ColouredFormatter(stream=stream)
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="message",
        args=(),
        exc_info=None,
    )
    formatter.format(record)
    assert "\033[" in record.levelname


def test_setup_logging_with_file(tmp_path: Path) -> None:
    log_file = tmp_path / "test.log"
    logger = setup_logging(level="DEBUG", log_file=log_file)
    logger.debug("Debug test message")

    assert log_file.exists()
    content = log_file.read_text()
    assert "Debug test message" in content

    # Call setup_logging again to cover cleaning handlers
    logger2 = setup_logging(level="INFO", log_file=log_file)
    assert len(logger2.handlers) == 2  # console and file
