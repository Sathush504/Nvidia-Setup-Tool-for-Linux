"""Driver and CUDA installation engine.

Supports both apt-based (Ubuntu/Debian) and dnf-based (Fedora/RHEL) systems.
Accepts an optional sudo password for GUI-driven authenticated installs.
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from nvidia_setup.config import Config, load_config
from nvidia_setup.detector import SystemInfo
from nvidia_setup.exceptions import (
    IncompatibleSystemError,
    InstallationError,
    NetworkError,
    PrivilegeError,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None]


@dataclass
class InstallOptions:
    """User-selected installation options."""

    install_driver: bool = True
    install_cuda: bool = False
    cuda_env_system_wide: bool = True
    dry_run: bool = False
    skip_confirmation: bool = False


@dataclass
class InstallResult:
    """Result of a complete installation run."""

    success: bool = False
    steps_completed: list[str] = field(default_factory=list)
    steps_failed: list[str] = field(default_factory=list)
    reboot_required: bool = False
    log_lines: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def __str__(self) -> str:  # pragma: no cover
        """Return a user-friendly string representation of the installation result."""
        status = "SUCCESS" if self.success else "FAILED"
        lines = [
            f"── Installation Result: {status} ──",
            f"  Duration   : {self.duration_seconds:.1f}s",
            f"  Completed  : {', '.join(self.steps_completed) or 'none'}",
            f"  Failed     : {', '.join(self.steps_failed) or 'none'}",
            f"  Reboot req.: {'Yes' if self.reboot_required else 'No'}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Package manager detection
# ---------------------------------------------------------------------------

def _detect_pkg_manager() -> str:
    """Return 'apt', 'dnf', or 'yum' based on what's available."""
    for pm in ("apt-get", "dnf", "yum"):
        if shutil.which(pm):
            return pm.replace("-get", "")  # normalise 'apt-get' → 'apt'
    return "apt"  # default


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------


class DriverInstaller:
    """Orchestrates NVIDIA driver and CUDA toolkit installation.

    Args:
        options: :class:`InstallOptions` controlling what to install.
        config: Optional :class:`Config`; loaded from defaults/env if omitted.
        sudo_password: Optional sudo password for non-interactive GUI installs.
            When provided, commands run via ``sudo -S`` with the password piped
            to stdin instead of using ``sudo -n``.
    """

    _KEYRING_FILENAME = "cuda-keyring_1.1-1_all.deb"
    _KEYRING_BASE_URL = "https://developer.download.nvidia.com/compute/cuda/repos"

    _CODENAME_MAP = {
        "jammy": "ubuntu2204",
        "noble": "ubuntu2404",
        "bookworm": "debian12",
        "bullseye": "debian11",
        "focal": "ubuntu2004",
    }

    _APT_PREREQS = [
        "software-properties-common", "apt-transport-https",
        "ca-certificates", "curl", "wget", "gnupg",
        "lsb-release", "build-essential", "dkms",
    ]
    _DNF_PREREQS = ["curl", "wget", "dkms", "kernel-devel", "kernel-headers"]

    def __init__(
        self,
        options: InstallOptions,
        config: Config | None = None,
        sudo_password: str | None = None,
    ) -> None:
        self._options = options
        self._config = config or load_config()
        self._sudo_password = sudo_password
        self._pkg_manager = _detect_pkg_manager()
        self._last_info = SystemInfo()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def install(
        self,
        info: SystemInfo,
        progress_callback: ProgressCallback | None = None,
    ) -> InstallResult:
        """Execute the full installation workflow."""
        start = time.monotonic()
        result = InstallResult()
        cb = progress_callback or _noop_callback

        try:
            self._preflight_checks(info)
            steps = self._build_step_plan()
            total = len(steps)

            for idx, (name, fn) in enumerate(steps):
                cb(idx / total, f"Step {idx + 1}/{total}: {name}")
                logger.info("▶ %s", name)
                fn(result)
                result.steps_completed.append(name)
                cb((idx + 1) / total, f"✓ {name}")

            result.success = True
            result.reboot_required = self._options.install_driver
            cb(1.0, "Installation completed successfully.")

        except (InstallationError, NetworkError, PrivilegeError, IncompatibleSystemError):
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error during installation.")
            raise InstallationError(
                "Installation failed due to an unexpected error.", details=str(exc)
            ) from exc
        finally:
            result.duration_seconds = time.monotonic() - start
            self._cleanup()

        return result

    # ------------------------------------------------------------------
    # Step planning
    # ------------------------------------------------------------------

    def _build_step_plan(self) -> list[tuple[str, Callable[[InstallResult], None]]]:
        """Build ordered install steps based on options and package manager."""
        is_apt = self._pkg_manager == "apt"

        steps: list[tuple[str, Callable[[InstallResult], None]]] = [
            ("Update package lists", self._step_pkg_update),
            ("Install prerequisites", self._step_install_prerequisites),
        ]

        if self._options.install_driver or self._options.install_cuda:
            if is_apt:
                steps += [
                    ("Add NVIDIA repository", self._step_add_nvidia_repo_apt),
                    ("Update package lists (post-repo)", self._step_pkg_update),
                ]
            else:
                steps.append(("Add NVIDIA repository", self._step_add_nvidia_repo_dnf))

        if self._options.install_driver:
            steps.append(("Install NVIDIA driver", self._step_install_driver))

        if self._options.install_cuda:
            steps += [
                ("Install CUDA toolkit", self._step_install_cuda),
                ("Configure CUDA environment", self._step_configure_cuda_env),
            ]

        return steps

    # ------------------------------------------------------------------
    # Steps — common
    # ------------------------------------------------------------------

    def _step_pkg_update(self, _r: InstallResult) -> None:
        if self._pkg_manager == "apt":
            self._sudo("apt-get", "update", "-y")
        else:
            self._sudo(self._pkg_manager, "check-update", "--assumeyes",
                       ignore_rc=100)  # dnf returns 100 when updates are available

    def _step_install_prerequisites(self, _r: InstallResult) -> None:
        if self._pkg_manager == "apt":
            self._sudo("apt-get", "install", "-y", *self._APT_PREREQS)
        else:
            self._sudo(self._pkg_manager, "install", "-y", *self._DNF_PREREQS)

    # ------------------------------------------------------------------
    # Steps — apt (Debian/Ubuntu)
    # ------------------------------------------------------------------

    def _step_add_nvidia_repo_apt(self, _r: InstallResult) -> None:
        codename_key = self._last_info.distro_codename
        repo_seg = self._CODENAME_MAP.get(codename_key, "ubuntu2204")
        url = f"{self._KEYRING_BASE_URL}/{repo_seg}/x86_64/{self._KEYRING_FILENAME}"
        self._run_command(f"wget -q -O {self._KEYRING_FILENAME} '{url}'",
                      name="Download CUDA keyring")
        self._sudo("dpkg", "-i", self._KEYRING_FILENAME)

    # ------------------------------------------------------------------
    # Steps — dnf (Fedora/RHEL)
    # ------------------------------------------------------------------

    def _step_add_nvidia_repo_dnf(self, _r: InstallResult) -> None:
        # Add RPM Fusion free + non-free repos (provides NVIDIA drivers on Fedora)
        fedora_ver = self._last_info.distro_version
        if not fedora_ver or not fedora_ver.isdigit():
            # Fallback: query rpm directly
            rc, val = self._run_raw("rpm -E %fedora")
            fedora_ver = val.strip() if rc == 0 and val.strip().isdigit() else "40"

        self._sudo(
            self._pkg_manager, "install", "-y",
            f"https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-{fedora_ver}.noarch.rpm",
            f"https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-{fedora_ver}.noarch.rpm",
        )

    def _step_install_driver(self, _r: InstallResult) -> None:
        pkg = self._config.driver_version
        if self._pkg_manager == "apt":
            self._sudo("apt-get", "install", "-y", pkg or "cuda-drivers")
        else:
            # Fedora: akmod-nvidia is the standard DKMS-based NVIDIA driver
            self._sudo(self._pkg_manager, "install", "-y",
                       pkg or "akmod-nvidia", "xorg-x11-drv-nvidia-cuda")

    def _step_install_cuda(self, _r: InstallResult) -> None:
        if self._pkg_manager == "apt":
            self._sudo("apt-get", "install", "-y", self._config.cuda_package_name)
        else:
            # Fedora CUDA via RPM Fusion / NVIDIA repo
            self._sudo(self._pkg_manager, "install", "-y",
                       "cuda-toolkit", "cuda-libraries", "--enablerepo=rpmfusion-nonfree")

    def _step_configure_cuda_env(self, _r: InstallResult) -> None:
        env_lines = [
            "export PATH=/usr/local/cuda/bin${PATH:+:$PATH}",
            "export LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}",
        ]
        if self._options.cuda_env_system_wide:
            target = Path("/etc/profile.d/cuda.sh")
            content = "\n".join(env_lines) + "\n"
            self._run_command(
                f"echo '{content}' | sudo -S tee {target}",
                name="Write CUDA env profile",
            )
        else:
            bashrc = Path.home() / ".bashrc"
            existing = bashrc.read_text() if bashrc.exists() else ""
            additions = [ln for ln in env_lines if ln not in existing]
            if additions:
                with bashrc.open("a") as fh:
                    fh.write("\n# CUDA environment\n" + "\n".join(additions) + "\n")

    # ------------------------------------------------------------------
    # Pre-flight checks
    # ------------------------------------------------------------------

    def _preflight_checks(self, info: SystemInfo) -> None:
        self._last_info = info
        if info.is_wsl:
            raise IncompatibleSystemError(
                "Cannot install NVIDIA drivers inside WSL."
            )
        self._check_network()
        self._check_sudo()

    def _check_network(self) -> None:
        host = self._config.network_check_host
        rc, _ = self._run_raw(f"ping -c 1 {host} >/dev/null 2>&1")
        if rc != 0:
            raise NetworkError(
                "No internet connectivity detected.",
                url=f"ping://{host}",
            )

    def _check_sudo(self) -> None:
        if os.geteuid() == 0:
            return
        if not shutil.which("sudo"):
            raise PrivilegeError("sudo is not available on this system.")
        if self._sudo_password:
            # Validate supplied password
            rc, _, stderr = self._run_sudo_s(["true"])
            if rc != 0:
                raise PrivilegeError("Incorrect sudo password.", details=stderr)
        else:
            rc, _ = self._run_raw("sudo -n true 2>/dev/null")
            if rc != 0:
                raise PrivilegeError(
                    "Sudo access is required. "
                    "Enter your sudo password in the GUI or run with NOPASSWD."
                )

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    def _sudo(self, *cmd_parts: str, ignore_rc: int = -1) -> str:
        """Run a command with sudo, using password if available."""
        if self._options.dry_run:
            logger.info("[DRY-RUN] sudo %s", " ".join(cmd_parts))
            return ""

        label = " ".join(cmd_parts[:3])

        if self._sudo_password:
            rc, stdout, stderr = self._run_sudo_s(list(cmd_parts))
            if rc != 0 and rc != ignore_rc:
                raise InstallationError(
                    f"Command failed: {label}", return_code=rc, details=stderr
                )
            return stdout
        else:
            # No password — use regular sudo (NOPASSWD or cached creds)
            cmd = "sudo " + " ".join(cmd_parts)
            return self._run_command(cmd, name=label, ignore_rc=ignore_rc)

    def _run_sudo_s(self, cmd_parts: list[str]) -> tuple[int, str, str]:
        """Run a command via 'sudo -S' with piped password."""
        cmd_str = "sudo " + " ".join(cmd_parts)
        logger.debug("Running: %s", cmd_str)
        try:
            proc = subprocess.run(
                ["sudo", "-S"] + cmd_parts,
                input=(self._sudo_password or "") + "\n",
                capture_output=True,
                text=True,
                timeout=self._config.apt_timeout_seconds,
            )
            if proc.stdout:
                for line in proc.stdout.splitlines():
                    logger.debug("  stdout: %s", line)
            if proc.stderr:
                for line in proc.stderr.splitlines():
                    if "password for" not in line and "[sudo]" not in line:
                        logger.debug("  stderr: %s", line)
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            return -1, "", f"Command timed out after {self._config.apt_timeout_seconds}s: {exc}"
        except Exception as exc:  # noqa: BLE001
            return -1, "", str(exc)

    def _run_command(self, cmd: str, name: str = "", ignore_rc: int = -1) -> str:
        """Run a shell command string, raise InstallationError on failure."""
        label = name or cmd[:60]
        logger.debug("Running: %s", cmd)
        if self._options.dry_run:
            logger.info("[DRY-RUN] %s", cmd)
            return ""
        rc, stdout, stderr = self._run_raw_full(cmd)
        if rc != 0 and rc != ignore_rc:
            raise InstallationError(
                f"Step '{label}' failed.", command=cmd,
                return_code=rc, details=stderr,
            )
        return stdout

    def _run_raw(self, cmd: str) -> tuple[int, str]:
        try:
            p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                               timeout=self._config.apt_timeout_seconds)
            return p.returncode, p.stdout.strip()
        except Exception:  # noqa: BLE001
            return -1, ""

    def _run_raw_full(self, cmd: str) -> tuple[int, str, str]:
        try:
            p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                               timeout=self._config.apt_timeout_seconds)
            return p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired as exc:
            return -1, "", str(exc)
        except Exception as exc:  # noqa: BLE001
            return -1, "", str(exc)

    def _cleanup(self) -> None:
        keyring = Path(self._KEYRING_FILENAME)
        if keyring.exists():
            with contextlib.suppress(OSError):
                keyring.unlink()


def _noop_callback(_fraction: float, _message: str) -> None:
    """No-op progress callback."""
