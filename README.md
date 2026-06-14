# NVIDIA GPU Setup Tool

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform: Linux](https://img.shields.io/badge/platform-Linux-lightgrey.svg)](https://www.kernel.org/)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

A 100% pure Python, zero-compile-dependency toolkit and GUI for detecting, installing, and configuring NVIDIA GPU drivers and the CUDA toolkit on Linux.

Compatible with **Ubuntu 20.04–24.04**, **Debian 11–12**, and **Fedora 39–44**.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Installation Options](#installation-options)
- [GUI Application](#gui-application)
- [CLI Usage](#cli-usage)
- [Python API](#python-api)
- [Configuration](#configuration)
- [Running Tests](#running-tests)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)

---

## Features

- **100% Pure Python**: Zero C compilation, no `gcc`, `make`, or GTK3 build dependencies.
- **Modern Desktop GUI**: Sleek, NVIDIA-themed dark mode interface built in `tkinter` with a multi-threaded execution queue.
- **Cross-Distribution Package Manager Support**: Automated package handling for both `apt` (Debian/Ubuntu) and `dnf` (Fedora).
- **Inline sudo Password Elevation**: Input sudo passwords directly in the GUI with secure `sudo -S` input piping.
- **Real-Time Output Log Console**: Colour-coded, scrollable terminal output console displaying detailed subprocess output.
- **Automatic GPU Detection** via `lspci` — identifies NVIDIA GPU model, Rev, and count.
- **Driver Status Verification** via `nvidia-smi` — reports installed driver versions.
- **CUDA Detection** via `nvcc` — checks current CUDA version.
- **WSL Detection & Safeguard** — blocks accidental desktop installations inside WSL environments.
- **Secure Boot & Disk Space Pre-Checks** — pre-flight verification to prevent installation failures.
- **Dry-run Mode** — preview commands and log outputs without making any changes to the system.

---

## Requirements

### System
- **OS**: Ubuntu 20.04+, Debian 11+, or Fedora 39+
- **Architecture**: x86_64 (64-bit)
- **Privileges**: Sudo access (configured via NOPASSWD or provided in GUI/prompt)

### Python Environment
- Python 3.10+
- `tkinter` library (supplied by python stdlib; on Ubuntu/Debian run `sudo apt-get install python3-tk`)

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Sathush504/Nvidia-Setup-Tool-for-Linux.git
cd Nvidia-Setup-Tool-for-Linux

# 2. Install the package in development mode
pip install -e ".[dev]"

# 3. Launch the modern desktop GUI
nvidia-setup
```

---

## Installation Options

### pip

```bash
# From PyPI (once published)
pip install nvidia-setup-tool

# Direct from GitHub repository
pip install "git+https://github.com/Sathush504/Nvidia-Setup-Tool-for-Linux.git"

# Development / Editable mode
pip install -e ".[dev]"
```

### Poetry

```bash
# Install dependencies and project
poetry install

# Run the GUI
poetry run nvidia-setup
```

---

## GUI Application

To launch the modern desktop GUI, simply execute:
```bash
nvidia-setup
```
Alternatively, you can run the GUI package directly:
```bash
python -m nvidia_setup
```

### GUI Features:
- **System Status Cards**: Real-time visual status dots (Green = Installed, Yellow = Not Installed, Red = Error) for GPUs, Drivers, and CUDA.
- **Configure Installation Options**: Interactively select Driver and/or CUDA Toolkit with checkboxes.
- **Authentication Box**: Secure password field to authenticate sudo commands without leaving the GUI.
- **Live Output Log Console**: Prints execution status, warnings, and subprocess logs in real-time.

---

## CLI Usage

For programmatic use and CLI-only environments, the tool provides specific commands:

```
usage: nvidia-setup [-h] [--version] [--log-level {DEBUG,INFO,WARNING,ERROR}]
                    [--log-file PATH] [--config PATH]
                    {detect,install,gui} ...
```

### `detect` — Show system status

```bash
# Human-readable output
nvidia-setup detect

# Machine-readable JSON output
nvidia-setup detect --json
```

**Sample output:**
```
── System Information ──────────────────────────
  GPU         : NVIDIA Corporation GB207M [GeForce RTX 5050 Max-Q] (×2)
  Driver      : 595.80
  CUDA        : Not installed
  Distro      : fedora 44 (n/a)
  Arch        : x86_64
  Kernel      : 7.0.12-200.fc44.x86_64
  WSL         : No
  Secure Boot : Disabled
  Free Disk   : 23.2 GB
────────────────────────────────────────────────
```

### `install` — Install Driver and/or CUDA via CLI

```bash
# Install driver only (interactive)
nvidia-setup install --driver

# Install CUDA toolkit only
nvidia-setup install --cuda

# Install both (non-interactive, skip confirmation)
nvidia-setup install --driver --cuda --yes

# Dry-run — preview commands without executing
nvidia-setup install --driver --cuda --dry-run
```

---

## Python API

You can import the core detection and installation modules in your own Python projects:

```python
from nvidia_setup import SystemDetector, DriverInstaller, InstallOptions

# --- System Detection ---
detector = SystemDetector()
info = detector.detect()

print(f"GPU: {info.gpu_model}")
print(f"Driver version: {info.driver_version}")
print(f"CUDA version: {info.cuda_version}")

# --- Validate before installing ---
try:
    info = detector.assert_ready_for_install()
except Exception as e:
    print(f"System not ready: {e}")

# --- Trigger Installation ---
options = InstallOptions(
    install_driver=True,
    install_cuda=True,
    dry_run=False,
)

def on_progress(fraction: float, message: str) -> None:
    print(f"[{int(fraction*100):3d}%] {message}")

installer = DriverInstaller(options, sudo_password="your_secure_password")
result = installer.install(info, progress_callback=on_progress)

print(f"Success: {result.success}")
print(f"Reboot required: {result.reboot_required}")
```

---

## Configuration

### Config file (TOML)

You can customize the installer by creating a configuration file at `~/.config/nvidia-setup/config.toml` or a project-local `nvidia-setup.toml`:

```toml
# Logging
log_level = "INFO"
log_file = "/var/log/nvidia-setup.log"

# CUDA version to install
cuda_version = "12-6"

# Execution timeout in seconds
apt_timeout_seconds = 600

# Minimum free disk space before installation
min_free_disk_gb = 5.0

# Network check settings
network_check_host = "8.8.8.8"
network_check_count = 1
```

### Environment variables

All config keys can be overridden with the `NVIDIA_SETUP_` prefix:
```bash
export NVIDIA_SETUP_LOG_LEVEL=DEBUG
export NVIDIA_SETUP_CUDA_VERSION=12-6
```

---

## Running Tests

All CLI/GUI functions are covered by unit tests running on mocked shell subprocesses to ensure safety in test environments:

```bash
# Run pytest test suite
pytest

# Run tests with verbose output
pytest -v

# Run formatting and lint checks
ruff check nvidia_setup/ tests/
```

---

## Project Structure

```
Nvidia-Setup-Tool-for-Linux/
├── nvidia_setup/               # Core Python Package
│   ├── __init__.py             # Public API exports
│   ├── cli.py                  # CLI argument parsing
│   ├── detector.py             # System hardware & platform detection
│   ├── installer.py            # Cross-distro installation engine (apt & dnf)
│   ├── gui.py                  # Tkinter-based modern Dark Mode GUI
│   ├── config.py               # Config parsing (TOML & env vars)
│   ├── exceptions.py           # Custom exception classes
│   └── logging_utils.py        # Formatting terminal and file logs
├── tests/                      # Automated test suite
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_detector.py
│   ├── test_exceptions.py
│   ├── test_gui.py
│   └── test_installer.py
├── pyproject.toml              # Build backend and packaging dependencies
├── requirements.txt            # Runtime dependencies
└── README.md                   # Project documentation
```

---

## Troubleshooting

### Tkinter is not installed / Import Error
If you receive a tkinter import error when launching the GUI:
- **Ubuntu/Debian**: Run `sudo apt-get install python3-tk`
- **Fedora**: Run `sudo dnf install python3-tkinter`

### WSL / Virtual Machine Installation
Drivers cannot be installed in WSL or VM environments lacking direct GPU passthrough. Verify that the GPU is passed through or run on a bare-metal Linux installation.

### Secure Boot / Driver Blocked
If your drivers install but fail to load on system restart, Secure Boot may require signing. Enroll your MOK key using `mokutil` and enroll at BIOS startup.
