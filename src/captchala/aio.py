"""Asynchronous client. Requires httpx: ``pip install "captchala[async]"``."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Mapping, Optional, Tuple

try:
    import httpx
except ImportError as e:  # pragma: no cover
    raise ImportError('captchala.AsyncClient requires httpx: pip install "captchala[async]"') from e

from . import _core
from ._core import Hostnames, ModerationItem, RawResponse, Settings
from .errors import CaptchaLaError, NetworkError, RequestTimeoutError
from .results import IssueResult, ModerationResult, ValidateResult

# (event loop id, url) -> in-flight probe
_inflight: Dict[Tuple[int, str], "asyncio.Future[bool]"] = {}


class AsyncClient:
    """CaptchaLa server-side client for asyncio.

    >>> async with AsyncClient("your_app_key", "your_app_secret") as captchala:
    ...     result = await captchala.validate(token, client_ip=ip, expected_action="login")

    Pass your own ``httpx.AsyncClient`` as ``http_client`` to share a
    connection pool (it is then not closed by ``aclose()``).
    """

    def __init__(
        self,
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
        *,
        timeout: float = 5.0,
        max_retries: int = 2,
        retry_backoff: float = 0.2,
        reject_client_only: bool = False,
        headers: Optional[Mapping[str, str]] = None,
        http_client: Optional["httpx.AsyncClient"] = None,
    ) -> None:
        self._s = Settings(
            app_key, app_secret, timeout, max_retries, retry_backoff, reject_client_only, headers
        )
        self._own_client = http_client is None
        self._http = http_client or httpx.AsyncClient(follow_redirects=False)

    def __repr__(self) -> str:
        return f"AsyncClient(app_key={self.app_key!r})"

    @property
    def app_key(self) -> str:
        return self._s.app_key

    async def aclose(self) -> None:
        if self._own_client:
            await self._http.aclose()

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    # ------------------------------------------------------------ transport

    async def _attempt(self, url: str, body: bytes, timeout: float) -> RawResponse:
        try:
            resp = await self._http.post(url, content=body, headers=self._s.headers, timeout=timeout)
            data = await resp.aread()
        except httpx.ConnectTimeout as e:
            raise _connect_timeout(timeout) from e
        except httpx.TimeoutException as e:
            raise RequestTimeoutError(f"request timed out after {timeout} s") from e
        except httpx.ConnectError as e:
            raise NetworkError(f"request failed ({e})", connect_failed=True) from e
        except httpx.TransportError as e:
            raise NetworkError(f"request failed ({e.__class__.__name__})") from e
        return _core.decode(resp.status_code, dict(resp.headers.items()), data)

    async def _send(
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
                r = await self._attempt(url, body, t)
            except NetworkError as e:
                if not _core.should_retry_error(e, attempt, retries, retry_ambiguous):
                    raise
                await asyncio.sleep(_core.backoff_delay(self._s.retry_backoff, attempt, None))
                attempt += 1
                continue
            if attempt < retries and _core.should_retry_status(r, retry_ambiguous):
                await asyncio.sleep(_core.backoff_delay(self._s.retry_backoff, attempt, _core.retry_after_of(r)))
                attempt += 1
                continue
            return r

    # ------------------------------------------------------------ API

    async def validate(
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
        """Validate a pass token. Same parameters as ``Client.validate``."""
        if not isinstance(token, str) or token == "":
            return ValidateResult(valid=False, error="empty_token")
        if _core.is_client_only_token(token):
            return await self._validate_client_only()
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
            r = await self._send(url, body, retry_ambiguous=True)
        except CaptchaLaError as e:
            return ValidateResult(valid=False, offline=offline, **_core.network_failure(e))
        return _core.parse_validate(r, offline, expected_action)

    async def issue_server_token(
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
        """Issue a one-time ``sct_`` server token. Same parameters as ``Client.issue_server_token``."""
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
            r = await self._send(self._s.issue_url, body, retry_ambiguous=True)
        except CaptchaLaError as e:
            return IssueResult(ok=False, **_core.network_failure(e))
        return _core.parse_issue(r)

    async def moderation_check(
        self, input: List[ModerationItem], *, user_id: Optional[str] = None
    ) -> ModerationResult:
        if not input:
            return ModerationResult(ok=False, error="empty_input", message="input is required")
        return await self._moderate("check", {"input": list(input)}, user_id)

    async def moderation_text(self, text: str, *, user_id: Optional[str] = None) -> ModerationResult:
        if not text:
            return ModerationResult(ok=False, error="empty_text", message="text is required")
        return await self._moderate("text", {"text": text}, user_id)

    async def _moderate(self, kind: str, payload: Dict[str, Any], user_id: Optional[str]) -> ModerationResult:
        try:
            r = await self._send(
                self._s.moderation_url(kind), self._s.moderation_body(payload, user_id), retry_ambiguous=False
            )
        except CaptchaLaError as e:
            return ModerationResult(ok=False, **_core.network_failure(e))
        return _core.parse_moderation(r)

    # ------------------------------------------------------------ client-only tokens

    async def _validate_client_only(self) -> ValidateResult:
        if self._s.reject_client_only:
            return _core.client_only_policy_result()
        if await self._probe(self._s.validate_url):
            return _core.client_only_result(True, None)
        return _core.client_only_result(False, await self._probe(self._s.backup_validate_url))

    async def _probe(self, url: str) -> bool:
        hit = _core.cached_probe(url)
        if hit is not None:
            return hit
        key = (id(asyncio.get_running_loop()), url)
        pending = _inflight.get(key)
        if pending is not None:
            return await asyncio.shield(pending)
        fut: "asyncio.Future[bool]" = asyncio.get_running_loop().create_future()
        _inflight[key] = fut
        try:
            try:
                await self._send(url, dict(_core.PROBE_BODY), retry_ambiguous=False, timeout=_core.PROBE_TIMEOUT, max_retries=0)
                reachable = True
            except CaptchaLaError:
                reachable = False
            _core.store_probe(url, reachable)
            fut.set_result(reachable)
            return reachable
        except BaseException:
            # Cancelled: let waiters fail closed ("reachable" means reject).
            if not fut.done():
                fut.set_result(True)
            raise
        finally:
            _inflight.pop(key, None)


def _connect_timeout(timeout: float) -> RequestTimeoutError:
    e = RequestTimeoutError(f"connect timed out after {timeout} s")
    e.connect_failed = True
    return e
