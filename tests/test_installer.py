"""Unit tests for nvidia_setup.installer.DriverInstaller."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from nvidia_setup.config import Config
from nvidia_setup.detector import SystemInfo
from nvidia_setup.exceptions import (
    IncompatibleSystemError,
    InstallationError,
    NetworkError,
    PrivilegeError,
)
from nvidia_setup.installer import DriverInstaller, InstallOptions, InstallResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_info(**kwargs: object) -> SystemInfo:
    """Return a SystemInfo that passes preflight checks."""
    defaults = dict(
        is_wsl=False,
        gpu_detected=True,
        arch="x86_64",
        distro_codename="jammy",
    )
    defaults.update(kwargs)
    return SystemInfo(**defaults)  # type: ignore[arg-type]


def _make_installer(**option_kwargs: object) -> DriverInstaller:
    opts = InstallOptions(install_driver=True, **option_kwargs)  # type: ignore[arg-type]
    cfg = Config()
    return DriverInstaller(opts, config=cfg)


# ---------------------------------------------------------------------------
# InstallResult
# ---------------------------------------------------------------------------


class TestInstallResult:
    def test_defaults(self) -> None:
        r = InstallResult()
        assert r.success is False
        assert r.steps_completed == []
        assert r.reboot_required is False

    def test_str_success(self) -> None:
        r = InstallResult(success=True, steps_completed=["Update"])
        assert "SUCCESS" in str(r)

    def test_str_failure(self) -> None:
        r = InstallResult(success=False, steps_failed=["Install"])
        assert "FAILED" in str(r)


# ---------------------------------------------------------------------------
# InstallOptions
# ---------------------------------------------------------------------------


class TestInstallOptions:
    def test_defaults(self) -> None:
        opts = InstallOptions()
        assert opts.install_driver is True
        assert opts.install_cuda is False
        assert opts.dry_run is False


# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------


class TestPreflightChecks:
    def test_raises_on_wsl(self) -> None:
        installer = _make_installer()
        info = _valid_info(is_wsl=True)
        with pytest.raises(IncompatibleSystemError, match="WSL"):
            installer._preflight_checks(info)

    def test_raises_on_no_network(self) -> None:
        installer = _make_installer()
        info = _valid_info()
        with patch.object(installer, "_run_raw", return_value=(1, "")):
            with pytest.raises(NetworkError):
                installer._preflight_checks(info)

    def test_raises_on_no_sudo(self) -> None:
        installer = _make_installer()
        info = _valid_info()

        def side_effect(cmd: str):
            if "ping" in cmd:
                return (0, "")
            if "sudo -n" in cmd:
                return (1, "")
            return (0, "")

        with patch("os.geteuid", return_value=1000), \
             patch("shutil.which", return_value="/usr/bin/sudo"), \
             patch.object(installer, "_run_raw", side_effect=side_effect):
            with pytest.raises(PrivilegeError):
                installer._preflight_checks(info)

    def test_root_skips_sudo_check(self) -> None:
        installer = _make_installer()
        info = _valid_info()
        with patch("os.geteuid", return_value=0), \
             patch.object(installer, "_run_raw", return_value=(0, "")):
            # Should not raise
            installer._preflight_checks(info)


# ---------------------------------------------------------------------------
# Step planning
# ---------------------------------------------------------------------------


class TestBuildStepPlan:
    def test_driver_only_steps(self) -> None:
        opts = InstallOptions(install_driver=True, install_cuda=False)
        installer = DriverInstaller(opts)
        steps = installer._build_step_plan()
        names = [s[0] for s in steps]
        assert any("driver" in n.lower() for n in names)
        assert not any("cuda" in n.lower() for n in names)

    def test_cuda_only_steps(self) -> None:
        opts = InstallOptions(install_driver=False, install_cuda=True)
        installer = DriverInstaller(opts)
        steps = installer._build_step_plan()
        names = [s[0] for s in steps]
        assert any("cuda" in n.lower() for n in names)
        assert not any("driver" in n.lower() for n in names)

    def test_both_steps(self) -> None:
        opts = InstallOptions(install_driver=True, install_cuda=True)
        installer = DriverInstaller(opts)
        steps = installer._build_step_plan()
        names = [s[0] for s in steps]
        assert any("driver" in n.lower() for n in names)
        assert any("cuda" in n.lower() for n in names)


# ---------------------------------------------------------------------------
# Dry-run integration
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_succeeds_without_executing(self) -> None:
        opts = InstallOptions(install_driver=True, install_cuda=False, dry_run=True)
        installer = DriverInstaller(opts)
        info = _valid_info()

        # Patch preflight to avoid network/sudo calls
        with patch.object(installer, "_preflight_checks"), \
             patch.object(installer, "_cleanup"):
            result = installer.install(info)

        assert result.success is True
        assert result.reboot_required is True

    def test_dry_run_records_steps(self) -> None:
        opts = InstallOptions(install_driver=True, dry_run=True)
        installer = DriverInstaller(opts)
        info = _valid_info()

        with patch.object(installer, "_preflight_checks"), \
             patch.object(installer, "_cleanup"):
            result = installer.install(info)

        assert len(result.steps_completed) > 0


# ---------------------------------------------------------------------------
# Command execution helpers
# ---------------------------------------------------------------------------


class TestRunCommand:
    def test_raises_installation_error_on_failure(self) -> None:
        opts = InstallOptions(dry_run=False)
        installer = DriverInstaller(opts)
        with patch.object(installer, "_run_raw_full", return_value=(1, "", "error text")):
            with pytest.raises(InstallationError, match="failed"):
                installer._run_command("false", name="test step")

    def test_dry_run_returns_empty(self) -> None:
        opts = InstallOptions(dry_run=True)
        installer = DriverInstaller(opts)
        result = installer._run_command("sudo apt-get install -y gcc")
        assert result == ""


# ---------------------------------------------------------------------------
# CUDA env configuration
# ---------------------------------------------------------------------------


class TestConfigureCudaEnv:
    def test_system_wide_writes_via_shell(self) -> None:
        opts = InstallOptions(install_cuda=True, cuda_env_system_wide=True)
        installer = DriverInstaller(opts)
        calls = []

        def capture(cmd: str, name: str = "") -> str:
            calls.append(cmd)
            return ""

        with patch.object(installer, "_run_command", side_effect=capture):
            installer._step_configure_cuda_env(InstallResult())

        assert any("/etc/profile.d/cuda.sh" in c for c in calls)

    def test_user_bashrc(self, tmp_path: Path) -> None:
        opts = InstallOptions(install_cuda=True, cuda_env_system_wide=False)
        installer = DriverInstaller(opts)
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text("# existing content\n")

        with patch("pathlib.Path.home", return_value=tmp_path):
            installer._step_configure_cuda_env(InstallResult())

        content = bashrc.read_text()
        assert "PATH=/usr/local/cuda/bin" in content


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    def test_removes_keyring_file(self, tmp_path: Path) -> None:
        opts = InstallOptions()
        installer = DriverInstaller(opts)
        keyring = tmp_path / installer._KEYRING_FILENAME
        keyring.touch()

        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.unlink") as mock_unlink:
            installer._cleanup()
            mock_unlink.assert_called_once()

    def test_ok_if_keyring_missing(self) -> None:
        opts = InstallOptions()
        installer = DriverInstaller(opts)
        # Should not raise
        installer._cleanup()
