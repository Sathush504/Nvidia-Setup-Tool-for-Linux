"""Unit tests for nvidia_setup.detector.SystemDetector and SystemInfo."""

from __future__ import annotations

import platform
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from nvidia_setup.detector import SystemDetector, SystemInfo
from nvidia_setup.exceptions import GPUNotFoundError, IncompatibleSystemError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(responses: dict[str, tuple[int, str]]):
    """Return a mock _run method that dispatches on cmd substring."""

    def _run(self_arg, cmd: str, shell: bool = True):  # noqa: ANN001
        for key, val in responses.items():
            if key in cmd:
                return val
        return (1, "")

    return _run


# ---------------------------------------------------------------------------
# SystemInfo tests
# ---------------------------------------------------------------------------


class TestSystemInfo:
    def test_defaults(self) -> None:
        info = SystemInfo()
        assert info.gpu_detected is False
        assert info.driver_installed is False
        assert info.cuda_installed is False
        assert info.warnings == []

    def test_str_no_gpu(self) -> None:
        info = SystemInfo()
        text = str(info)
        assert "Not detected" in text

    def test_str_with_gpu(self) -> None:
        info = SystemInfo(gpu_detected=True, gpu_model="RTX 4090", gpu_count=1)
        text = str(info)
        assert "RTX 4090" in text


# ---------------------------------------------------------------------------
# SystemDetector init
# ---------------------------------------------------------------------------


class TestSystemDetectorInit:
    def test_raises_on_non_linux(self) -> None:
        with patch("platform.system", return_value="Windows"):
            with pytest.raises(IncompatibleSystemError, match="Linux"):
                SystemDetector()

    def test_ok_on_linux(self) -> None:
        with patch("platform.system", return_value="Linux"):
            det = SystemDetector()
            assert det._timeout == 10


# ---------------------------------------------------------------------------
# _detect_wsl
# ---------------------------------------------------------------------------


class TestDetectWsl:
    def test_wsl_detected(self, tmp_path: Path) -> None:
        proc_version = tmp_path / "version"
        proc_version.write_text("Linux version 5.15 (microsoft-standard-WSL2)")

        with patch("platform.system", return_value="Linux"):
            det = SystemDetector()

        info = SystemInfo()
        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", return_value="microsoft"):
            det._detect_wsl(info)

        assert info.is_wsl is True

    def test_native_linux(self) -> None:
        with patch("platform.system", return_value="Linux"):
            det = SystemDetector()
        info = SystemInfo()
        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", return_value="Linux version 5.15 SMP"):
            det._detect_wsl(info)
        assert info.is_wsl is False


# ---------------------------------------------------------------------------
# _detect_gpu
# ---------------------------------------------------------------------------


class TestDetectGpu:
    def _make_detector(self) -> SystemDetector:
        with patch("platform.system", return_value="Linux"):
            return SystemDetector()

    def test_gpu_found(self) -> None:
        det = self._make_detector()
        info = SystemInfo()

        with patch("shutil.which", return_value="/usr/bin/lspci"), \
             patch.object(
                 det, "_run",
                 return_value=(0, "01:00.0 VGA compatible controller: NVIDIA Corporation GA102 [GeForce RTX 3090]"),
             ):
            det._detect_gpu(info)

        assert info.gpu_detected is True
        assert info.gpu_count == 1
        assert "NVIDIA" in info.gpu_model

    def test_no_lspci(self) -> None:
        det = self._make_detector()
        info = SystemInfo()
        with patch("shutil.which", return_value=None):
            det._detect_gpu(info)
        assert info.gpu_detected is False

    def test_no_nvidia_output(self) -> None:
        det = self._make_detector()
        info = SystemInfo()
        with patch("shutil.which", return_value="/usr/bin/lspci"), \
             patch.object(det, "_run", return_value=(1, "")):
            det._detect_gpu(info)
        assert info.gpu_detected is False

    def test_multiple_gpus(self) -> None:
        det = self._make_detector()
        info = SystemInfo()
        two_gpus = (
            "01:00.0 VGA: NVIDIA Corporation RTX 4090\n"
            "02:00.0 VGA: NVIDIA Corporation RTX 4090"
        )
        with patch("shutil.which", return_value="/usr/bin/lspci"), \
             patch.object(det, "_run", return_value=(0, two_gpus)):
            det._detect_gpu(info)
        assert info.gpu_count == 2


# ---------------------------------------------------------------------------
# _detect_driver
# ---------------------------------------------------------------------------


class TestDetectDriver:
    def _make_detector(self) -> SystemDetector:
        with patch("platform.system", return_value="Linux"):
            return SystemDetector()

    def test_driver_present(self) -> None:
        det = self._make_detector()
        info = SystemInfo()
        with patch("shutil.which", return_value="/usr/bin/nvidia-smi"), \
             patch.object(det, "_run", return_value=(0, "535.154.05")):
            det._detect_driver(info)
        assert info.driver_installed is True
        assert info.driver_version == "535.154.05"

    def test_driver_absent(self) -> None:
        det = self._make_detector()
        info = SystemInfo()
        with patch("shutil.which", return_value=None):
            det._detect_driver(info)
        assert info.driver_installed is False

    def test_nvidia_smi_fails(self) -> None:
        det = self._make_detector()
        info = SystemInfo()
        with patch("shutil.which", return_value="/usr/bin/nvidia-smi"), \
             patch.object(det, "_run", return_value=(1, "")):
            det._detect_driver(info)
        assert info.driver_installed is False


# ---------------------------------------------------------------------------
# _detect_cuda
# ---------------------------------------------------------------------------


class TestDetectCuda:
    def _make_detector(self) -> SystemDetector:
        with patch("platform.system", return_value="Linux"):
            return SystemDetector()

    def test_cuda_present(self) -> None:
        det = self._make_detector()
        info = SystemInfo()
        with patch("shutil.which", return_value="/usr/local/cuda/bin/nvcc"), \
             patch.object(det, "_run", return_value=(0, "12.6")):
            det._detect_cuda(info)
        assert info.cuda_installed is True
        assert info.cuda_version == "12.6"

    def test_cuda_absent(self) -> None:
        det = self._make_detector()
        info = SystemInfo()
        with patch("shutil.which", return_value=None):
            det._detect_cuda(info)
        assert info.cuda_installed is False


# ---------------------------------------------------------------------------
# _apply_warnings
# ---------------------------------------------------------------------------


class TestApplyWarnings:
    def _make_detector(self) -> SystemDetector:
        with patch("platform.system", return_value="Linux"):
            return SystemDetector()

    def test_wsl_warning(self) -> None:
        det = self._make_detector()
        info = SystemInfo(is_wsl=True)
        det._apply_warnings(info)
        assert any("WSL" in w for w in info.warnings)

    def test_secure_boot_warning(self) -> None:
        det = self._make_detector()
        info = SystemInfo(secure_boot_enabled=True)
        det._apply_warnings(info)
        assert any("Secure Boot" in w for w in info.warnings)

    def test_unsupported_distro_warning(self) -> None:
        det = self._make_detector()
        info = SystemInfo(distro_codename="mantic")  # not in supported set
        det._apply_warnings(info)
        assert any("not officially supported" in w for w in info.warnings)

    def test_low_disk_warning(self) -> None:
        det = self._make_detector()
        info = SystemInfo(free_disk_gb=2.0)
        det._apply_warnings(info)
        assert any("disk space" in w for w in info.warnings)

    def test_no_warnings_clean_system(self) -> None:
        det = self._make_detector()
        info = SystemInfo(
            is_wsl=False,
            secure_boot_enabled=False,
            distro_codename="jammy",
            free_disk_gb=20.0,
            arch="x86_64",
        )
        det._apply_warnings(info)
        assert info.warnings == []


# ---------------------------------------------------------------------------
# assert_ready_for_install
# ---------------------------------------------------------------------------


class TestAssertReadyForInstall:
    def _make_detector(self) -> SystemDetector:
        with patch("platform.system", return_value="Linux"):
            return SystemDetector()

    def test_raises_on_wsl(self) -> None:
        det = self._make_detector()
        info = SystemInfo(is_wsl=True, gpu_detected=True, arch="x86_64")
        with pytest.raises(IncompatibleSystemError, match="WSL"):
            det.assert_ready_for_install(info)

    def test_raises_on_no_gpu(self) -> None:
        det = self._make_detector()
        info = SystemInfo(is_wsl=False, gpu_detected=False, arch="x86_64")
        with pytest.raises(GPUNotFoundError):
            det.assert_ready_for_install(info)

    def test_raises_on_wrong_arch(self) -> None:
        det = self._make_detector()
        info = SystemInfo(is_wsl=False, gpu_detected=True, arch="aarch64")
        with pytest.raises(IncompatibleSystemError, match="aarch64"):
            det.assert_ready_for_install(info)

    def test_ok_when_ready(self) -> None:
        det = self._make_detector()
        info = SystemInfo(is_wsl=False, gpu_detected=True, arch="x86_64")
        result = det.assert_ready_for_install(info)
        assert result is info
