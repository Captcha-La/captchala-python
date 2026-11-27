"""Django integration: a form field and a view decorator.

Settings (all optional except the credentials, which fall back to the
``CAPTCHALA_APP_KEY`` / ``CAPTCHALA_APP_SECRET`` environment variables)::

    CAPTCHALA_APP_KEY = "..."
    CAPTCHALA_APP_SECRET = "..."
    CAPTCHALA_TIMEOUT = 5.0
    CAPTCHALA_REJECT_CLIENT_ONLY = False

Form field::

    from captchala.contrib.django import CaptchaLaField, CaptchaLaFormMixin

    class LoginForm(CaptchaLaFormMixin, forms.Form):
        username = forms.CharField()
        captcha_token = CaptchaLaField(expected_action="login")

    form = LoginForm(request.POST, request=request)   # request: forwards the client IP
    if form.is_valid():
        result = form.cleaned_data["captcha_token"]      # ValidateResult

View decorator::

    from captchala.contrib.django import captchala_required

    @captchala_required(action="login")
    def login_view(request):
        request.captchala  # ValidateResult
"""

from __future__ import annotations

import functools
import inspect
import json
from typing import Any, Callable, Iterable, Optional, Sequence, Tuple, Union

from django import forms
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

from ..client import Client
from ..ip import client_ip_from_headers
from ..messages import user_message
from ..results import ValidateResult

TOKEN_FIELDS = ("captcha_token", "captchala_token")
TOKEN_HEADER = "HTTP_X_CAPTCHA_TOKEN"

_client: Optional[Client] = None
_client_key: Optional[Tuple[Any, ...]] = None


def get_client() -> Client:
    """A client built from Django settings, cached until the settings change."""
    global _client, _client_key
    key = (
        getattr(settings, "CAPTCHALA_APP_KEY", None),
        getattr(settings, "CAPTCHALA_APP_SECRET", None),
        getattr(settings, "CAPTCHALA_TIMEOUT", 5.0),
        getattr(settings, "CAPTCHALA_REJECT_CLIENT_ONLY", False),
    )
    if _client is None or key != _client_key:
        _client = Client(key[0], key[1], timeout=key[2], reject_client_only=key[3])
        _client_key = key
    return _client


def client_ip(request: HttpRequest) -> Optional[str]:
    """End-user IP from ``CF-Connecting-IP`` / ``X-Forwarded-For`` / ``X-Real-IP`` / ``REMOTE_ADDR``."""
    return client_ip_from_headers(request.headers.get, request.META.get("REMOTE_ADDR"))


def _passes(result: ValidateResult, allow_degraded: bool) -> bool:
    return result.valid or (allow_degraded and result.degraded)


class CaptchaLaField(forms.CharField):
    """Validates a pass token. ``cleaned_data[name]`` is the ``ValidateResult``.

    Errors use ``captchala.user_message()`` texts and the API error code as
    the ``ValidationError`` code.
    """

    widget = forms.HiddenInput

    def __init__(
        self,
        *,
        expected_action: Optional[str] = None,
        expected_hostname: Optional[Union[str, Sequence[str]]] = None,
        allow_degraded: bool = False,
        client: Optional[Client] = None,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("required", True)
        kwargs.setdefault("error_messages", {"required": user_message(None)})
        super().__init__(**kwargs)
        self.expected_action = expected_action
        self.expected_hostname = expected_hostname
        self.allow_degraded = allow_degraded
        self.client = client
        #: Set by CaptchaLaFormMixin so the client IP can be forwarded.
        self.request: Optional[HttpRequest] = None

    def clean(self, value: Any) -> ValidateResult:  # type: ignore[override]
        token = super().clean(value)
        result = (self.client or get_client()).validate(
            token,
            client_ip=client_ip(self.request) if self.request is not None else None,
            expected_action=self.expected_action,
            expected_hostname=self.expected_hostname,
        )
        if not _passes(result, self.allow_degraded):
            raise forms.ValidationError(user_message(result.error), code=result.error or "captcha_failed")
        return result


class CaptchaLaFormMixin:
    """Accepts ``request=`` and hands it to every ``CaptchaLaField`` (for the client IP)."""

    def __init__(self, *args: Any, request: Optional[HttpRequest] = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        for f in self.fields.values():  # type: ignore[attr-defined]
            if isinstance(f, CaptchaLaField):
                f.request = request


def _token_from_request(request: HttpRequest, fields: Iterable[str]) -> str:
    for f in fields:
        v = request.POST.get(f)
        if v:
            return v
    if request.content_type == "application/json" and request.body:
        try:
            data = json.loads(request.body)
        except ValueError:
            data = None
        if isinstance(data, dict):
            for f in fields:
                v = data.get(f)
                if isinstance(v, str) and v:
                    return v
    return request.META.get(TOKEN_HEADER, "")


def verify_request(
    request: HttpRequest,
    *,
    action: Optional[str] = None,
    hostname: Optional[Union[str, Sequence[str]]] = None,
    fields: Iterable[str] = TOKEN_FIELDS,
    client: Optional[Client] = None,
    **identity: Any,
) -> ValidateResult:
    """Validate the token carried by ``request`` (form field, JSON body or ``X-Captcha-Token``)."""
    return (client or get_client()).validate(
        _token_from_request(request, fields),
        client_ip=client_ip(request),
        expected_action=action,
        expected_hostname=hostname,
        **identity,
    )


def _failure(result: ValidateResult) -> HttpResponse:
    return JsonResponse({"error": "captcha_failed", "code": result.error or "unknown_error"}, status=400)


def captchala_required(
    view: Optional[Callable[..., Any]] = None,
    *,
    action: Optional[str] = None,
    hostname: Optional[Union[str, Sequence[str]]] = None,
    fields: Iterable[str] = TOKEN_FIELDS,
    allow_degraded: bool = False,
    client: Optional[Client] = None,
    on_failure: Optional[Callable[[HttpRequest, ValidateResult], HttpResponse]] = None,
) -> Any:
    """View decorator. Sets ``request.captchala``; on failure returns 400
    ``{"error": "captcha_failed", "code": "..."}`` (or ``on_failure(request, result)``).
    Works with sync and async views.
    """
    fields = tuple(fields)

    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        def check(request: HttpRequest) -> Optional[HttpResponse]:
            result = verify_request(request, action=action, hostname=hostname, fields=fields, client=client)
            request.captchala = result  # type: ignore[attr-defined]
            if _passes(result, allow_degraded):
                return None
            return on_failure(request, result) if on_failure else _failure(result)

        if inspect.iscoroutinefunction(fn):
            from asgiref.sync import sync_to_async

            @functools.wraps(fn)
            async def async_wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
                denied = await sync_to_async(check, thread_sensitive=False)(request)
                return denied if denied is not None else await fn(request, *args, **kwargs)

            return async_wrapper

        @functools.wraps(fn)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
            denied = check(request)
            return denied if denied is not None else fn(request, *args, **kwargs)

        return wrapper

    return decorate(view) if view is not None else decorate
