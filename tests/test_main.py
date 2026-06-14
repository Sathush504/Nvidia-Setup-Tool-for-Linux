"""Unit tests for nvidia_setup.__main__."""

import runpy
from unittest.mock import patch


def test_main_executes_gui_launch() -> None:
    """Ensure running the module directly sets up logging and calls launch."""
    with patch("nvidia_setup.logging_utils.setup_logging") as mock_setup_logging, \
         patch("nvidia_setup.gui.launch") as mock_launch:
        runpy.run_module("nvidia_setup", run_name="__main__")
        mock_setup_logging.assert_called_once_with("INFO")
        mock_launch.assert_called_once()
