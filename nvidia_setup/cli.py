"""
Command-line interface for the NVIDIA Setup Tool.

Sub-commands:

  detect   — Detect GPU, driver, and CUDA status.
  install  — Install NVIDIA drivers and/or CUDA toolkit.
  gui      — Launch the Python tkinter GUI.

Usage:
    nvidia-setup detect
    nvidia-setup install --driver --cuda
    nvidia-setup gui
    nvidia-setup --help
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from nvidia_setup import __version__
from nvidia_setup.config import load_config
from nvidia_setup.detector import SystemDetector
from nvidia_setup.exceptions import NvidiaSetupError
from nvidia_setup.installer import DriverInstaller, InstallOptions
from nvidia_setup.logging_utils import setup_logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Progress display
# ---------------------------------------------------------------------------


def _progress_bar(fraction: float, message: str, width: int = 40) -> None:
    """Print an inline ASCII progress bar to stdout.

    Args:
        fraction: Completion fraction in ``[0.0, 1.0]``.
        message: Status label printed after the bar.
        width: Width of the bar in characters.
    """
    filled = int(fraction * width)
    bar = "█" * filled + "░" * (width - filled)
    pct = int(fraction * 100)
    print(f"\r  [{bar}] {pct:3d}%  {message}", end="", flush=True)
    if fraction >= 1.0:
        print()


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------


def cmd_detect(args: argparse.Namespace) -> int:
    """Run system detection and print results.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 = GPU found, 1 = error, 2 = no GPU).
    """
    try:
        detector = SystemDetector(timeout=args.timeout)
        info = detector.detect()
        print(info)

        if args.json:
            import dataclasses
            import json
            print(json.dumps(dataclasses.asdict(info), indent=2))

        return 0 if info.gpu_detected else 2
    except NvidiaSetupError as exc:
        logger.error("%s", exc)
        return 1


def cmd_install(args: argparse.Namespace) -> int:
    """Install NVIDIA driver and/or CUDA toolkit.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 = success, 1 = error).
    """
    if not args.driver and not args.cuda:
        logger.error("Select at least one of --driver / --cuda.")
        return 1

    config = load_config(Path(args.config) if args.config else None)
    if args.cuda_version:
        config.cuda_version = args.cuda_version

    options = InstallOptions(
        install_driver=args.driver,
        install_cuda=args.cuda,
        dry_run=args.dry_run,
        skip_confirmation=args.yes,
    )

    detector = SystemDetector()
    try:
        info = detector.assert_ready_for_install()
    except NvidiaSetupError as exc:
        logger.error("%s", exc)
        return 1

    print(info)

    if not args.yes:
        items = []
        if args.driver:
            items.append("NVIDIA Driver (cuda-drivers)")
        if args.cuda:
            items.append(f"CUDA Toolkit ({config.cuda_package_name})")
        print("\nThe following packages will be installed:")
        for item in items:
            print(f"  • {item}")
        answer = input("\nContinue? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print("Installation cancelled.")
            return 0

    installer = DriverInstaller(options, config=config)
    print()
    try:
        result = installer.install(info, progress_callback=_progress_bar)
    except NvidiaSetupError as exc:
        logger.error("%s", exc)
        return 1

    print(result)
    if result.reboot_required:
        print("\n⚠  A system reboot is required to activate the new driver.")
    return 0 if result.success else 1


def cmd_gui(args: argparse.Namespace) -> int:
    """Launch the Python tkinter GUI application.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 = normal exit, 1 = error).
    """
    try:
        import tkinter as tk  # noqa: F401  # validate availability
    except ImportError:
        logger.error(
            "tkinter is not available. Install it with:\n"
            "  sudo apt-get install python3-tk"
        )
        return 1

    try:
        from nvidia_setup.gui import launch
        config = load_config(Path(args.config) if args.config else None)
        launch(config=config)
        return 0
    except NvidiaSetupError as exc:
        logger.error("%s", exc)
        return 1
    except Exception as exc:  # noqa: BLE001
        logger.exception("GUI failed to start: %s", exc)
        return 1


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Construct and return the top-level argument parser.

    Returns:
        Fully configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="nvidia-setup",
        description=(
            "NVIDIA GPU Setup Tool — detect, install, and manage NVIDIA drivers"
            " and CUDA toolkit on Ubuntu/Debian Linux. Pure Python, no C required."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  nvidia-setup detect                   # Show GPU/driver/CUDA status
  nvidia-setup detect --json            # Machine-readable JSON output
  nvidia-setup install --driver         # Install NVIDIA driver
  nvidia-setup install --driver --cuda  # Install driver + CUDA
  nvidia-setup install --cuda --cuda-version 12-6
  nvidia-setup gui                      # Open the Python GUI
        """,
    )

    parser.add_argument(
        "--version", "-V", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        metavar="PATH",
        help="Optional file path for log output",
    )
    parser.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help="Path to a TOML configuration file",
    )

    subparsers = parser.add_subparsers(dest="command", required=False, title="commands")

    # -- detect ----------------------------------------------------------
    detect_p = subparsers.add_parser(
        "detect",
        help="Detect GPU, driver, and CUDA status",
        description="Interrogate the system and print NVIDIA hardware/software status.",
    )
    detect_p.add_argument("--json", action="store_true", help="Output results as JSON")
    detect_p.add_argument(
        "--timeout", type=int, default=10,
        help="Seconds to wait for each detection command (default: 10)",
    )

    # -- install ---------------------------------------------------------
    install_p = subparsers.add_parser(
        "install",
        help="Install NVIDIA driver and/or CUDA toolkit",
        description=(
            "Install NVIDIA proprietary driver and/or CUDA toolkit via apt-get."
            " Requires sudo access and an internet connection."
        ),
    )
    install_p.add_argument("--driver", action="store_true",
                           help="Install the NVIDIA proprietary driver")
    install_p.add_argument("--cuda", action="store_true",
                           help="Install the CUDA toolkit")
    install_p.add_argument(
        "--cuda-version", default=None, metavar="VER",
        help="CUDA version suffix (e.g. '12-6'). Overrides config file.",
    )
    install_p.add_argument("--dry-run", action="store_true",
                           help="Log commands without executing them")
    install_p.add_argument("-y", "--yes", action="store_true",
                           help="Skip interactive confirmation prompt")

    # -- gui -------------------------------------------------------------
    subparsers.add_parser(
        "gui",
        help="Launch the Python tkinter GUI",
        description=(
            "Open the graphical interface for interactive driver installation."
            " Requires python3-tk (sudo apt-get install python3-tk)."
        ),
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. No arguments → opens the GUI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    setup_logging(level=args.log_level, log_file=args.log_file)

    # No subcommand → launch GUI
    if not args.command:
        return cmd_gui(args)

    dispatch = {
        "detect": cmd_detect,
        "install": cmd_install,
        "gui": cmd_gui,
    }
    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


def entrypoint() -> None:
    """Setuptools console_scripts entry point wrapper."""
    sys.exit(main())


if __name__ == "__main__":
    entrypoint()
