"""Logic shared by the sync and async clients: request bodies, response parsing, retry policy."""

from __future__ import annotations

import json
import os
import random
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from ._version import __version__
from .errors import (
    APIError,
    AuthenticationError,
    CaptchaLaError,
    ConfigurationError,
    InvalidResponseError,
    NetworkError,
    RateLimitError,
)
from .results import Binding, CaptchaArgs, IssueResult, ModerationResult, ValidateResult

DEFAULT_BASE_URL = "https://verify.captcha.la"
#: Backup service that verifies ``offline_`` tokens issued during a service disruption.
DEFAULT_BACKUP_URL = "https://fallbackapiv1.captchala.com"

PREFIX_MAIN = "pt_"
PREFIX_OFFLINE = "offline_"
PREFIX_CLIENT = "client_"
PREFIX_CLIENT_WEB = "co_"
PREFIX_DEGRADED = "dg_"

#: ``error`` for a client-only token presented while the API is reachable.
ERROR_CLIENT_ONLY_REJECTED = "client_only_rejected_api_reachable"
#: ``error`` for a client-only token when ``reject_client_only`` is set.
ERROR_CLIENT_ONLY_POLICY = "client_only_rejected_by_policy"

PROBE_TIMEOUT = 2.0
REACHABLE_TTL = 30.0
UNREACHABLE_TTL = 5.0
MAX_RESPONSE_BYTES = 1 << 20
USER_AGENT = f"captchala-python/{__version__}"

_AUTH_CODES = frozenset(
    {
        "invalid_app_key",
        "invalid_app_secret",
        "invalid_secret",
        "missing_app_key",
        "missing_app_secret",
        "missing_credentials",
        "invalid_credentials",
    }
)
_RATE_CODES = frozenset({"rate_limited", "rate_limit_exceeded", "qps_exceeded", "too_many_failures"})

Hostnames = Union[str, Sequence[str]]
ModerationItem = Dict[str, Any]


def text_item(text: str) -> ModerationItem:
    """A ``{"type": "text", "text": ...}`` moderation item."""
    return {"type": "text", "text": text}


def image_url_item(url: str) -> ModerationItem:
    """A ``{"type": "image_url", "image_url": {"url": ...}}`` moderation item."""
    return {"type": "image_url", "image_url": {"url": url}}


def is_client_only_token(token: str) -> bool:
    """Whether the token is a device-minted client-only placeholder (``client_`` or ``co_``)."""
    return token.startswith(PREFIX_CLIENT) or token.startswith(PREFIX_CLIENT_WEB)


@dataclass
class RawResponse:
    status: int
    headers: Mapping[str, str]
    json: Optional[Dict[str, Any]]


def decode(status: int, headers: Mapping[str, str], body: bytes) -> RawResponse:
    data: Optional[Dict[str, Any]] = None
    if len(body) <= MAX_RESPONSE_BYTES:
        try:
            parsed = json.loads(body.decode("utf-8"))
            if isinstance(parsed, dict):
                data = parsed
        except (ValueError, UnicodeDecodeError):
            data = None
    lower = {k.lower(): v for k, v in headers.items()}
    return RawResponse(status, lower, data)


class Settings:
    """Resolved client configuration. The secret is kept out of ``repr``."""

    def __init__(
        self,
        app_key: Optional[str],
        app_secret: Optional[str],
        base_url: Optional[str],
        backup_url: Optional[str],
        timeout: float,
        max_retries: int,
        retry_backoff: float,
        reject_client_only: bool,
        headers: Optional[Mapping[str, str]],
    ) -> None:
        key = app_key if app_key is not None else os.environ.get("CAPTCHALA_APP_KEY", "")
        secret = app_secret if app_secret is not None else os.environ.get("CAPTCHALA_APP_SECRET", "")
        if not key:
            raise ConfigurationError("app_key is required (or set CAPTCHALA_APP_KEY)")
        if not secret:
            raise ConfigurationError("app_secret is required (or set CAPTCHALA_APP_SECRET)")
        self.app_key = key
        self._app_secret = secret
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.backup_url = (backup_url or DEFAULT_BACKUP_URL).rstrip("/")
        self.timeout = float(timeout)
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff = max(0.0, float(retry_backoff))
        self.reject_client_only = bool(reject_client_only)
        self.headers: Dict[str, str] = {
            **dict(headers or {}),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "X-App-Key": key,
            "X-App-Secret": secret,
        }

    def __repr__(self) -> str:
        return f"Settings(app_key={self.app_key!r}, base_url={self.base_url!r})"

    @property
    def validate_url(self) -> str:
        return f"{self.base_url}/v1/validate"

    @property
    def backup_validate_url(self) -> str:
        return f"{self.backup_url}/api/validate"

    @property
    def issue_url(self) -> str:
        return f"{self.base_url}/v1/server/challenge/issue"

    def moderation_url(self, kind: str) -> str:
        return f"{self.base_url}/v1/moderation/{kind}"

    def moderation_body(self, payload: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
        # The moderation endpoints read the credentials from the body.
        body: Dict[str, Any] = {"app_key": self.app_key, "app_secret": self._app_secret, **payload}
        if user_id:
            body["user_id"] = user_id
        return body


# ---------------------------------------------------------------- retry policy


def backoff_delay(base: float, attempt: int, retry_after: Optional[float]) -> float:
    if retry_after is not None and retry_after > 0:
        return min(retry_after, 5.0)
    delay = min(base * float(2**attempt), 2.0)
    return delay * (0.75 + random.random() * 0.5)


def retry_after_of(r: RawResponse) -> Optional[float]:
    v = (r.json or {}).get("retry_after")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    h = r.headers.get("retry-after", "").strip()
    return float(h) if h.isdigit() else None


def should_retry_status(r: RawResponse, retry_ambiguous: bool) -> bool:
    body = r.json or {}
    if body.get("retryable") is False or body.get("error") == "service_online":
        return False
    if r.status in (502, 503):
        return True
    return r.status == 504 and retry_ambiguous


def should_retry_error(e: NetworkError, attempt: int, max_retries: int, retry_ambiguous: bool) -> bool:
    return attempt < max_retries and (e.connect_failed or retry_ambiguous)


# ---------------------------------------------------------------- request bodies


def identity_body(
    body: Dict[str, Any],
    bind_uid: Optional[str],
    bind_account: Optional[str],
    bind_email: Optional[str],
    bind_phone: Optional[str],
    scene: Optional[str],
) -> None:
    for k, v in (
        ("bind_uid", bind_uid),
        ("bind_account", bind_account),
        ("bind_email", bind_email),
        ("bind_phone", bind_phone),
        ("scene", scene),
    ):
        if v:
            body[k] = v


def validate_body(
    token: str,
    *,
    client_ip: Optional[str],
    keep_token: bool,
    expected_action: Optional[str],
    expected_hostname: Optional[Hostnames],
    bind_uid: Optional[str],
    bind_account: Optional[str],
    bind_email: Optional[str],
    bind_phone: Optional[str],
    scene: Optional[str],
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"pass_token": token, "keep_token": bool(keep_token)}
    if client_ip:
        body["client_ip"] = client_ip
    if expected_action:
        body["expected_action"] = expected_action
    if expected_hostname:
        body["expected_hostname"] = (
            expected_hostname if isinstance(expected_hostname, str) else list(expected_hostname)
        )
    identity_body(body, bind_uid, bind_account, bind_email, bind_phone, scene)
    return body


def issue_body(
    action: str,
    *,
    bind_ip: Optional[str],
    ttl: Optional[int],
    max_uses: Optional[int],
    bind_device_id: Optional[str],
    bind_fingerprint: Optional[str],
    bind_uid: Optional[str],
    bind_account: Optional[str],
    bind_email: Optional[str],
    bind_phone: Optional[str],
    scene: Optional[str],
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"action": action}
    if bind_ip:
        body["bind_ip"] = bind_ip
    if ttl is not None and ttl > 0:
        body["ttl"] = int(ttl)
    if max_uses is not None and max_uses > 0:
        body["max_uses"] = int(max_uses)
    if bind_device_id:
        body["bind_device_id"] = bind_device_id
    if bind_fingerprint:
        body["bind_fingerprint"] = bind_fingerprint
    identity_body(body, bind_uid, bind_account, bind_email, bind_phone, scene)
    return body


# ---------------------------------------------------------------- parsing


def _s(v: Any) -> Optional[str]:
    return v if isinstance(v, str) else None


def _n(v: Any) -> Optional[int]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    return None


def _obj(v: Any) -> Optional[Dict[str, Any]]:
    return v if isinstance(v, dict) else None


def is_success(r: RawResponse) -> bool:
    return 200 <= r.status <= 299 and r.json is not None and r.json.get("code") == 0


def api_failure(r: RawResponse) -> Dict[str, Any]:
    """Describe a non-success response, with a typed ``cause``."""
    status = r.status
    retry_after = retry_after_of(r)
    if r.json is None:
        code = "invalid_response" if 200 <= status <= 299 else f"http_{status}"
        return {
            "error": code,
            "http_status": status,
            "retry_after": retry_after,
            "cause": InvalidResponseError(
                code, "response was not a JSON object", http_status=status, retry_after=retry_after
            ),
        }
    body = r.json
    data = _obj(body.get("data")) or {}

    def text(v: Any) -> Optional[str]:
        if isinstance(v, str) and v:
            return v
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return str(v)
        return None

    message = text(body.get("msg")) or text(body.get("message"))
    code = (
        text(data.get("error"))
        or text(body.get("error"))
        or message
        or ("unknown_error" if 200 <= status <= 299 else f"http_{status}")
    )
    retryable = body.get("retryable") if isinstance(body.get("retryable"), bool) else None
    kw = dict(http_status=status, retry_after=retry_after, retryable=retryable, body=body)
    cause: APIError
    if code in _AUTH_CODES:
        cause = AuthenticationError(code, message, **kw)  # type: ignore[arg-type]
    elif status == 429 or code in _RATE_CODES:
        cause = RateLimitError(code, message, **kw)  # type: ignore[arg-type]
    else:
        cause = APIError(code, message, **kw)  # type: ignore[arg-type]
    return {
        "error": code,
        "message": message,
        "http_status": status,
        "retry_after": retry_after,
        "retryable": retryable,
        "cause": cause,
    }


def network_failure(e: CaptchaLaError) -> Dict[str, Any]:
    return {"error": "request_failed", "cause": e}


def parse_captcha_args(v: Any) -> Optional[CaptchaArgs]:
    a = _obj(v)
    if a is None:
        return None
    return CaptchaArgs(
        platform=_s(a.get("platform")),
        user_ip=_s(a.get("user_ip")),
        referer=_s(a.get("referer")),
        pkg=_s(a.get("pkg")),
        solved_at=_n(a.get("solved_at")),
        risk_score=_n(a.get("risk_score")),
    )


def parse_validate(r: RawResponse, offline: bool, expected_action: Optional[str]) -> ValidateResult:
    data = _obj((r.json or {}).get("data"))
    if is_success(r) and data is not None:
        valid = data.get("valid")
        if valid is True or (valid is None and data.get("ok") is True):
            action = _s(data.get("action"))
            test = data.get("test") is True
            # The API enforces expected_action; this re-check is defence in depth.
            # Test keys ignore expected_action by design, so they are skipped.
            if expected_action and not test and action is not None and action != expected_action:
                return ValidateResult(
                    valid=False, offline=offline, error="action_mismatch", action=action, raw=data, http_status=r.status
                )
            args = parse_captcha_args(data.get("captcha_args"))
            b = _obj(data.get("binding"))
            m = _obj(data.get("binding_match"))
            labels = data.get("risk_labels")
            return ValidateResult(
                valid=True,
                offline=offline,
                challenge_id=_s(data.get("challenge_id")),
                action=action,
                uid=_s(data.get("uid")),
                hostname=_s(data.get("hostname")),
                challenge_ts=_s(data.get("challenge_ts")),
                risk_level=_s(data.get("risk_level")),
                risk_labels=tuple(x for x in labels if isinstance(x, str)) if isinstance(labels, list) else (),
                captcha_args=args,
                user_ip=(args.user_ip if args else None) or _s(data.get("user_ip")),
                binding=None
                if b is None
                else Binding(
                    uid=_s(b.get("uid")),
                    account=_s(b.get("account")),
                    email=_s(b.get("email")),
                    phone=_s(b.get("phone")),
                    scene=_s(b.get("scene")),
                ),
                binding_match=None if m is None else {k: v for k, v in m.items() if isinstance(v, bool)},
                test=test,
                raw=data,
                http_status=r.status,
            )
        if data.get("degraded") is True:
            return ValidateResult(
                valid=False,
                offline=offline,
                degraded=True,
                degraded_reason=_s(data.get("reason")) or "quota_exhausted",
                error=_s(data.get("error")) or "degraded",
                raw=data,
                http_status=r.status,
            )
        return ValidateResult(
            valid=False,
            offline=offline,
            error=_s(data.get("error")) or "unknown_error",
            test=data.get("test") is True,
            raw=data,
            http_status=r.status,
        )
    return ValidateResult(valid=False, offline=offline, raw=data, **api_failure(r))


def parse_issue(r: RawResponse) -> IssueResult:
    data = _obj((r.json or {}).get("data")) or {}
    token = _s(data.get("server_token"))
    if is_success(r) and token:
        return IssueResult(
            ok=True,
            token=token,
            expires_in=_n(data.get("expires_in")),
            issued_at=_n(data.get("issued_at")),
            http_status=r.status,
        )
    return IssueResult(ok=False, **api_failure(r))


def parse_moderation(r: RawResponse) -> ModerationResult:
    if is_success(r):
        d = _obj((r.json or {}).get("data")) or {}
        cats = {k: v for k, v in (_obj(d.get("categories")) or {}).items() if isinstance(v, bool)}
        scores = {
            k: float(v)
            for k, v in (_obj(d.get("category_scores")) or {}).items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        }
        return ModerationResult(
            ok=True,
            flagged=d.get("flagged") is True,
            categories=cats,
            category_scores=scores,
            content_type=_s(d.get("content_type")),
            raw=d,
            http_status=r.status,
        )
    return ModerationResult(ok=False, **api_failure(r))


# ---------------------------------------------------------------- client-only tokens


def client_only_policy_result() -> ValidateResult:
    return ValidateResult(
        valid=False,
        offline=True,
        client_only=True,
        error=ERROR_CLIENT_ONLY_POLICY,
        warning="Client-only token rejected: client-only tokens are disabled for this client",
    )


def client_only_result(main_reachable: bool, backup_reachable: Optional[bool]) -> ValidateResult:
    if main_reachable:
        return ValidateResult(
            valid=False,
            offline=True,
            client_only=True,
            error=ERROR_CLIENT_ONLY_REJECTED,
            warning="Client-only token rejected: main API is reachable",
        )
    if backup_reachable:
        return ValidateResult(
            valid=False,
            offline=True,
            client_only=True,
            error=ERROR_CLIENT_ONLY_REJECTED,
            warning="Client-only token rejected: backup API is reachable",
        )
    return ValidateResult(
        valid=True,
        offline=True,
        client_only=True,
        warning="Client-only token accepted: CaptchaLa API unreachable, token cannot be verified server-side",
    )


PROBE_BODY = {"pass_token": "", "keep_token": True}

# url -> (reachable, monotonic deadline). Shared by all clients in the process.
_probe_cache: Dict[str, Tuple[bool, float]] = {}
_probe_lock = threading.Lock()


def cached_probe(url: str) -> Optional[bool]:
    with _probe_lock:
        hit = _probe_cache.get(url)
    if hit is not None and hit[1] > time.monotonic():
        return hit[0]
    return None


def store_probe(url: str, reachable: bool) -> None:
    ttl = REACHABLE_TTL if reachable else UNREACHABLE_TTL
    with _probe_lock:
        _probe_cache[url] = (reachable, time.monotonic() + ttl)


def reset_reachability_cache() -> None:
    """Clear the shared reachability cache. Intended for tests."""
    with _probe_lock:
        _probe_cache.clear()


__all__: List[str] = []
