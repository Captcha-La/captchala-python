"""Flask integration.

Config keys: ``CAPTCHALA_APP_KEY``, ``CAPTCHALA_APP_SECRET`` (fall back to the
environment variables of the same name), ``CAPTCHALA_BASE_URL``,
``CAPTCHALA_TIMEOUT``, ``CAPTCHALA_REJECT_CLIENT_ONLY``.

::

    from captchala.contrib.flask import CaptchaLa

    captcha = CaptchaLa(app)          # or captcha.init_app(app)

    @app.post("/login")
    @captcha.required(action="login")
    def login():
        g.captchala                   # ValidateResult
"""

from __future__ import annotations

import asyncio
import functools
import inspect
from typing import Any, Callable, Iterable, Optional, Sequence, Union

from flask import Flask, current_app, g, jsonify, request

from ..client import Client
from ..ip import client_ip_from_headers
from ..results import ValidateResult

TOKEN_FIELDS = ("captcha_token", "captchala_token")
TOKEN_HEADER = "X-Captcha-Token"


def client_ip() -> Optional[str]:
    """End-user IP of the current request (``CF-Connecting-IP`` / ``X-Forwarded-For`` / ``X-Real-IP`` / remote addr)."""
    return client_ip_from_headers(request.headers.get, request.remote_addr)


def _token(fields: Iterable[str]) -> str:
    for f in fields:
        v = request.form.get(f)
        if v:
            return v
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        for f in fields:
            v = data.get(f)
            if isinstance(v, str) and v:
                return v
    return request.headers.get(TOKEN_HEADER, "")


class CaptchaLa:
    """Flask extension holding a configured ``Client``."""

    def __init__(self, app: Optional[Flask] = None, *, client: Optional[Client] = None) -> None:
        self._client = client
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        app.extensions["captchala"] = self
        if self._client is None:
            c = app.config
            self._client = Client(
                c.get("CAPTCHALA_APP_KEY"),
                c.get("CAPTCHALA_APP_SECRET"),
                base_url=c.get("CAPTCHALA_BASE_URL"),
                timeout=c.get("CAPTCHALA_TIMEOUT", 5.0),
                reject_client_only=c.get("CAPTCHALA_REJECT_CLIENT_ONLY", False),
            )

    @property
    def client(self) -> Client:
        if self._client is None:
            ext = current_app.extensions.get("captchala")
            c = getattr(ext, "_client", None)
            if not isinstance(c, Client):
                raise RuntimeError("CaptchaLa is not initialised; call init_app(app)")
            return c
        return self._client

    def verify(
        self,
        token: Optional[str] = None,
        *,
        action: Optional[str] = None,
        hostname: Optional[Union[str, Sequence[str]]] = None,
        fields: Iterable[str] = TOKEN_FIELDS,
        **identity: Any,
    ) -> ValidateResult:
        """Validate ``token`` (default: read from the current request)."""
        return self.client.validate(
            token if token is not None else _token(fields),
            client_ip=client_ip(),
            expected_action=action,
            expected_hostname=hostname,
            **identity,
        )

    def required(
        self,
        view: Optional[Callable[..., Any]] = None,
        *,
        action: Optional[str] = None,
        hostname: Optional[Union[str, Sequence[str]]] = None,
        fields: Iterable[str] = TOKEN_FIELDS,
        allow_degraded: bool = False,
        on_failure: Optional[Callable[[ValidateResult], Any]] = None,
    ) -> Any:
        """View decorator. Sets ``g.captchala``; on failure returns 400
        ``{"error": "captcha_failed", "code": "..."}`` (or ``on_failure(result)``).
        """
        fields = tuple(fields)

        def decide(result: ValidateResult) -> Any:
            g.captchala = result
            if result.valid or (allow_degraded and result.degraded):
                return None
            if on_failure is not None:
                return on_failure(result)
            return jsonify({"error": "captcha_failed", "code": result.error or "unknown_error"}), 400

        def evaluate() -> ValidateResult:
            return self.verify(action=action, hostname=hostname, fields=fields)

        def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
            if inspect.iscoroutinefunction(fn):

                @functools.wraps(fn)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    # The sync client blocks; keep it off the event loop.
                    from flask import copy_current_request_context

                    result = await asyncio.get_running_loop().run_in_executor(
                        None, copy_current_request_context(evaluate)
                    )
                    denied = decide(result)
                    return denied if denied is not None else await fn(*args, **kwargs)

                return async_wrapper

            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                denied = decide(evaluate())
                return denied if denied is not None else fn(*args, **kwargs)

            return wrapper

        return decorate(view) if view is not None else decorate
