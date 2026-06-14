"""Test suite for nvidia_setup.exceptions."""

import pytest
from nvidia_setup.exceptions import (
    BuildError,
    ConfigurationError,
    GPUNotFoundError,
    IncompatibleSystemError,
    InstallationError,
    NetworkError,
    NvidiaSetupError,
    PrivilegeError,
)


class TestNvidiaSetupError:
    def test_base_message(self) -> None:
        exc = NvidiaSetupError("base error")
        assert str(exc) == "base error"
        assert exc.message == "base error"
        assert exc.details == ""

    def test_with_details(self) -> None:
        exc = NvidiaSetupError("base error", details="extra info")
        assert "extra info" in str(exc)
        assert exc.details == "extra info"

    def test_is_exception(self) -> None:
        with pytest.raises(NvidiaSetupError):
            raise NvidiaSetupError("raised")


class TestSubclasses:
    def test_gpu_not_found(self) -> None:
        exc = GPUNotFoundError("no gpu")
        assert isinstance(exc, NvidiaSetupError)
        assert "no gpu" in str(exc)

    def test_incompatible_system(self) -> None:
        exc = IncompatibleSystemError("wsl detected")
        assert isinstance(exc, NvidiaSetupError)

    def test_installation_error_attributes(self) -> None:
        exc = InstallationError("failed", command="apt-get install", return_code=1, details="err")
        assert exc.command == "apt-get install"
        assert exc.return_code == 1
        assert isinstance(exc, NvidiaSetupError)

    def test_build_error_missing_deps(self) -> None:
        exc = BuildError("missing", missing_deps=["gcc", "make"])
        assert exc.missing_deps == ["gcc", "make"]

    def test_build_error_default_deps(self) -> None:
        exc = BuildError("build failed")
        assert exc.missing_deps == []

    def test_privilege_error(self) -> None:
        exc = PrivilegeError("no sudo")
        assert isinstance(exc, NvidiaSetupError)

    def test_network_error_url(self) -> None:
        exc = NetworkError("timeout", url="https://example.com")
        assert exc.url == "https://example.com"
        assert isinstance(exc, NvidiaSetupError)

    def test_configuration_error_key(self) -> None:
        exc = ConfigurationError("missing key", key="cuda_version")
        assert exc.key == "cuda_version"
        assert isinstance(exc, NvidiaSetupError)

    def test_hierarchy_catchable_as_base(self) -> None:
        for cls in (
            GPUNotFoundError,
            IncompatibleSystemError,
            InstallationError,
            BuildError,
            PrivilegeError,
            NetworkError,
            ConfigurationError,
        ):
            with pytest.raises(NvidiaSetupError):
                raise cls("test")
