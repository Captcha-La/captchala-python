"""Result types returned by the clients."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .errors import CaptchaLaError, ValidationFailedError


@dataclass(frozen=True)
class CaptchaArgs:
    """Solve-time context echoed by validate. Informational only: never gate pass/fail on it."""

    platform: Optional[str] = None
    """``web`` / ``android`` / ``ios`` / ``flutter`` / ``windows`` / ..."""
    user_ip: Optional[str] = None
    """End-user IP recorded when the challenge was solved."""
    referer: Optional[str] = None
    """Page URL the challenge was solved on (web)."""
    pkg: Optional[str] = None
    """App package / bundle id (native)."""
    solved_at: Optional[int] = None
    """Solve completion time, unix seconds."""
    risk_score: Optional[int] = None
    """Solve-time risk score, 0-100 (higher = riskier)."""


@dataclass(frozen=True)
class Binding:
    """Identity bound when the server token was issued (``None`` for fields not bound)."""

    uid: Optional[str] = None
    account: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    scene: Optional[str] = None


@dataclass(frozen=True)
class ValidateResult:
    """Result of ``validate()``. ``valid`` is the only field to gate on."""

    valid: bool
    error: Optional[str] = None
    """Error code when ``valid`` is False, e.g. ``token_expired``, ``action_mismatch``, ``request_failed``."""
    message: Optional[str] = None
    """Human-readable message from the API, for API-level errors."""
    warning: Optional[str] = None
    offline: bool = False
    """True for ``offline_`` tokens (backup service) and client-only tokens."""
    client_only: bool = False
    """True for device-minted ``client_`` / ``co_`` tokens, which cannot be verified server-side."""
    degraded: bool = False
    """``dg_`` token issued while the quota is exhausted. ``valid`` is always False; your decision."""
    degraded_reason: Optional[str] = None
    challenge_id: Optional[str] = None
    action: Optional[str] = None
    uid: Optional[str] = None
    """User ID bound via ``bind_uid`` at issue."""
    hostname: Optional[str] = None
    """Hostname (web) or package / bundle id (native) where the challenge was solved."""
    challenge_ts: Optional[str] = None
    """Solve time, ISO 8601 UTC."""
    risk_level: Optional[str] = None
    """``low`` / ``medium`` / ``high`` / ``critical``. Informational."""
    risk_labels: Tuple[str, ...] = ()
    """Coarse risk categories. Informational; new values may appear."""
    captcha_args: Optional[CaptchaArgs] = None
    user_ip: Optional[str] = None
    binding: Optional[Binding] = None
    binding_match: Optional[Dict[str, bool]] = None
    test: bool = False
    """True when the answer came from a public test key. Reject it in production."""
    http_status: Optional[int] = None
    retry_after: Optional[float] = None
    retryable: Optional[bool] = None
    cause: Optional[CaptchaLaError] = field(default=None, compare=False)
    """Typed error for API / network failures (None for plain verification failures)."""
    raw: Optional[Dict[str, Any]] = field(default=None, compare=False, repr=False)
    """The raw ``data`` object of the response."""

    @property
    def binding_mismatch(self) -> bool:
        """True when any ``binding_match`` field is False (token issued for another identity).

        A mismatch does not make ``valid`` False on its own; reject it yourself if it matters.
        """
        return bool(self.binding_match) and any(v is False for v in self.binding_match.values())  # type: ignore[union-attr]

    def raise_if_invalid(self) -> "ValidateResult":
        """Raise ``ValidationFailedError`` unless ``valid``. Returns self."""
        if not self.valid:
            raise ValidationFailedError(self)
        return self

    def to_dict(self) -> Dict[str, Any]:
        args = self.captcha_args
        return {
            "valid": self.valid,
            "error": self.error,
            "warning": self.warning,
            "offline": self.offline,
            "client_only": self.client_only,
            "degraded": self.degraded,
            "degraded_reason": self.degraded_reason,
            "challenge_id": self.challenge_id,
            "action": self.action,
            "uid": self.uid,
            "hostname": self.hostname,
            "challenge_ts": self.challenge_ts,
            "risk_level": self.risk_level,
            "risk_labels": list(self.risk_labels),
            "user_ip": self.user_ip,
            "captcha_args": None if args is None else args.__dict__.copy(),
            "binding": None if self.binding is None else self.binding.__dict__.copy(),
            "binding_match": self.binding_match,
            "test": self.test,
        }


@dataclass(frozen=True)
class IssueResult:
    """Result of ``issue_server_token()``."""

    ok: bool
    token: Optional[str] = None
    """The ``sct_`` server token. Hand it to the client SDK as ``serverToken``."""
    expires_in: Optional[int] = None
    issued_at: Optional[int] = None
    error: Optional[str] = None
    message: Optional[str] = None
    http_status: Optional[int] = None
    retry_after: Optional[float] = None
    retryable: Optional[bool] = None
    cause: Optional[CaptchaLaError] = field(default=None, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "token": self.token,
            "expires_in": self.expires_in,
            "issued_at": self.issued_at,
            "error": self.error,
            "message": self.message,
        }


@dataclass(frozen=True)
class ModerationResult:
    """Result of ``moderation_check()`` / ``moderation_text()``."""

    ok: bool
    flagged: bool = False
    categories: Dict[str, bool] = field(default_factory=dict)
    """Category -> tripped. The set depends on the model; iterate defensively."""
    category_scores: Dict[str, float] = field(default_factory=dict)
    content_type: Optional[str] = None
    raw: Optional[Dict[str, Any]] = field(default=None, repr=False)
    error: Optional[str] = None
    message: Optional[str] = None
    http_status: Optional[int] = None
    retry_after: Optional[float] = None
    retryable: Optional[bool] = None
    cause: Optional[CaptchaLaError] = field(default=None, compare=False)

    def has_category(self, *names: str) -> bool:
        """True if any of the named categories tripped."""
        return any(self.categories.get(n) is True for n in names)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "flagged": self.flagged,
            "categories": self.categories,
            "category_scores": self.category_scores,
            "content_type": self.content_type,
            "error": self.error,
            "message": self.message,
            "raw": self.raw,
        }


__all__: List[str] = ["CaptchaArgs", "Binding", "ValidateResult", "IssueResult", "ModerationResult"]
