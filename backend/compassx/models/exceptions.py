"""Platform-independent exception hierarchy.

Drivers and launchers must translate infrastructure-specific errors
(docker SDK errors, kubernetes ApiException, OSError, ...) into these
exceptions. Nothing above the driver layer may catch infra exceptions.
"""

from __future__ import annotations


class PlatformError(Exception):
    """Base class for all platform-layer errors."""


class ServiceNotFoundError(PlatformError):
    """Service Registry has no definition for the requested service/mode."""


class RuntimeProvisionError(PlatformError):
    """Provisioning a runtime failed."""


class RuntimeNotFoundError(PlatformError):
    """No runtime exists with the given runtime ID."""


class RuntimeAlreadyExistsError(PlatformError):
    """A runtime with the given runtime ID already exists."""


class DriverUnavailableError(PlatformError):
    """Requested driver is not installed/configured/reachable."""


class ResourceLimitExceededError(PlatformError):
    """Requested resources exceed quota or capacity."""


class RuntimeCreationTimeoutError(PlatformError):
    """Runtime did not become ready within the allotted time."""


class RuntimeExecutionFailedError(PlatformError):
    """A command executed inside a runtime failed."""


class LauncherError(PlatformError):
    """A platform launcher operation (up/down/restart) failed."""


class HealthCheckFailedError(PlatformError):
    """One or more platform services failed health checks."""
