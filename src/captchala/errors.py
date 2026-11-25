"""Typed errors.

Client methods never raise for verification outcomes or API / network
failures: they return a result whose ``error`` field holds a short code (e.g.
``token_expired``, ``request_failed``). When the failure came from the
transport or the API, the matching exception below is attached to the result
as ``cause``, so you can branch on its type.

Exceptions are raised only for programming mistakes (``ConfigurationError``)
and by ``ValidateResult.raise_if_invalid()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # pragma: no cover
    from .results import ValidateResult


class CaptchaLaError(Exception):
    """Base class. ``code`` is a short machine-readable code."""

    def __init__(self, code: str, message: Optional[str] = None) -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


class ConfigurationError(CaptchaLaError):
    """Invalid client configuration, e.g. missing app key / secret."""

    def __init__(self, message: str) -> None:
        super().__init__("configuration_error", message)


class NetworkError(CaptchaLaError):
    """The request could not be completed (DNS failure, connection refused / reset, ...)."""

    def __init__(self, message: str, *, connect_failed: bool = False) -> None:
        super().__init__("request_failed", message)
        #: True when the connection was never established (the request did not reach the API).
        self.connect_failed = connect_failed


class RequestTimeoutError(NetworkError):
    """No answer within the configured timeout."""


class APIError(CaptchaLaError):
    """The API answered with an error envelope (``code != 0``) or a non-2xx status."""

    def __init__(
        self,
        code: str,
        message: Optional[str] = None,
        *,
        http_status: int,
        retry_after: Optional[float] = None,
        retryable: Optional[bool] = None,
        body: Any = None,
    ) -> None:
        super().__init__(code, message)
        self.http_status = http_status
        self.retry_after = retry_after
        self.retryable = retryable
        self.body = body


class AuthenticationError(APIError):
    """Wrong or missing app key / secret."""


class RateLimitError(APIError):
    """Rate limit or quota reached; check ``retry_after``."""


class InvalidResponseError(APIError):
    """The response body was not the expected JSON envelope."""


class ValidationFailedError(CaptchaLaError):
    """Raised by ``ValidateResult.raise_if_invalid()``. Carries the result."""

    def __init__(self, result: "ValidateResult") -> None:
        code = result.error or "unknown_error"
        super().__init__(code, f"CAPTCHA validation failed: {code}")
        self.result = result
        self.__cause__ = result.cause
