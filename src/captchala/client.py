"""Synchronous client (standard library only)."""

from __future__ import annotations

import http.client
import json
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from . import _core
from ._core import Hostnames, ModerationItem, RawResponse, Settings
from .errors import CaptchaLaError, NetworkError, RequestTimeoutError
from .results import IssueResult, ModerationResult, ValidateResult

#: A transport takes (url, body bytes, headers, timeout seconds) and returns
#: (status, headers, body bytes) for ANY HTTP response. It raises NetworkError /
#: RequestTimeoutError when no response was received.
Transport = Callable[[str, bytes, Mapping[str, str], float], Tuple[int, Mapping[str, str], bytes]]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def _is_timeout(e: BaseException) -> bool:
    return isinstance(e, (socket.timeout, TimeoutError)) or "timed out" in str(e)


def urllib_transport(
    url: str, body: bytes, headers: Mapping[str, str], timeout: float
) -> Tuple[int, Mapping[str, str], bytes]:
    """Default transport built on urllib."""
    req = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with _opener.open(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers.items()), resp.read(_core.MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as e:  # non-2xx: still an HTTP response
        try:
            data = e.read(_core.MAX_RESPONSE_BYTES + 1)
        except Exception:  # pragma: no cover
            data = b""
        return e.code, dict(e.headers.items()) if e.headers else {}, data
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, BaseException) and _is_timeout(reason):
            raise RequestTimeoutError(f"request timed out after {timeout} s") from e
        connect = isinstance(reason, (ConnectionRefusedError, socket.gaierror, OSError)) and not isinstance(
            reason, (ConnectionResetError, ssl.SSLError)
        )
        raise NetworkError(f"request failed ({reason})", connect_failed=connect) from e
    except (socket.timeout, TimeoutError) as e:
        raise RequestTimeoutError(f"request timed out after {timeout} s") from e
    except (http.client.HTTPException, ConnectionError, OSError) as e:
        raise NetworkError(f"request failed ({e.__class__.__name__})") from e


class Client:
    """CaptchaLa server-side client (synchronous, thread-safe).

    >>> captchala = Client("your_app_key", "your_app_secret")
    >>> result = captchala.validate(token, client_ip=ip, expected_action="login")
    >>> if not result.valid: ...

    Methods never raise for verification, API or network failures: check
    ``result.valid`` / ``result.error``.
    """

    def __init__(
        self,
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        backup_url: Optional[str] = None,
        timeout: float = 5.0,
        max_retries: int = 2,
        retry_backoff: float = 0.2,
        reject_client_only: bool = False,
        headers: Optional[Mapping[str, str]] = None,
        transport: Optional[Transport] = None,
    ) -> None:
        self._s = Settings(
            app_key, app_secret, base_url, backup_url, timeout, max_retries, retry_backoff, reject_client_only, headers
        )
        self._transport: Transport = transport or urllib_transport
        self._inflight: Dict[str, threading.Event] = {}
        self._inflight_lock = threading.Lock()

    def __repr__(self) -> str:
        return f"Client(app_key={self.app_key!r}, base_url={self.base_url!r})"

    @property
    def app_key(self) -> str:
        return self._s.app_key

    @property
    def base_url(self) -> str:
        return self._s.base_url

    def close(self) -> None:
        """No-op; present for symmetry with AsyncClient."""

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------ transport

    def _send(
        self,
        url: str,
        payload: Dict[str, Any],
        *,
        retry_ambiguous: bool,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> RawResponse:
        body = json.dumps(payload).encode("utf-8")
        t = self._s.timeout if timeout is None else timeout
        retries = self._s.max_retries if max_retries is None else max_retries
        attempt = 0
        while True:
            try:
                status, headers, data = self._transport(url, body, self._s.headers, t)
            except NetworkError as e:
                if not _core.should_retry_error(e, attempt, retries, retry_ambiguous):
                    raise
                time.sleep(_core.backoff_delay(self._s.retry_backoff, attempt, None))
                attempt += 1
                continue
            r = _core.decode(status, headers, data)
            if attempt < retries and _core.should_retry_status(r, retry_ambiguous):
                time.sleep(_core.backoff_delay(self._s.retry_backoff, attempt, _core.retry_after_of(r)))
                attempt += 1
                continue
            return r

    # ------------------------------------------------------------ API

    def validate(
        self,
        token: str,
        *,
        client_ip: Optional[str] = None,
        keep_token: bool = False,
        expected_action: Optional[str] = None,
        expected_hostname: Optional[Hostnames] = None,
        bind_uid: Optional[str] = None,
        bind_account: Optional[str] = None,
        bind_email: Optional[str] = None,
        bind_phone: Optional[str] = None,
        scene: Optional[str] = None,
    ) -> ValidateResult:
        """Validate a pass token from the client SDK.

        :param client_ip: End-user IP from your inbound request. Optional, recommended.
        :param keep_token: Check without consuming the token.
        :param expected_action: Reject tokens issued for another action (``action_mismatch``).
        :param expected_hostname: Hostname / package id, a string (comma-separated) or a list.
            ``*.example.com`` matches subdomains. Mismatch: ``hostname_mismatch``.
        :param bind_uid: Identity fields, compared with the identity bound at issue.
        """
        if not isinstance(token, str) or token == "":
            return ValidateResult(valid=False, error="empty_token")
        if _core.is_client_only_token(token):
            return self._validate_client_only()
        offline = token.startswith(_core.PREFIX_OFFLINE)
        url = self._s.backup_validate_url if offline else self._s.validate_url
        body = _core.validate_body(
            token,
            client_ip=client_ip,
            keep_token=keep_token,
            expected_action=expected_action,
            expected_hostname=expected_hostname,
            bind_uid=bind_uid,
            bind_account=bind_account,
            bind_email=bind_email,
            bind_phone=bind_phone,
            scene=scene,
        )
        try:
            r = self._send(url, body, retry_ambiguous=True)
        except CaptchaLaError as e:
            return ValidateResult(valid=False, offline=offline, **_core.network_failure(e))
        return _core.parse_validate(r, offline, expected_action)

    def issue_server_token(
        self,
        action: str,
        *,
        bind_ip: Optional[str] = None,
        ttl: Optional[int] = None,
        max_uses: Optional[int] = None,
        bind_uid: Optional[str] = None,
        bind_account: Optional[str] = None,
        bind_email: Optional[str] = None,
        bind_phone: Optional[str] = None,
        scene: Optional[str] = None,
        bind_device_id: Optional[str] = None,
        bind_fingerprint: Optional[str] = None,
    ) -> IssueResult:
        """Issue a one-time ``sct_`` server token. Hand it to the client SDK as ``serverToken``."""
        if not isinstance(action, str) or action == "":
            return IssueResult(ok=False, error="invalid_action", message="action is required")
        body = _core.issue_body(
            action,
            bind_ip=bind_ip,
            ttl=ttl,
            max_uses=max_uses,
            bind_device_id=bind_device_id,
            bind_fingerprint=bind_fingerprint,
            bind_uid=bind_uid,
            bind_account=bind_account,
            bind_email=bind_email,
            bind_phone=bind_phone,
            scene=scene,
        )
        try:
            r = self._send(self._s.issue_url, body, retry_ambiguous=True)
        except CaptchaLaError as e:
            return IssueResult(ok=False, **_core.network_failure(e))
        return _core.parse_issue(r)

    def moderation_check(self, input: List[ModerationItem], *, user_id: Optional[str] = None) -> ModerationResult:
        """Multi-modal content moderation. Build items with ``text_item()`` / ``image_url_item()``."""
        if not input:
            return ModerationResult(ok=False, error="empty_input", message="input is required")
        return self._moderate("check", {"input": list(input)}, user_id)

    def moderation_text(self, text: str, *, user_id: Optional[str] = None) -> ModerationResult:
        """Plain-text moderation."""
        if not text:
            return ModerationResult(ok=False, error="empty_text", message="text is required")
        return self._moderate("text", {"text": text}, user_id)

    def _moderate(self, kind: str, payload: Dict[str, Any], user_id: Optional[str]) -> ModerationResult:
        try:
            # Not retried after a timeout: the content may already be processing.
            r = self._send(
                self._s.moderation_url(kind), self._s.moderation_body(payload, user_id), retry_ambiguous=False
            )
        except CaptchaLaError as e:
            return ModerationResult(ok=False, **_core.network_failure(e))
        return _core.parse_moderation(r)

    # ------------------------------------------------------------ client-only tokens

    def _validate_client_only(self) -> ValidateResult:
        if self._s.reject_client_only:
            return _core.client_only_policy_result()
        if self._probe(self._s.validate_url):
            return _core.client_only_result(True, None)
        return _core.client_only_result(False, self._probe(self._s.backup_validate_url))

    def _probe(self, url: str) -> bool:
        """Any HTTP response within the probe timeout means reachable. Cached, single-flight per URL."""
        hit = _core.cached_probe(url)
        if hit is not None:
            return hit
        with self._inflight_lock:
            ev = self._inflight.get(url)
            leader = ev is None
            if leader:
                ev = self._inflight[url] = threading.Event()
        assert ev is not None
        if not leader:
            ev.wait(_core.PROBE_TIMEOUT + 1)
            hit = _core.cached_probe(url)
            return hit if hit is not None else False
        try:
            try:
                self._send(url, dict(_core.PROBE_BODY), retry_ambiguous=False, timeout=_core.PROBE_TIMEOUT, max_retries=0)
                reachable = True
            except CaptchaLaError:
                reachable = False
            _core.store_probe(url, reachable)
            return reachable
        finally:
            with self._inflight_lock:
                self._inflight.pop(url, None)
            ev.set()
