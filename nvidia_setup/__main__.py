"""Allow ``python -m nvidia_setup`` to launch the GUI directly."""

from nvidia_setup.gui import launch
from nvidia_setup.logging_utils import setup_logging

if __name__ == "__main__":
    setup_logging("INFO")
    launch()
