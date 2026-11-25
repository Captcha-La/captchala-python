import asyncio
import json

import httpx
import pytest

import captchala
from captchala import AsyncClient, AuthenticationError, NetworkError, RequestTimeoutError
from conftest import SUCCESS


def run(coro):
    return asyncio.run(coro)


def mock(*steps):
    """httpx.MockTransport with scripted steps (httpx.Response, exception, or callable). Last repeats."""
    calls = []

    def handler(request: httpx.Request):
        calls.append({"url": str(request.url), "headers": request.headers, "body": json.loads(request.content)})
        step = steps[min(len(calls) - 1, len(steps) - 1)]
        if isinstance(step, BaseException):
            raise step
        if callable(step):
            return step(request)
        return step

    return httpx.MockTransport(handler), calls


def ok(data):
    return httpx.Response(200, json={"code": 0, "msg": "success", "data": data})


def make(transport, **kw):
    kw.setdefault("retry_backoff", 0)
    return AsyncClient("key_1", "secret_1", http_client=httpx.AsyncClient(transport=transport), **kw)


def test_lazy_export():
    assert captchala.AsyncClient is AsyncClient


def test_success_and_request():
    t, calls = mock(ok(SUCCESS))

    async def go():
        async with make(t) as c:
            return await c.validate("pt_abc", client_ip="5.6.7.8", expected_action="login", bind_uid="u")

    r = run(go())
    assert r.valid and r.uid == "user_42" and r.captcha_args.risk_score == 12
    assert calls[0]["url"] == "https://verify.captcha.la/v1/validate"
    assert calls[0]["headers"]["x-app-key"] == "key_1"
    assert calls[0]["headers"]["x-app-secret"] == "secret_1"
    assert calls[0]["body"] == {"pass_token": "pt_abc", "keep_token": False, "client_ip": "5.6.7.8", "expected_action": "login", "bind_uid": "u"}


def test_invalid():
    t, _ = mock(ok({"valid": False, "error": "token_not_found"}))
    r = run(make(t).validate("pt_bogus"))
    assert not r.valid and r.error == "token_not_found" and r.cause is None


def test_mismatch():
    t, _ = mock(ok({"valid": False, "error": "hostname_mismatch"}))
    assert run(make(t).validate("pt_x", expected_hostname=["a.example"])).error == "hostname_mismatch"


def test_connect_error_retried():
    t, calls = mock(httpx.ConnectError("refused"), ok(SUCCESS))
    assert run(make(t).validate("pt_x")).valid
    assert len(calls) == 2


def test_connect_error_exhausted():
    t, calls = mock(httpx.ConnectError("refused"))
    r = run(make(t, max_retries=2).validate("pt_x"))
    assert len(calls) == 3 and r.error == "request_failed"
    assert isinstance(r.cause, NetworkError) and r.cause.connect_failed


def test_timeout():
    t, calls = mock(httpx.ReadTimeout("slow"))
    r = run(make(t, max_retries=1).validate("pt_x"))
    assert len(calls) == 2 and isinstance(r.cause, RequestTimeoutError)


def test_503_retried():
    t, calls = mock(httpx.Response(503, text="busy"), ok(SUCCESS))
    assert run(make(t).validate("pt_x")).valid and len(calls) == 2


def test_auth_error():
    t, _ = mock(httpx.Response(200, json={"code": -1, "msg": "Invalid app secret", "error": "invalid_app_secret"}))
    r = run(make(t).validate("pt_x"))
    assert r.error == "invalid_app_secret" and isinstance(r.cause, AuthenticationError)


def test_issue_and_moderation():
    t, calls = mock(ok({"server_token": "sct_1", "expires_in": 60, "issued_at": 1}))
    r = run(make(t).issue_server_token("login", ttl=60))
    assert r.ok and r.token == "sct_1" and calls[0]["body"] == {"action": "login", "ttl": 60}

    t, calls = mock(ok({"flagged": True, "categories": {"hate": True}}))
    m = run(make(t).moderation_text("x", user_id="u"))
    assert m.ok and m.has_category("hate") and calls[0]["body"]["app_secret"] == "secret_1"

    t, calls = mock(httpx.ReadTimeout("slow"))
    m = run(make(t).moderation_check([captchala.text_item("x")]))
    assert len(calls) == 1 and isinstance(m.cause, RequestTimeoutError)


def test_client_only():
    t, calls = mock(httpx.ConnectError("down"))
    c = make(t)
    r = run(c.validate("co_x"))
    assert r.valid and r.client_only and len(calls) == 2

    captchala.reset_reachability_cache()
    t, calls = mock(httpx.Response(404, text="x"))
    r = run(make(t).validate("client_x"))
    assert not r.valid and r.error == captchala.ERROR_CLIENT_ONLY_REJECTED and len(calls) == 1


def test_client_only_single_flight():
    async def slow(request):
        await asyncio.sleep(0.05)
        return httpx.Response(200, text="x")

    calls = []

    async def handler(request):
        calls.append(1)
        return await slow(request)

    c = AsyncClient("k", "s", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    async def go():
        return await asyncio.gather(*(c.validate("co_1") for _ in range(5)))

    rs = run(go())
    assert len(calls) == 1 and all(not r.valid for r in rs)


def test_owned_client_closed():
    async def go():
        c = AsyncClient("k", "s")
        await c.aclose()
        return c._http.is_closed

    assert run(go())
