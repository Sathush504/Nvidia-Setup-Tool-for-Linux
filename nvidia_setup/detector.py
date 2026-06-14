"""System detection module for NVIDIA GPU, driver, and CUDA status.

This module provides the :class:`SystemDetector` class which uses standard
Linux utilities (``lspci``, ``nvidia-smi``, ``nvcc``, ``lsb_release``) to
interrogate the system state without requiring root privileges.

Example:
    >>> from nvidia_setup.detector import SystemDetector
    >>> detector = SystemDetector()
    >>> info = detector.detect()
    >>> if info.gpu_detected:
    ...     print(f"Found GPU: {info.gpu_model}")
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from nvidia_setup.exceptions import GPUNotFoundError, IncompatibleSystemError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class SystemInfo:
    """Snapshot of NVIDIA-related system state.

    Attributes:
        gpu_detected: Whether at least one NVIDIA GPU PCIe device was found.
        gpu_model: Human-readable GPU model string (e.g. ``"NVIDIA GeForce RTX 4090"``).
        gpu_count: Number of NVIDIA GPUs detected.
        driver_installed: Whether a working NVIDIA driver is loaded.
        driver_version: Driver version string (e.g. ``"535.154.05"``).
        cuda_installed: Whether the CUDA toolkit compiler (``nvcc``) is found.
        cuda_version: CUDA version string (e.g. ``"12.6"``).
        distro_id: Distribution ID (e.g. ``"ubuntu"``, ``"debian"``).
        distro_codename: Distribution codename (e.g. ``"jammy"``, ``"bookworm"``).
        distro_version: Distribution version (e.g. ``"22.04"``).
        arch: System architecture (e.g. ``"x86_64"``).
        kernel_version: Kernel release string from ``uname -r``.
        is_wsl: Whether the process is running inside WSL.
        secure_boot_enabled: Whether UEFI Secure Boot is active.
        free_disk_gb: Available disk space on ``/`` in gigabytes.
        warnings: Non-fatal advisory messages collected during detection.
    """

    gpu_detected: bool = False
    gpu_model: str = "Unknown"
    gpu_count: int = 0
    driver_installed: bool = False
    driver_version: str = "Not installed"
    cuda_installed: bool = False
    cuda_version: str = "Not installed"
    distro_id: str = "Unknown"
    distro_codename: str = "Unknown"
    distro_version: str = "Unknown"
    arch: str = "Unknown"
    kernel_version: str = "Unknown"
    is_wsl: bool = False
    secure_boot_enabled: bool = False
    free_disk_gb: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def __str__(self) -> str:  # pragma: no cover
        """Return a user-friendly string representation of system information."""
        lines = [
            "── System Information ──────────────────────────",
            f"  GPU         : {self.gpu_model} (×{self.gpu_count})"
            if self.gpu_detected
            else "  GPU         : Not detected",
            f"  Driver      : {self.driver_version}"
            if self.driver_installed
            else "  Driver      : Not installed",
            f"  CUDA        : {self.cuda_version}"
            if self.cuda_installed
            else "  CUDA        : Not installed",
            f"  Distro      : {self.distro_id} {self.distro_version} ({self.distro_codename})",
            f"  Arch        : {self.arch}",
            f"  Kernel      : {self.kernel_version}",
            f"  WSL         : {'Yes' if self.is_wsl else 'No'}",
            f"  Secure Boot : {'Enabled' if self.secure_boot_enabled else 'Disabled'}",
            f"  Free Disk   : {self.free_disk_gb:.1f} GB",
        ]
        if self.warnings:
            lines.append("  Warnings:")
            for w in self.warnings:
                lines.append(f"    ⚠  {w}")
        lines.append("─" * 48)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class SystemDetector:
    """Detects NVIDIA GPU hardware, driver, and CUDA state on Linux.

    This class is safe to instantiate multiple times.  Each call to
    :meth:`detect` performs a fresh interrogation of the system.

    Args:
        timeout: Seconds to wait for each subprocess call before giving up.

    Raises:
        IncompatibleSystemError: If the host OS is not Linux.
    """

    _SUPPORTED_DISTROS = {"jammy", "noble", "bookworm", "bullseye", "focal"}
    _SUPPORTED_DISTRO_IDS = {"ubuntu", "debian", "fedora", "arch", "archlinux"}

    def __init__(self, timeout: int = 10) -> None:
        if platform.system() != "Linux":
            raise IncompatibleSystemError(
                "nvidia_setup is supported on Linux only.",
                details=f"Detected OS: {platform.system()}",
            )
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self) -> SystemInfo:
        """Run all detection checks and return a populated :class:`SystemInfo`.

        Returns:
            Populated :class:`SystemInfo` dataclass.
        """
        info = SystemInfo()
        info.arch = platform.machine()
        info.kernel_version = platform.release()

        logger.info("Starting system detection …")

        self._detect_distro(info)
        self._detect_wsl(info)
        self._detect_gpu(info)
        self._detect_driver(info)
        self._detect_cuda(info)
        self._detect_disk(info)
        self._detect_secure_boot(info)
        self._apply_warnings(info)

        logger.info("System detection complete.")
        return info

    def assert_ready_for_install(self, info: SystemInfo | None = None) -> SystemInfo:
        """Detect system state and raise if prerequisites are not met.

        Args:
            info: Pre-populated :class:`SystemInfo`.  If ``None``, calls
                :meth:`detect` automatically.

        Returns:
            The validated :class:`SystemInfo`.

        Raises:
            IncompatibleSystemError: If running in WSL or on an unsupported
                distribution or architecture.
            GPUNotFoundError: If no NVIDIA GPU is detected.
        """
        if info is None:
            info = self.detect()

        if info.is_wsl:
            raise IncompatibleSystemError(
                "Running inside WSL. NVIDIA driver installation requires a"
                " native Linux boot (live USB or bare-metal install).",
                details="cat /proc/version contains 'Microsoft'",
            )

        if info.arch != "x86_64":
            raise IncompatibleSystemError(
                f"Unsupported architecture: {info.arch}. Only x86_64 is supported.",
            )

        if not info.gpu_detected:
            raise GPUNotFoundError(
                "No NVIDIA GPU detected via lspci. "
                "Ensure the GPU is installed and the system is not virtualised.",
            )

        return info

    # ------------------------------------------------------------------
    # Private detection helpers
    # ------------------------------------------------------------------

    def _run(self, cmd: str, shell: bool = True) -> tuple[int, str]:
        """Execute a shell command and return (returncode, stdout).

        Args:
            cmd: Command string to execute.
            shell: Whether to run via the shell (default True).

        Returns:
            Tuple of ``(returncode, stdout_stripped)``.
        """
        try:
            result = subprocess.run(
                cmd,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            return result.returncode, result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.warning("Command timed out: %s", cmd)
            return -1, ""
        except Exception as exc:  # noqa: BLE001
            logger.debug("Command error (%s): %s", cmd, exc)
            return -1, ""

    def _detect_distro(self, info: SystemInfo) -> None:
        """Populate distro fields on *info*.

        Args:
            info: SystemInfo to mutate.
        """
        # Try lsb_release first (most reliable cross-distro)
        rc, codename = self._run("lsb_release -cs 2>/dev/null")
        if rc == 0 and codename:
            info.distro_codename = codename

        rc, distro_id = self._run("lsb_release -is 2>/dev/null")
        if rc == 0 and distro_id:
            info.distro_id = distro_id.lower()

        rc, version = self._run("lsb_release -rs 2>/dev/null")
        if rc == 0 and version:
            info.distro_version = version

        # Fallback: /etc/os-release
        if info.distro_codename == "Unknown":
            os_release = Path("/etc/os-release")
            if os_release.exists():
                data = dict(
                    line.strip().split("=", 1)
                    for line in os_release.read_text().splitlines()
                    if "=" in line
                )
                info.distro_codename = data.get("VERSION_CODENAME", "Unknown").strip('"')
                info.distro_id = data.get("ID", "Unknown").lower().strip('"')
                info.distro_version = data.get("VERSION_ID", "Unknown").strip('"')

        logger.debug(
            "Distro: %s %s (%s)",
            info.distro_id,
            info.distro_version,
            info.distro_codename,
        )

    def _detect_wsl(self, info: SystemInfo) -> None:
        """Set info.is_wsl if running in Windows Subsystem for Linux.

        Args:
            info: SystemInfo to mutate.
        """
        proc_version = Path("/proc/version")
        if proc_version.exists():
            content = proc_version.read_text().lower()
            info.is_wsl = "microsoft" in content or "wsl" in content
        logger.debug("WSL: %s", info.is_wsl)

    def _detect_gpu(self, info: SystemInfo) -> None:
        """Detect NVIDIA GPU(s) via lspci.

        Args:
            info: SystemInfo to mutate.
        """
        if not shutil.which("lspci"):
            logger.warning("lspci not found; cannot detect GPU via PCI bus.")
            return

        rc, output = self._run("lspci 2>/dev/null | grep -i nvidia")
        if rc != 0 or not output:
            info.gpu_detected = False
            return

        lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
        info.gpu_count = len(lines)
        info.gpu_detected = True

        # Extract the first GPU model string (strip PCI address prefix)
        if lines:
            parts = lines[0].split(":", 2)
            info.gpu_model = parts[-1].strip() if len(parts) >= 2 else lines[0]

        logger.info("GPU detected: %s (count=%d)", info.gpu_model, info.gpu_count)

    def _detect_driver(self, info: SystemInfo) -> None:
        """Detect whether an NVIDIA kernel driver is loaded via nvidia-smi.

        Args:
            info: SystemInfo to mutate.
        """
        if not shutil.which("nvidia-smi"):
            info.driver_installed = False
            return

        rc, version = self._run(
            "nvidia-smi --query-gpu=driver_version "
            "--format=csv,noheader,nounits 2>/dev/null | head -1"
        )
        if rc == 0 and version:
            info.driver_installed = True
            info.driver_version = version
            logger.info("NVIDIA driver version: %s", version)
        else:
            info.driver_installed = False
            logger.info("NVIDIA driver not detected.")

    def _detect_cuda(self, info: SystemInfo) -> None:
        """Detect the CUDA toolkit via nvcc.

        Args:
            info: SystemInfo to mutate.
        """
        if not shutil.which("nvcc"):
            info.cuda_installed = False
            return

        rc, output = self._run(
            "nvcc --version 2>/dev/null | grep 'release' | "
            "awk '{print $6}' | cut -c2-"
        )
        if rc == 0 and output:
            info.cuda_installed = True
            info.cuda_version = output
            logger.info("CUDA version: %s", output)
        else:
            info.cuda_installed = False
            logger.info("CUDA toolkit not detected.")

    def _detect_disk(self, info: SystemInfo) -> None:
        """Populate free_disk_gb with available space on the root filesystem.

        Args:
            info: SystemInfo to mutate.
        """
        rc, output = self._run("df / --output=avail -B1 | tail -1")
        if rc == 0 and output.isdigit():
            info.free_disk_gb = int(output) / 1_073_741_824  # bytes → GiB
        logger.debug("Free disk: %.1f GB", info.free_disk_gb)

    def _detect_secure_boot(self, info: SystemInfo) -> None:
        """Check whether UEFI Secure Boot is active.

        Args:
            info: SystemInfo to mutate.
        """
        if not shutil.which("mokutil"):
            return
        rc, output = self._run("mokutil --sb-state 2>/dev/null")
        if rc == 0 and "enabled" in output.lower():
            info.secure_boot_enabled = True
            logger.debug("Secure Boot is enabled.")

    def _apply_warnings(self, info: SystemInfo) -> None:
        """Append advisory warnings to info.warnings for edge-case conditions.

        Args:
            info: SystemInfo to mutate.
        """
        if info.is_wsl:
            info.warnings.append(
                "Running in WSL. GPU pass-through may not be available."
            )
        if info.secure_boot_enabled:
            info.warnings.append(
                "Secure Boot is enabled. Third-party NVIDIA kernel modules may"
                " need to be signed (MOK enrollment)."
            )
        if (
            info.distro_codename not in self._SUPPORTED_DISTROS
            and info.distro_id not in self._SUPPORTED_DISTRO_IDS
        ):
            info.warnings.append(
                f"Distribution '{info.distro_id}' "
                f"(codename: '{info.distro_codename}') is not officially supported. "
                "Installation may fail."
            )
        if info.free_disk_gb < 5.0:
            info.warnings.append(
                f"Low disk space ({info.free_disk_gb:.1f} GB free). "
                "At least 5 GB is recommended."
            )
        if info.arch != "x86_64":
            info.warnings.append(
                f"Architecture '{info.arch}' is not x86_64. "
                "Prebuilt NVIDIA packages are only available for x86_64."
            )
