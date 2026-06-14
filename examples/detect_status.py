"""Example: Detecting system status programmatically.

Run from the project root:
    python examples/detect_status.py
"""

import sys
from pathlib import Path

# Allow running without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from nvidia_setup.detector import SystemDetector
from nvidia_setup.exceptions import IncompatibleSystemError
from nvidia_setup.logging_utils import setup_logging

setup_logging(level="INFO")


def main() -> None:
    """Detect and display NVIDIA hardware/software status."""
    try:
        detector = SystemDetector()
    except IncompatibleSystemError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    print("Detecting system …\n")
    info = detector.detect()
    print(info)

    # Programmatic access to fields
    if info.gpu_detected:
        print(f"✓ GPU found: {info.gpu_model} (×{info.gpu_count})")
        if info.driver_installed:
            print(f"  Driver version: {info.driver_version}")
        else:
            print("  Driver: NOT installed — run 'nvidia-setup install --driver'")
        if info.cuda_installed:
            print(f"  CUDA version: {info.cuda_version}")
        else:
            print("  CUDA: NOT installed — run 'nvidia-setup install --cuda'")
    else:
        print("✗ No NVIDIA GPU detected.")

    if info.warnings:
        print("\nWarnings:")
        for w in info.warnings:
            print(f"  ⚠  {w}")


if __name__ == "__main__":
    main()
