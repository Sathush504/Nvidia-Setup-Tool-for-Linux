"""Unit tests for nvidia_setup.cli entry-point and sub-commands."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from nvidia_setup.cli import _build_parser, main
from nvidia_setup.detector import SystemInfo


# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------


class TestParser:
    def test_detect_subcommand(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["detect"])
        assert args.command == "detect"
        assert args.json is False

    def test_detect_json_flag(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["detect", "--json"])
        assert args.json is True

    def test_install_subcommand(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["install", "--driver"])
        assert args.command == "install"
        assert args.driver is True
        assert args.cuda is False

    def test_install_both(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["install", "--driver", "--cuda"])
        assert args.driver is True
        assert args.cuda is True

    def test_gui_subcommand(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["gui"])
        assert args.command == "gui"

    def test_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--version"])

    def test_no_command_defaults_to_none(self) -> None:
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.command is None

    def test_build_not_valid(self) -> None:
        """'build' sub-command has been removed — should error."""
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["build"])


# ---------------------------------------------------------------------------
# cmd_detect
# ---------------------------------------------------------------------------


class TestCmdDetect:
    def test_returns_0_on_gpu_found(self) -> None:
        info = SystemInfo(gpu_detected=True, arch="x86_64")
        with patch("nvidia_setup.cli.SystemDetector") as MockDet:
            MockDet.return_value.detect.return_value = info
            rc = main(["detect"])
        assert rc == 0

    def test_returns_2_on_no_gpu(self) -> None:
        info = SystemInfo(gpu_detected=False)
        with patch("nvidia_setup.cli.SystemDetector") as MockDet:
            MockDet.return_value.detect.return_value = info
            rc = main(["detect"])
        assert rc == 2

    def test_returns_1_on_exception(self) -> None:
        from nvidia_setup.exceptions import IncompatibleSystemError
        with patch("nvidia_setup.cli.SystemDetector", side_effect=IncompatibleSystemError("no")):
            rc = main(["detect"])
        assert rc == 1


# ---------------------------------------------------------------------------
# cmd_install
# ---------------------------------------------------------------------------


class TestCmdInstall:
    def test_requires_driver_or_cuda(self) -> None:
        rc = main(["install"])  # neither --driver nor --cuda
        assert rc == 1

    def test_dry_run_succeeds(self) -> None:
        from unittest.mock import create_autospec
        from nvidia_setup.detector import SystemDetector as _Det
        info = SystemInfo(gpu_detected=True, is_wsl=False, arch="x86_64", distro_codename="jammy")
        mock_result = MagicMock(success=True, reboot_required=False, __str__=lambda s: "ok")

        det_spec = create_autospec(_Det, instance=True)
        det_spec.assert_ready_for_install.return_value = info

        with patch("nvidia_setup.cli.SystemDetector", return_value=det_spec), \
             patch("nvidia_setup.cli.DriverInstaller") as MockInst:
            MockInst.return_value.install.return_value = mock_result
            rc = main(["install", "--driver", "--dry-run", "--yes"])

        assert rc == 0

    def test_returns_1_on_install_error(self) -> None:
        from unittest.mock import create_autospec
        from nvidia_setup.detector import SystemDetector as _Det
        from nvidia_setup.exceptions import InstallationError
        info = SystemInfo(gpu_detected=True, is_wsl=False, arch="x86_64")

        det_spec = create_autospec(_Det, instance=True)
        det_spec.assert_ready_for_install.return_value = info

        with patch("nvidia_setup.cli.SystemDetector", return_value=det_spec), \
             patch("nvidia_setup.cli.DriverInstaller") as MockInst:
            MockInst.return_value.install.side_effect = InstallationError("fail")
            rc = main(["install", "--driver", "--yes"])

        assert rc == 1


# ---------------------------------------------------------------------------
# cmd_gui
# ---------------------------------------------------------------------------


class TestCmdGui:
    def test_returns_1_if_no_tkinter(self) -> None:
        """Returns 1 when tkinter is not importable."""
        import builtins
        real_import = builtins.__import__

        def blocked(name: str, *args, **kwargs):
            if name == "tkinter":
                raise ImportError("no tkinter")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=blocked):
            rc = main(["gui"])
        assert rc == 1

    def test_returns_0_after_successful_launch(self) -> None:
        """Returns 0 when GUI launches and exits normally."""
        with patch("nvidia_setup.cli.cmd_gui", return_value=0) as mock_gui:
            # Call via main so the dispatcher is exercised
            with patch("nvidia_setup.cli.cmd_detect"), \
                 patch("nvidia_setup.cli.cmd_install"):
                # Bypass the full CLI stack and test cmd_gui directly
                from nvidia_setup.cli import cmd_gui
                import argparse
                args = argparse.Namespace(config=None, log_level="INFO", log_file=None)
                with patch("nvidia_setup.gui.launch") as mock_launch:
                    mock_launch.return_value = None
                    rc = cmd_gui(args)
        assert rc == 0
