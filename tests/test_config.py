"""Unit tests for nvidia_setup.config."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from nvidia_setup.config import Config, _apply_env_overrides, load_config


class TestConfig:
    def test_defaults(self) -> None:
        cfg = Config()
        assert cfg.log_level == "INFO"
        assert cfg.cuda_version == "12-6"
        assert cfg.apt_timeout_seconds == 300
        assert cfg.min_free_disk_gb == 5.0
        assert "jammy" in cfg.supported_distros

    def test_cuda_package_name(self) -> None:
        cfg = Config(cuda_version="12-6")
        assert cfg.cuda_package_name == "cuda-toolkit-12-6"

    def test_cuda_package_name_default(self) -> None:
        cfg = Config(cuda_version=None)
        assert cfg.cuda_package_name == "cuda-toolkit-12-6"

    def test_log_level_int_info(self) -> None:
        import logging
        cfg = Config(log_level="INFO")
        assert cfg.log_level_int == logging.INFO

    def test_log_level_int_debug(self) -> None:
        import logging
        cfg = Config(log_level="DEBUG")
        assert cfg.log_level_int == logging.DEBUG

    def test_log_level_int_invalid(self) -> None:
        cfg = Config(log_level="BOGUS")
        with pytest.raises(ValueError, match="Invalid log_level"):
            _ = cfg.log_level_int


class TestEnvOverrides:
    def test_string_override(self) -> None:
        cfg = Config()
        with patch.dict(os.environ, {"NVIDIA_SETUP_LOG_LEVEL": "DEBUG"}):
            _apply_env_overrides(cfg)
        assert cfg.log_level == "DEBUG"

    def test_int_override(self) -> None:
        cfg = Config()
        with patch.dict(os.environ, {"NVIDIA_SETUP_APT_TIMEOUT_SECONDS": "600"}):
            _apply_env_overrides(cfg)
        assert cfg.apt_timeout_seconds == 600

    def test_bool_override_true(self) -> None:
        cfg = Config(enable_secure_boot_check=False)
        with patch.dict(os.environ, {"NVIDIA_SETUP_ENABLE_SECURE_BOOT_CHECK": "true"}):
            _apply_env_overrides(cfg)
        assert cfg.enable_secure_boot_check is True

    def test_bool_override_false(self) -> None:
        cfg = Config(enable_secure_boot_check=True)
        with patch.dict(os.environ, {"NVIDIA_SETUP_ENABLE_SECURE_BOOT_CHECK": "0"}):
            _apply_env_overrides(cfg)
        assert cfg.enable_secure_boot_check is False

    def test_float_override(self) -> None:
        cfg = Config()
        with patch.dict(os.environ, {"NVIDIA_SETUP_MIN_FREE_DISK_GB": "10.5"}):
            _apply_env_overrides(cfg)
        assert cfg.min_free_disk_gb == pytest.approx(10.5)

    def test_unknown_env_ignored(self) -> None:
        cfg = Config()
        with patch.dict(os.environ, {"NVIDIA_SETUP_NONEXISTENT_KEY": "foo"}):
            _apply_env_overrides(cfg)  # Should not raise

    def test_invalid_int_ignored(self) -> None:
        cfg = Config()
        original = cfg.apt_timeout_seconds
        with patch.dict(os.environ, {"NVIDIA_SETUP_APT_TIMEOUT_SECONDS": "not_a_number"}):
            _apply_env_overrides(cfg)
        assert cfg.apt_timeout_seconds == original


class TestLoadConfig:
    def test_returns_config_instance(self) -> None:
        cfg = load_config()
        assert isinstance(cfg, Config)

    def test_env_applied(self) -> None:
        with patch.dict(os.environ, {"NVIDIA_SETUP_LOG_LEVEL": "WARNING"}):
            cfg = load_config()
        assert cfg.log_level == "WARNING"

    def test_nonexistent_file_ok(self) -> None:
        cfg = load_config(Path("/nonexistent/config.toml"))
        assert isinstance(cfg, Config)

    def test_explicit_toml(self, tmp_path: Path) -> None:
        toml_file = tmp_path / "cfg.toml"
        toml_file.write_text('log_level = "DEBUG"\napt_timeout_seconds = 999\n')
        try:
            import tomllib  # noqa: F401
            has_toml = True
        except ImportError:
            try:
                import tomli  # type: ignore[import]  # noqa: F401
                has_toml = True
            except ImportError:
                has_toml = False

        if not has_toml:
            pytest.skip("No TOML parser available")

        cfg = load_config(toml_file)
        assert cfg.log_level == "DEBUG"
        assert cfg.apt_timeout_seconds == 999

    def test_load_config_unknown_key(self, tmp_path: Path) -> None:
        toml_file = tmp_path / "cfg.toml"
        toml_file.write_text('unknown_key = "value"\n')
        cfg = load_config(toml_file)
        assert hasattr(cfg, "unknown_key") is False

    def test_load_config_corrupt_toml(self, tmp_path: Path) -> None:
        toml_file = tmp_path / "cfg.toml"
        toml_file.write_text('invalid = [toml\n')
        cfg = load_config(toml_file)
        assert isinstance(cfg, Config)

    def test_load_config_no_toml_parser(self, tmp_path: Path) -> None:
        toml_file = tmp_path / "cfg.toml"
        toml_file.write_text('log_level = "DEBUG"\n')
        with patch("sys.version_info", (3, 10)), \
             patch("sys.modules", {"tomllib": None, "tomli": None}):
            # This triggers ModuleNotFoundError in _load_toml
            cfg = load_config(toml_file)
            assert isinstance(cfg, Config)

    def test_load_config_tomli(self, tmp_path: Path) -> None:
        toml_file = tmp_path / "cfg.toml"
        toml_file.write_text('log_level = "DEBUG"\n')
        mock_tomli = MagicMock()
        mock_tomli.load.return_value = {"log_level": "DEBUG"}
        with patch("sys.version_info", (3, 10)), \
             patch("sys.modules", {"tomllib": None, "tomli": mock_tomli}):
            cfg = load_config(toml_file)
            assert cfg.log_level == "DEBUG"

