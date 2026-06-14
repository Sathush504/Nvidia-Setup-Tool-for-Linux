# NVIDIA GPU Setup Tool for Linux

An utility for detecting, installing, and configuring NVIDIA GPU drivers and the CUDA toolkit on Linux. This tool provides both a graphical user interface (GUI) and a command-line interface (CLI) to assist with setup.

> **Implementation Note:** This application was originally implemented in C. It has since been rewritten entirely in Python to eliminate compilation requirements, remove build toolchain dependencies (such as `gcc` or `make`), and improve overall maintainability.

---

## Features

- **System Detection:** Identifies NVIDIA GPU models, current driver versions, and CUDA installations using system utilities (`lspci`, `nvidia-smi`, and `nvcc`).
- **Pre-flight Validation:** Checks for WSL environments, Secure Boot status, system architecture, minimum disk space, and network connectivity before attempting installation.
- **Cross-Distribution Support:** Handles package installation for both `apt` (Debian/Ubuntu) and `dnf` (Fedora).
- **GUI and CLI Interfaces:** Includes a graphical application built with `tkinter` and a standard terminal interface.
- **Privilege Elevation:** Prompts for sudo passwords via a GUI dialog when run in graphical mode, using standard piped input to authenticate subprocess actions.
- **Real-Time Logging:** Outputs command execution progress and subprocess output to a log console or CLI progress bar.
- **Dry-run Mode:** Allows simulating the installation steps to preview executed commands without modifying the system.

---

## Requirements

### Supported Operating Systems
- Ubuntu 20.04 or newer
- Debian 11 or newer
- Fedora 39 or newer
- System Architecture: `x86_64`

### Dependencies
- Python 3.10 or newer
- `tkinter` (on Ubuntu/Debian, install with `sudo apt-get install python3-tk`; on Fedora, install with `sudo dnf install python3-tkinter`)

---

## Installation

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/Sathush504/Nvidia-Setup-Tool-for-Linux.git
   cd Nvidia-Setup-Tool-for-Linux
   ```

2. Install the package in editable mode with development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

### Using Poetry

If you prefer Poetry for dependency management:
```bash
poetry install
```

---

## Usage

### Graphical Interface

To launch the GUI:
```bash
nvidia-setup
```
Or run the module directly:
```bash
python -m nvidia_setup
```

The GUI allows you to inspect the detected GPU/driver/CUDA status, select components to install (Driver and/or CUDA Toolkit), enter your sudo password securely, and monitor the installation logs.

### Command-Line Interface

The CLI offers subcommands for automated or headless environments:

```bash
# Display general help
nvidia-setup --help

# Detect system hardware and driver status
nvidia-setup detect

# Detect system and export status as JSON
nvidia-setup detect --json

# Install the NVIDIA driver (interactive confirmation)
nvidia-setup install --driver

# Install both driver and CUDA toolkit without interactive prompts
nvidia-setup install --driver --cuda --yes

# Perform a dry-run simulation of the installation
nvidia-setup install --driver --cuda --dry-run
```

---

## Configuration

You can customize runtime defaults using a TOML configuration file located at `~/.config/nvidia-setup/config.toml` or a project-local `nvidia-setup.toml`.

### Example Configuration

```toml
# Logging settings
log_level = "INFO"
log_file = "/var/log/nvidia-setup.log"

# Target CUDA package suffix
cuda_version = "12-6"

# Package manager timeout in seconds
apt_timeout_seconds = 600

# Minimum free disk space threshold (in GB)
min_free_disk_gb = 5.0

# Network reachability check settings
network_check_host = "8.8.8.8"
```

### Environment Overrides

Any configuration parameter can be overridden using environment variables prefixed with `NVIDIA_SETUP_`:
```bash
export NVIDIA_SETUP_LOG_LEVEL=DEBUG
export NVIDIA_SETUP_CUDA_VERSION=12-6
```

---

## Development and Testing

The test suite runs on mocked subprocesses and does not perform active package modifications on your system.

```bash
# Run all unit tests
pytest

# Run tests with verbose output
pytest -v

# Run lint and style checks
ruff check
```

---

## Troubleshooting

### Tkinter Import Errors
If the graphical application fails to start with a `tkinter` import error:
- **Debian/Ubuntu:** `sudo apt-get install python3-tk`
- **Fedora:** `sudo dnf install python3-tkinter`

### WSL / Virtual Environments
This utility is designed for bare-metal installations. Direct driver installation is blocked inside WSL because WSL utilizes GPU virtualization rather than standard driver packages.

### Secure Boot Issues
If drivers install successfully but do not load after reboot, check your Secure Boot status. You may need to enroll the Machine Owner Key (MOK) using `mokutil` so the kernel can load the third-party NVIDIA modules.

---

## Changelog

### Version 2.0.0
- **Implementation Overhaul:** Rewrote the entire application from C to pure Python to remove compiler and local build dependencies.
- **GUI Improvement:** Switched graphical interface implementation to standard Python Tkinter.
- **Improved Password Prompting:** Re-implemented secure inline elevation checks to prevent incorrect sudo password reporting.
- **Full Test Suite:** Added comprehensive unit and integration tests covering the CLI and GUI packages.

