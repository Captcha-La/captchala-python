import threading

import pytest

import captchala
from captchala import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    InvalidResponseError,
    NetworkError,
    RateLimitError,
    RequestTimeoutError,
    ValidationFailedError,
)
from conftest import REFUSED, RESET, SUCCESS, TIMEOUT, FakeTransport, make, ok, reply


# ----------------------------------------------------------------- constructor


def test_requires_credentials(monkeypatch):
    monkeypatch.delenv("CAPTCHALA_APP_KEY", raising=False)
    monkeypatch.delenv("CAPTCHALA_APP_SECRET", raising=False)
    with pytest.raises(ConfigurationError):
        captchala.Client(app_secret="s")
    with pytest.raises(ConfigurationError):
        captchala.Client("k")
    monkeypatch.setenv("CAPTCHALA_APP_KEY", "env_key")
    monkeypatch.setenv("CAPTCHALA_APP_SECRET", "env_secret")
    assert captchala.Client().app_key == "env_key"


def test_repr_hides_secret():
    c = make(FakeTransport(ok({})))
    assert "secret_1" not in repr(c)
    assert "secret_1" not in repr(c._s)


# ----------------------------------------------------------------- validate


def test_success_maps_fields_and_sends_credentials():
    t = FakeTransport(ok(SUCCESS))
    r = make(t).validate("pt_abc")
    assert r.valid is True and r.error is None
    assert (r.challenge_id, r.action, r.uid, r.hostname) == ("ch_1", "login", "user_42", "a.example")
    assert r.challenge_ts == "2025-06-15T15:06:40Z"
    assert r.risk_level == "low" and r.risk_labels == ("proxy",)
    assert r.captcha_args == captchala.CaptchaArgs("web", "1.2.3.4", "https://a.example/login", None, 1750000000, 12)
    assert r.user_ip == "1.2.3.4"
    assert r.binding.email == "A@example.com"
    assert r.binding_mismatch is False
    assert r.offline is False and r.test is False
    assert len(t.calls) == 1
    c = t.calls[0]
    assert c["url"] == "https://verify.captcha.la/v1/validate"
    assert c["headers"]["X-App-Key"] == "key_1"
    assert c["headers"]["X-App-Secret"] == "secret_1"
    assert c["headers"]["Content-Type"] == "application/json"
    assert c["headers"]["User-Agent"] == f"captchala-python/{captchala.__version__}"
    assert c["body"] == {"pass_token": "pt_abc", "keep_token": False}
    assert c["timeout"] == 5.0


def test_sends_all_options():
    t = FakeTransport(ok(SUCCESS))
    make(t).validate(
        "pt_abc",
        client_ip="5.6.7.8",
        keep_token=True,
        expected_action="login",
        expected_hostname=("a.example", "*.b.example"),
        bind_uid="user_42",
        bind_account="alice",
        bind_email="a@example.com",
        bind_phone="+8613800138000",
        scene="login",
    )
    assert t.calls[0]["body"] == {
        "pass_token": "pt_abc",
        "keep_token": True,
        "client_ip": "5.6.7.8",
        "expected_action": "login",
        "expected_hostname": ["a.example", "*.b.example"],
        "bind_uid": "user_42",
        "bind_account": "alice",
        "bind_email": "a@example.com",
        "bind_phone": "+8613800138000",
        "scene": "login",
    }


def test_api_url_is_not_configurable():
    t = FakeTransport(ok(SUCCESS))
    with pytest.raises(TypeError):
        make(t, base_url="http://127.0.0.1:9999/")
    with pytest.raises(TypeError):
        make(t, backup_url="https://backup.example")
    assert not hasattr(make(t), "base_url")


def test_invalid_token_is_clean_failure():
    t = FakeTransport(ok({"valid": False, "error": "token_not_found"}))
    r = make(t).validate("pt_bogus")
    assert r.valid is False and r.error == "token_not_found"
    assert r.cause is None and r.http_status == 200
    assert len(t.calls) == 1


def test_empty_token_no_network():
    t = FakeTransport(ok(SUCCESS))
    assert make(t).validate("").error == "empty_token"
    assert t.calls == []


@pytest.mark.parametrize("code", ["action_mismatch", "hostname_mismatch"])
def test_mismatch_from_api(code):
    r = make(FakeTransport(ok({"valid": False, "error": code}))).validate(
        "pt_x", expected_action="login", expected_hostname="a.example"
    )
    assert r.valid is False and r.error == code


def test_action_recheck():
    r = make(FakeTransport(ok({**SUCCESS, "action": "pay"}))).validate("pt_x", expected_action="login")
    assert r.valid is False and r.error == "action_mismatch" and r.action == "pay"


def test_action_recheck_skips_test_keys():
    r = make(FakeTransport(ok({"valid": True, "test": True, "action": "test"}))).validate("pt_x", expected_action="login")
    assert r.valid is True and r.test is True


def test_binding_mismatch():
    r = make(FakeTransport(ok({**SUCCESS, "binding_match": {"uid": True, "email": False}}))).validate("pt_x")
    assert r.valid is True and r.binding_mismatch is True


def test_degraded():
    r = make(FakeTransport(ok({"valid": False, "degraded": True, "reason": "quota_exhausted"}))).validate("dg_x")
    assert r.valid is False and r.degraded is True and r.degraded_reason == "quota_exhausted"


def test_offline_goes_to_backup():
    t = FakeTransport(ok({"valid": True}))
    r = make(t).validate("offline_abc")
    assert t.calls[0]["url"] == "https://fallbackapiv1.captchala.com/api/validate"
    assert r.valid is True and r.offline is True


def test_auth_error_typed_cause():
    t = FakeTransport(reply(200, {"code": -1, "msg": "Invalid app secret", "error": "invalid_app_secret"}))
    r = make(t).validate("pt_x")
    assert r.valid is False and r.error == "invalid_app_secret"
    assert isinstance(r.cause, AuthenticationError) and isinstance(r.cause, APIError)
    assert len(t.calls) == 1


def test_code0_on_non2xx_not_success():
    r = make(FakeTransport(reply(500, {"code": 0, "data": {"valid": True}}))).validate("pt_x")
    assert r.valid is False and isinstance(r.cause, APIError) and r.http_status == 500


def test_connection_failure_retried_then_request_failed():
    t = FakeTransport(REFUSED)
    r = make(t, max_retries=2).validate("pt_x")
    assert len(t.calls) == 3
    assert r.error == "request_failed"
    assert isinstance(r.cause, NetworkError) and r.cause.connect_failed


def test_retry_then_success():
    t = FakeTransport(REFUSED, ok(SUCCESS))
    assert make(t).validate("pt_x").valid is True
    assert len(t.calls) == 2


@pytest.mark.parametrize("status", [502, 503, 504])
def test_gateway_errors_retried(status):
    t = FakeTransport(reply(status, "<html>bad</html>"), ok(SUCCESS))
    assert make(t).validate("pt_x").valid is True
    assert len(t.calls) == 2


def test_exhausted_502():
    t = FakeTransport(reply(502, "<html>bad</html>"))
    r = make(t, max_retries=1).validate("pt_x")
    assert len(t.calls) == 2
    assert r.error == "http_502" and isinstance(r.cause, InvalidResponseError)


def test_service_online_not_retried():
    t = FakeTransport(reply(503, {"code": -1, "error": "service_online", "message": "x"}))
    r = make(t).validate("pt_x")
    assert len(t.calls) == 1 and r.error == "service_online"


def test_429_not_retried():
    t = FakeTransport(reply(429, {"code": -1, "error": "rate_limited", "retry_after": 7, "retryable": True}))
    r = make(t).validate("pt_x")
    assert len(t.calls) == 1
    assert r.error == "rate_limited" and r.retry_after == 7 and r.retryable is True
    assert isinstance(r.cause, RateLimitError)


def test_retry_after_header():
    r = make(FakeTransport(reply(429, {"code": -1, "error": "rate_limited"}, {"Retry-After": "3"}))).validate("pt_x")
    assert r.retry_after == 3


def test_timeout_retried_for_validate():
    t = FakeTransport(TIMEOUT)
    r = make(t, max_retries=1).validate("pt_x")
    assert len(t.calls) == 2
    assert r.error == "request_failed" and isinstance(r.cause, RequestTimeoutError)


def test_max_retries_zero():
    t = FakeTransport(REFUSED)
    make(t, max_retries=0).validate("pt_x")
    assert len(t.calls) == 1


def test_non_json_200():
    r = make(FakeTransport(reply(200, "not json"))).validate("pt_x")
    assert r.error == "invalid_response" and isinstance(r.cause, InvalidResponseError)


def test_raise_if_invalid():
    good = make(FakeTransport(ok(SUCCESS))).validate("pt_x")
    assert good.raise_if_invalid() is good
    bad = make(FakeTransport(ok({"valid": False, "error": "token_expired"}))).validate("pt_x")
    with pytest.raises(ValidationFailedError) as ei:
        bad.raise_if_invalid()
    assert ei.value.code == "token_expired" and ei.value.result is bad


def test_to_dict():
    d = make(FakeTransport(ok(SUCCESS))).validate("pt_x").to_dict()
    assert d["valid"] is True and d["challenge_id"] == "ch_1" and d["captcha_args"]["user_ip"] == "1.2.3.4"


# ----------------------------------------------------------------- client-only tokens


def test_client_only_policy():
    t = FakeTransport(ok({}))
    r = make(t, reject_client_only=True).validate("co_abc")
    assert r.valid is False and r.client_only and r.error == captchala.ERROR_CLIENT_ONLY_POLICY
    assert t.calls == []


@pytest.mark.parametrize("status", [200, 400, 503])
def test_client_only_rejected_when_main_reachable(status):
    t = FakeTransport(reply(status, "nope"))
    r = make(t).validate("client_abc")
    assert r.valid is False and r.error == captchala.ERROR_CLIENT_ONLY_REJECTED
    assert len(t.calls) == 1
    assert t.calls[0]["body"] == {"pass_token": "", "keep_token": True}
    assert t.calls[0]["timeout"] == 2.0


def test_client_only_rejected_when_backup_reachable():
    t = FakeTransport(REFUSED, reply(200, "ok"))
    r = make(t).validate("co_abc")
    assert r.valid is False and "backup" in r.warning
    assert len(t.calls) == 2


def test_client_only_accepted_when_both_down_and_cached():
    t = FakeTransport(REFUSED)
    c = make(t)
    r = c.validate("client_abc")
    assert r.valid and r.client_only and r.offline and r.warning
    assert len(t.calls) == 2
    c.validate("co_def")
    assert len(t.calls) == 2


def test_client_only_probe_single_flight():
    gate = threading.Event()

    def slow(*_):
        gate.wait(2)
        return reply(200, "x")

    t = FakeTransport(slow)
    c = make(t)
    results = []
    threads = [threading.Thread(target=lambda: results.append(c.validate("co_1"))) for _ in range(3)]
    for th in threads:
        th.start()
    gate.set()
    for th in threads:
        th.join()
    assert len(t.calls) == 1
    assert all(not r.valid for r in results)


# ----------------------------------------------------------------- issue


def test_issue_success():
    t = FakeTransport(ok({"server_token": "sct_abc", "expires_in": 300, "issued_at": 1713600000}))
    r = make(t).issue_server_token(
        "login", bind_ip="1.2.3.4", ttl=120, max_uses=3, bind_uid="u1", bind_email="a@b.example",
        bind_device_id="d1", bind_fingerprint="fp1", scene="login",
    )
    assert r.ok and r.token == "sct_abc" and r.expires_in == 300 and r.issued_at == 1713600000
    assert t.calls[0]["url"] == "https://verify.captcha.la/v1/server/challenge/issue"
    assert t.calls[0]["body"] == {
        "action": "login", "bind_ip": "1.2.3.4", "ttl": 120, "max_uses": 3, "bind_device_id": "d1",
        "bind_fingerprint": "fp1", "bind_uid": "u1", "bind_email": "a@b.example", "scene": "login",
    }


def test_issue_empty_action():
    t = FakeTransport(ok({}))
    r = make(t).issue_server_token("")
    assert not r.ok and r.error == "invalid_action" and t.calls == []


def test_issue_error_code_not_message():
    r = make(FakeTransport(reply(200, {"code": -1, "msg": "secret mismatch", "error": "invalid_app_secret"}))).issue_server_token("login")
    assert not r.ok and r.error == "invalid_app_secret" and r.message == "secret mismatch"
    assert isinstance(r.cause, AuthenticationError)


def test_issue_rate_limit():
    r = make(FakeTransport(reply(200, {"code": -1, "error": "rate_limit_exceeded", "retry_after": 10}))).issue_server_token("login")
    assert r.error == "rate_limit_exceeded" and isinstance(r.cause, RateLimitError) and r.retry_after == 10


def test_issue_network_failure_retried():
    t = FakeTransport(RESET)
    r = make(t, max_retries=1).issue_server_token("login")
    assert not r.ok and r.error == "request_failed" and len(t.calls) == 2


# ----------------------------------------------------------------- moderation


def test_moderation_check():
    t = FakeTransport(ok({"flagged": True, "categories": {"violence": True, "hate": False}, "category_scores": {"violence": 0.9}}))
    r = make(t).moderation_check(
        [captchala.text_item("hello"), captchala.image_url_item("https://img.example/a.png")], user_id="u1"
    )
    assert r.ok and r.flagged
    assert r.has_category("hate") is False and r.has_category("hate", "violence") is True
    assert r.category_scores == {"violence": 0.9}
    assert t.calls[0]["url"] == "https://verify.captcha.la/v1/moderation/check"
    assert t.calls[0]["body"] == {
        "app_key": "key_1", "app_secret": "secret_1", "user_id": "u1",
        "input": [{"type": "text", "text": "hello"}, {"type": "image_url", "image_url": {"url": "https://img.example/a.png"}}],
    }


def test_moderation_text():
    t = FakeTransport(ok({"flagged": False}))
    r = make(t).moderation_text("hi")
    assert r.ok and not r.flagged
    assert t.calls[0]["url"].endswith("/v1/moderation/text") and t.calls[0]["body"]["text"] == "hi"


def test_moderation_empty():
    t = FakeTransport(ok({}))
    assert make(t).moderation_check([]).error == "empty_input"
    assert make(t).moderation_text("").error == "empty_text"
    assert t.calls == []


def test_moderation_error_envelope():
    r = make(FakeTransport(reply(401, {"code": 1, "error": "invalid_credentials", "message": "bad"}))).moderation_text("hi")
    assert not r.ok and r.error == "invalid_credentials" and r.message == "bad"
    assert isinstance(r.cause, AuthenticationError)


def test_moderation_not_retried_after_timeout():
    t = FakeTransport(TIMEOUT)
    r = make(t).moderation_text("hi")
    assert len(t.calls) == 1 and isinstance(r.cause, RequestTimeoutError)


def test_moderation_retried_after_connect_failure():
    t = FakeTransport(REFUSED, ok({"flagged": False}))
    assert make(t).moderation_text("hi").ok
    assert len(t.calls) == 2


# ----------------------------------------------------------------- helpers


def test_user_message():
    assert "refresh" in captchala.user_message("token_expired")
    assert captchala.user_message("brand_new") == captchala.user_message(None)


def test_client_ip_from_headers():
    h = {"CF-Connecting-IP": None, "X-Forwarded-For": " 2.2.2.2, 3.3.3.3", "X-Real-IP": "4.4.4.4"}
    assert captchala.client_ip_from_headers(h.get) == "2.2.2.2"
    assert captchala.client_ip_from_headers({"X-Forwarded-For": "junk"}.get, "::ffff:5.5.5.5") == "5.5.5.5"
    assert captchala.client_ip_from_headers({}.get, "2001:db8::1") == "2001:db8::1"
    assert captchala.client_ip_from_headers({}.get) is None
