"""
Configuration management for the nvidia_setup library.

Supports layered configuration from:
1. Built-in defaults
2. TOML config file (~/.config/nvidia-setup/config.toml or project-local)
3. Environment variables (prefixed NVIDIA_SETUP_)
4. Programmatic overrides at runtime

Usage:
    >>> from nvidia_setup.config import load_config, Config
    >>> cfg = load_config()
    >>> print(cfg.log_level)
    'INFO'
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_XDG_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
_DEFAULT_CONFIG_DIR = _XDG_CONFIG_HOME / "nvidia-setup"
_DEFAULT_CONFIG_FILE = _DEFAULT_CONFIG_DIR / "config.toml"
_PROJECT_CONFIG_FILE = Path("nvidia-setup.toml")  # project-local override


# ---------------------------------------------------------------------------
# Dataclass configuration model
# ---------------------------------------------------------------------------


@dataclass
class Config:
    """Central configuration for the nvidia_setup library.

    All attributes can be overridden via environment variables by uppercasing
    the attribute name and prefixing with ``NVIDIA_SETUP_``.  For example,
    ``log_level`` → ``NVIDIA_SETUP_LOG_LEVEL``.

    Attributes:
        log_level: Python logging level string (DEBUG, INFO, WARNING, ERROR).
        log_file: Optional path to write log output; ``None`` logs to stderr.
        driver_version: Pinned NVIDIA driver package name; ``None`` uses the
            latest available via ``cuda-drivers``.
        cuda_version: CUDA toolkit package suffix (e.g. ``"12-6"``);
            ``None`` installs the latest stable.
        apt_timeout_seconds: Timeout in seconds for apt-get operations.
        network_check_host: Hostname/IP used for internet connectivity test.
        network_check_count: Number of ping packets to send for connectivity.
        supported_distros: Codenames of officially supported distributions.
        build_output_dir: Directory where compiled binaries are placed.
        enable_secure_boot_check: Whether to warn when Secure Boot is active.
        package_manager: Preferred Python package manager for bootstrap
            (``"pip"``, ``"poetry"``, or ``"conda"``).
        min_free_disk_gb: Minimum free disk space (GB) required before install.
    """

    log_level: str = "INFO"
    log_file: str | None = None
    driver_version: str | None = None
    cuda_version: str | None = "12-6"
    apt_timeout_seconds: int = 300
    network_check_host: str = "8.8.8.8"
    network_check_count: int = 1
    supported_distros: list[str] = field(
        default_factory=lambda: ["jammy", "noble", "bookworm"]
    )
    build_output_dir: str = "."
    enable_secure_boot_check: bool = True
    package_manager: str = "pip"
    min_free_disk_gb: float = 5.0

    # ------------------------------------------------------------------
    # Derived helpers (not serialised)
    # ------------------------------------------------------------------

    @property
    def cuda_package_name(self) -> str:
        """Return the full apt package name for the chosen CUDA version.

        Returns:
            Full apt package string, e.g. ``"cuda-toolkit-12-6"``.
        """
        version = self.cuda_version or "12-6"
        return f"cuda-toolkit-{version}"

    @property
    def log_level_int(self) -> int:
        """Return the numeric logging level corresponding to ``log_level``.

        Returns:
            Integer logging level from the ``logging`` module.

        Raises:
            ValueError: If ``log_level`` is not a recognised level name.
        """
        level = logging.getLevelName(self.log_level.upper())
        if not isinstance(level, int):
            raise ValueError(
                f"Invalid log_level '{self.log_level}'. "
                "Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL."
            )
        return level


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file and return its contents as a dict.

    Args:
        path: Filesystem path to the ``.toml`` file.

    Returns:
        Parsed key/value mapping, or an empty dict if the file is absent.

    Note:
        Uses ``tomllib`` (stdlib ≥ 3.11) or falls back to ``tomli`` on
        older interpreters.  If neither is available the file is silently
        skipped and an empty dict is returned.
    """
    if not path.exists():
        return {}

    try:
        if sys.version_info >= (3, 11):
            import tomllib  # noqa: PLC0415  # stdlib

            with path.open("rb") as fh:
                return tomllib.load(fh)  # type: ignore[arg-type]
        else:
            import tomli  # type: ignore[import]  # optional dep

            with path.open("rb") as fh:
                return tomli.load(fh)
    except ModuleNotFoundError:
        logger.debug(
            "TOML parser not available; skipping config file %s. "
            "Install 'tomli' on Python < 3.11 to enable TOML config support.",
            path,
        )
        return {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to parse config file %s: %s", path, exc)
        return {}


def _apply_env_overrides(cfg: Config) -> None:
    """Override Config fields from environment variables in place.

    Args:
        cfg: Config instance to mutate.
    """
    prefix = "NVIDIA_SETUP_"
    type_map: dict[str, type] = {
        "log_level": str,
        "log_file": str,
        "driver_version": str,
        "cuda_version": str,
        "apt_timeout_seconds": int,
        "network_check_host": str,
        "network_check_count": int,
        "build_output_dir": str,
        "enable_secure_boot_check": bool,
        "package_manager": str,
        "min_free_disk_gb": float,
    }

    for attr, cast in type_map.items():
        env_key = prefix + attr.upper()
        raw = os.environ.get(env_key)
        if raw is None:
            continue
        try:
            if cast is bool:
                value: Any = raw.lower() in {"1", "true", "yes", "on"}
            else:
                value = cast(raw)
            setattr(cfg, attr, value)
            logger.debug("Config override from env %s=%r → %r", env_key, raw, value)
        except (ValueError, TypeError) as exc:
            logger.warning(
                "Cannot apply env override %s=%r: %s", env_key, raw, exc
            )


def load_config(config_file: Path | None = None) -> Config:
    """Load and return a merged Config from defaults, file, and environment.

    Resolution order (later sources win):
    1. Hardcoded defaults in :class:`Config`.
    2. Global config file (``~/.config/nvidia-setup/config.toml``).
    3. Project-local config file (``nvidia-setup.toml`` in CWD).
    4. Explicit ``config_file`` argument.
    5. Environment variables prefixed ``NVIDIA_SETUP_``.

    Args:
        config_file: Optional explicit path to a TOML config file.

    Returns:
        Fully resolved :class:`Config` instance.
    """
    cfg = Config()  # start with defaults

    # Layer 2: global user config
    merged: dict[str, Any] = _load_toml(_DEFAULT_CONFIG_FILE)

    # Layer 3: project-local config
    merged.update(_load_toml(_PROJECT_CONFIG_FILE))

    # Layer 4: explicit path argument
    if config_file is not None:
        merged.update(_load_toml(config_file))

    # Apply TOML values
    for key, value in merged.items():
        if hasattr(cfg, key):
            setattr(cfg, key, value)
        else:
            logger.debug("Ignoring unknown config key: %s", key)

    # Layer 5: environment variables
    _apply_env_overrides(cfg)

    return cfg
