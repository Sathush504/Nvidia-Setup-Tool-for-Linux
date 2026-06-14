"""Custom exception hierarchy for the nvidia_setup library.

All exceptions inherit from NvidiaSetupError, making it easy to catch any
library-specific error with a single except clause.
"""


class NvidiaSetupError(Exception):
    """Base exception for all nvidia_setup errors.

    All library-specific exceptions inherit from this class, enabling
    callers to catch the entire exception hierarchy with a single clause.

    Args:
        message: Human-readable description of the error.
        details: Optional extended details or diagnostic information.
    """

    def __init__(self, message: str, details: str = "") -> None:
        self.message = message
        self.details = details
        super().__init__(message)

    def __str__(self) -> str:
        """Return a user-friendly string representation of the exception."""
        if self.details:
            return f"{self.message}\nDetails: {self.details}"
        return self.message


class GPUNotFoundError(NvidiaSetupError):
    """Raised when no NVIDIA GPU is detected in the system.

    This typically means no NVIDIA PCIe device is visible via lspci,
    which can occur on systems without an NVIDIA GPU or in virtualised
    environments that do not expose the GPU.
    """


class IncompatibleSystemError(NvidiaSetupError):
    """Raised when the host system is incompatible with this tool.

    Examples include:
    - Running inside WSL (Windows Subsystem for Linux)
    - Unsupported Linux distribution
    - Unsupported CPU architecture
    - Insufficient disk space
    """


class InstallationError(NvidiaSetupError):
    """Raised when a driver or CUDA installation step fails.

    Args:
        message: High-level description of the failure.
        command: The shell command that failed, if applicable.
        return_code: The non-zero exit code from the failed command.
        details: Captured stderr/stdout for diagnostics.
    """

    def __init__(
        self,
        message: str,
        command: str = "",
        return_code: int = -1,
        details: str = "",
    ) -> None:
        self.command = command
        self.return_code = return_code
        super().__init__(message, details)


class BuildError(NvidiaSetupError):
    """Raised when compilation of the native GTK3 application fails.

    Args:
        message: Description of the build failure.
        missing_deps: List of missing build dependencies.
        details: Compiler output or error log.
    """

    def __init__(
        self,
        message: str,
        missing_deps: list[str] | None = None,
        details: str = "",
    ) -> None:
        self.missing_deps = missing_deps or []
        super().__init__(message, details)


class PrivilegeError(NvidiaSetupError):
    """Raised when the operation requires elevated privileges that are unavailable.

    This can occur when sudo access is denied, the password is incorrect,
    or the process does not have the required capabilities.
    """


class NetworkError(NvidiaSetupError):
    """Raised when a network operation fails (e.g., downloading packages).

    Args:
        message: Description of the network failure.
        url: The URL that was being accessed, if applicable.
    """

    def __init__(self, message: str, url: str = "", details: str = "") -> None:
        self.url = url
        super().__init__(message, details)


class ConfigurationError(NvidiaSetupError):
    """Raised when configuration is invalid or missing required values.

    Args:
        message: Description of the configuration problem.
        key: The configuration key that is missing or invalid.
    """

    def __init__(self, message: str, key: str = "", details: str = "") -> None:
        self.key = key
        super().__init__(message, details)
