"""
Example: Headless/automated driver installation.

Demonstrates how to use DriverInstaller in a non-interactive script
(e.g. in a CI/CD pipeline or provisioning script).

Run from the project root (requires sudo and a real NVIDIA GPU):
    python examples/headless_install.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from nvidia_setup.config import Config
from nvidia_setup.detector import SystemDetector
from nvidia_setup.exceptions import NvidiaSetupError
from nvidia_setup.installer import DriverInstaller, InstallOptions
from nvidia_setup.logging_utils import setup_logging

setup_logging(level="DEBUG")


def progress(fraction: float, message: str) -> None:
    """Simple progress printer."""
    bar_len = 30
    filled = int(fraction * bar_len)
    bar = "=" * filled + "-" * (bar_len - filled)
    print(f"\r[{bar}] {int(fraction*100):3d}%  {message}", end="", flush=True)
    if fraction >= 1.0:
        print()


def main() -> None:
    """Run automated driver-only installation (dry-run by default)."""
    # In production, set dry_run=False and ensure the user has sudo
    options = InstallOptions(
        install_driver=True,
        install_cuda=False,
        dry_run=True,       # ← change to False for actual install
        skip_confirmation=True,
    )

    config = Config(
        cuda_version="12-6",
        apt_timeout_seconds=600,
        network_check_host="8.8.8.8",
    )

    try:
        detector = SystemDetector()
        info = detector.assert_ready_for_install()
        print(info)

        installer = DriverInstaller(options, config=config)
        result = installer.install(info, progress_callback=progress)

        print(result)
        if result.reboot_required:
            print("\n⚠  Reboot required to activate driver.")
        sys.exit(0 if result.success else 1)

    except NvidiaSetupError as exc:
        print(f"\n✗ {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
