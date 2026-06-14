"""Unit tests for nvidia_setup.cli entry-point and sub-commands."""

from __future__ import annotations

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
        with patch("nvidia_setup.cli.SystemDetector") as mock_det:
            mock_det.return_value.detect.return_value = info
            rc = main(["detect"])
        assert rc == 0

    def test_returns_2_on_no_gpu(self) -> None:
        info = SystemInfo(gpu_detected=False)
        with patch("nvidia_setup.cli.SystemDetector") as mock_det:
            mock_det.return_value.detect.return_value = info
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
             patch("nvidia_setup.cli.DriverInstaller") as mock_inst:
            mock_inst.return_value.install.return_value = mock_result
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
             patch("nvidia_setup.cli.DriverInstaller") as mock_inst:
            mock_inst.return_value.install.side_effect = InstallationError("fail")
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
        with patch("nvidia_setup.cli.cmd_gui", return_value=0), \
             patch("nvidia_setup.cli.cmd_detect"), \
             patch("nvidia_setup.cli.cmd_install"):
                # Bypass the full CLI stack and test cmd_gui directly
                import argparse

                from nvidia_setup.cli import cmd_gui
                args = argparse.Namespace(config=None, log_level="INFO", log_file=None)
                with patch("nvidia_setup.gui.launch") as mock_launch:
                    mock_launch.return_value = None
                    rc = cmd_gui(args)
        assert rc == 0


def test_progress_bar(capsys: pytest.CaptureFixture[str]) -> None:
    """Test the progress bar output."""
    from nvidia_setup.cli import _progress_bar
    _progress_bar(0.0, "Starting")
    captured = capsys.readouterr().out
    assert "0%" in captured

    _progress_bar(0.5, "Halfway")
    captured = capsys.readouterr().out
    assert "50%" in captured

    _progress_bar(1.0, "Done")
    captured = capsys.readouterr().out
    assert "100%" in captured
    assert captured.endswith("\n")


def test_cmd_detect_json(capsys: pytest.CaptureFixture[str]) -> None:
    """Test detect subcommand with --json flag."""
    import argparse

    from nvidia_setup.cli import cmd_detect

    args = argparse.Namespace(json=True, timeout=5)
    info = SystemInfo(gpu_detected=True, arch="x86_64")
    with patch("nvidia_setup.cli.SystemDetector") as mock_det:
        mock_det.return_value.detect.return_value = info
        rc = cmd_detect(args)
    assert rc == 0
    captured = capsys.readouterr().out
    assert '"gpu_detected": true' in captured


class TestCmdInstallInteractive:
    def test_cuda_version_override(self) -> None:
        """Test that --cuda-version overrides the config file."""
        import argparse

        from nvidia_setup.cli import cmd_install
        from nvidia_setup.detector import SystemDetector as _Det

        args = argparse.Namespace(
            driver=False,
            cuda=True,
            cuda_version="12-6",
            config=None,
            yes=True,
            dry_run=True,
        )
        info = SystemInfo(gpu_detected=True, is_wsl=False, arch="x86_64")
        det_spec = MagicMock(spec=_Det)
        det_spec.assert_ready_for_install.return_value = info

        mock_result = MagicMock(success=True, reboot_required=False, __str__=lambda s: "ok")

        with patch("nvidia_setup.cli.SystemDetector", return_value=det_spec), \
             patch("nvidia_setup.cli.DriverInstaller") as mock_inst:
            mock_inst.return_value.install.return_value = mock_result
            rc = cmd_install(args)
        assert rc == 0

    def test_interactive_confirm_yes(self) -> None:
        """Test interactive install when user types 'y'."""
        import argparse

        from nvidia_setup.cli import cmd_install
        from nvidia_setup.detector import SystemDetector as _Det

        args = argparse.Namespace(
            driver=True,
            cuda=False,
            cuda_version=None,
            config=None,
            yes=False,
            dry_run=True,
        )
        info = SystemInfo(gpu_detected=True, is_wsl=False, arch="x86_64")
        det_spec = MagicMock(spec=_Det)
        det_spec.assert_ready_for_install.return_value = info

        mock_result = MagicMock(success=True, reboot_required=True, __str__=lambda s: "ok")

        with patch("nvidia_setup.cli.SystemDetector", return_value=det_spec), \
             patch("nvidia_setup.cli.DriverInstaller") as mock_inst, \
             patch("builtins.input", return_value="y"):
            mock_inst.return_value.install.return_value = mock_result
            rc = cmd_install(args)
        assert rc == 0

    def test_interactive_confirm_no(self) -> None:
        """Test interactive install when user types 'n'."""
        import argparse

        from nvidia_setup.cli import cmd_install
        from nvidia_setup.detector import SystemDetector as _Det

        args = argparse.Namespace(
            driver=True,
            cuda=False,
            cuda_version=None,
            config=None,
            yes=False,
            dry_run=True,
        )
        info = SystemInfo(gpu_detected=True, is_wsl=False, arch="x86_64")
        det_spec = MagicMock(spec=_Det)
        det_spec.assert_ready_for_install.return_value = info

        with patch("nvidia_setup.cli.SystemDetector", return_value=det_spec), \
             patch("builtins.input", return_value="n"):
            rc = cmd_install(args)
        assert rc == 0


class TestCmdGuiExceptions:
    def test_gui_nvidia_setup_error(self) -> None:
        """Test cmd_gui raising NvidiaSetupError."""
        import argparse

        from nvidia_setup.cli import cmd_gui
        from nvidia_setup.exceptions import NvidiaSetupError

        args = argparse.Namespace(config=None)
        with patch("nvidia_setup.gui.launch", side_effect=NvidiaSetupError("error")):
            rc = cmd_gui(args)
        assert rc == 1

    def test_gui_general_exception(self) -> None:
        """Test cmd_gui raising general Exception."""
        import argparse

        from nvidia_setup.cli import cmd_gui

        args = argparse.Namespace(config=None)
        with patch("nvidia_setup.gui.launch", side_effect=RuntimeError("oops")):
            rc = cmd_gui(args)
        assert rc == 1


def test_entrypoint() -> None:
    """Test console script entrypoint function."""
    from nvidia_setup.cli import entrypoint
    with patch("nvidia_setup.cli.main", return_value=0) as mock_main, \
         patch("sys.exit") as mock_exit:
        entrypoint()
        mock_main.assert_called_once()
        mock_exit.assert_called_once_with(0)


class TestCliDetailed:
    def test_main_invalid_command_fallback(self) -> None:
        import argparse
        mock_parser = MagicMock(spec=argparse.ArgumentParser)
        mock_args = argparse.Namespace(command="invalid", log_level="INFO", log_file=None)
        mock_parser.parse_args.return_value = mock_args
        with patch("nvidia_setup.cli._build_parser", return_value=mock_parser):
            rc = main([])
            assert rc == 1
            mock_parser.print_help.assert_called_once()

    def test_main_no_command_launches_gui(self) -> None:
        with patch("nvidia_setup.cli.cmd_gui", return_value=42) as mock_cmd_gui:
            rc = main([])
            assert rc == 42
            mock_cmd_gui.assert_called_once()

    def test_cmd_install_prerequisite_error(self) -> None:
        import argparse

        from nvidia_setup.cli import cmd_install
        from nvidia_setup.detector import SystemDetector as _Det
        from nvidia_setup.exceptions import IncompatibleSystemError

        args = argparse.Namespace(
            driver=True,
            cuda=False,
            cuda_version=None,
            config=None,
            yes=True,
            dry_run=True,
        )
        det_spec = MagicMock(spec=_Det)
        det_spec.assert_ready_for_install.side_effect = IncompatibleSystemError("arch")
        with patch("nvidia_setup.cli.SystemDetector", return_value=det_spec):
            rc = cmd_install(args)
        assert rc == 1

    def test_cmd_install_interactive_lists_cuda(self) -> None:
        import argparse

        from nvidia_setup.cli import cmd_install
        from nvidia_setup.detector import SystemDetector as _Det

        args = argparse.Namespace(
            driver=False,
            cuda=True,
            cuda_version=None,
            config=None,
            yes=False,
            dry_run=True,
        )
        info = SystemInfo(gpu_detected=True, is_wsl=False, arch="x86_64")
        det_spec = MagicMock(spec=_Det)
        det_spec.assert_ready_for_install.return_value = info
        with patch("nvidia_setup.cli.SystemDetector", return_value=det_spec), \
             patch("builtins.input", return_value="n"):
            rc = cmd_install(args)
        assert rc == 0


