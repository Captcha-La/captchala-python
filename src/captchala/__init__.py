"""CaptchaLa server-side SDK for Python.

>>> from captchala import Client
>>> captchala = Client("your_app_key", "your_app_secret")
>>> result = captchala.validate(token, client_ip=ip, expected_action="login")
>>> if result.valid:
...     pass  # verification passed
"""

from __future__ import annotations

from typing import Any

from ._core import (
    DEFAULT_BACKUP_URL,
    DEFAULT_BASE_URL,
    ERROR_CLIENT_ONLY_POLICY,
    ERROR_CLIENT_ONLY_REJECTED,
    PREFIX_CLIENT,
    PREFIX_CLIENT_WEB,
    PREFIX_DEGRADED,
    PREFIX_MAIN,
    PREFIX_OFFLINE,
    image_url_item,
    is_client_only_token,
    reset_reachability_cache,
    text_item,
)
from ._version import __version__
from .client import Client
from .errors import (
    APIError,
    AuthenticationError,
    CaptchaLaError,
    ConfigurationError,
    InvalidResponseError,
    NetworkError,
    RateLimitError,
    RequestTimeoutError,
    ValidationFailedError,
)
from .ip import client_ip_from_headers
from .messages import user_message
from .results import Binding, CaptchaArgs, IssueResult, ModerationResult, ValidateResult

__all__ = [
    "__version__",
    "Client",
    "AsyncClient",
    "ValidateResult",
    "IssueResult",
    "ModerationResult",
    "CaptchaArgs",
    "Binding",
    "CaptchaLaError",
    "ConfigurationError",
    "NetworkError",
    "RequestTimeoutError",
    "APIError",
    "AuthenticationError",
    "RateLimitError",
    "InvalidResponseError",
    "ValidationFailedError",
    "DEFAULT_BASE_URL",
    "DEFAULT_BACKUP_URL",
    "PREFIX_MAIN",
    "PREFIX_OFFLINE",
    "PREFIX_CLIENT",
    "PREFIX_CLIENT_WEB",
    "PREFIX_DEGRADED",
    "ERROR_CLIENT_ONLY_REJECTED",
    "ERROR_CLIENT_ONLY_POLICY",
    "text_item",
    "image_url_item",
    "is_client_only_token",
    "reset_reachability_cache",
    "client_ip_from_headers",
    "user_message",
]


def __getattr__(name: str) -> Any:
    # AsyncClient needs httpx; import it only when asked for.
    if name == "AsyncClient":
        from .aio import AsyncClient

        return AsyncClient
    raise AttributeError(f"module 'captchala' has no attribute {name!r}")
