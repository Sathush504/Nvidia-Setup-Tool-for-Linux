"""
nvidia_setup - Python library for NVIDIA GPU Driver and CUDA toolkit management.

This package provides a programmatic interface to detect, install, and configure
NVIDIA GPU drivers and CUDA toolkit on Ubuntu/Debian Linux systems.  It is
entirely self-contained in Python (no C compilation required) and ships both a
library API and a full tkinter desktop GUI.

Example:
    >>> from nvidia_setup import SystemDetector, DriverInstaller
    >>> detector = SystemDetector()
    >>> info = detector.detect()
    >>> print(info.gpu_model)
    'NVIDIA GeForce RTX 4090'
"""

from nvidia_setup.detector import SystemDetector, SystemInfo
from nvidia_setup.installer import DriverInstaller, InstallOptions, InstallResult
from nvidia_setup.config import Config, load_config
from nvidia_setup.exceptions import (
    NvidiaSetupError,
    GPUNotFoundError,
    IncompatibleSystemError,
    InstallationError,
    PrivilegeError,
)

__version__ = "1.1.0"
__author__ = "NVIDIA Setup Tool Contributors"
__license__ = "MIT"

__all__ = [
    # Core classes
    "SystemDetector",
    "SystemInfo",
    "DriverInstaller",
    "InstallOptions",
    "InstallResult",
    # Configuration
    "Config",
    "load_config",
    # Exceptions
    "NvidiaSetupError",
    "GPUNotFoundError",
    "IncompatibleSystemError",
    "InstallationError",
    "PrivilegeError",
]
