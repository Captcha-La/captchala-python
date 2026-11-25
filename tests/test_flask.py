import asyncio

from flask import Flask, g

from captchala.contrib.flask import CaptchaLa
from conftest import FakeTransport, make, ok


def build(t, **kw):
    app = Flask(__name__)
    captcha = CaptchaLa(app, client=make(t))

    @app.post("/login")
    @captcha.required(action="login", **kw)
    def login():
        return {"uid": g.captchala.uid}

    return app, captcha


def test_config_client():
    app = Flask(__name__)
    app.config.update(CAPTCHALA_APP_KEY="fk", CAPTCHALA_APP_SECRET="fs")
    assert CaptchaLa(app).client.app_key == "fk"


def test_required_pass_form():
    t = FakeTransport(ok({"valid": True, "uid": "u1"}))
    app, _ = build(t)
    r = app.test_client().post("/login", data={"captcha_token": "pt_1"}, headers={"X-Forwarded-For": "8.8.8.8"})
    assert r.status_code == 200 and r.get_json() == {"uid": "u1"}
    assert t.calls[0]["body"] == {"pass_token": "pt_1", "keep_token": False, "client_ip": "8.8.8.8", "expected_action": "login"}


def test_required_fail_json_body():
    t = FakeTransport(ok({"valid": False, "error": "token_already_used"}))
    app, _ = build(t)
    r = app.test_client().post("/login", json={"captchala_token": "pt_2"})
    assert r.status_code == 400 and r.get_json() == {"error": "captcha_failed", "code": "token_already_used"}


def test_header_token_and_on_failure():
    t = FakeTransport(ok({"valid": False, "error": "x"}))
    app, _ = build(t, on_failure=lambda result: ({"nope": result.error}, 403))
    r = app.test_client().post("/login", headers={"X-Captcha-Token": "pt_h"})
    assert r.status_code == 403 and r.get_json() == {"nope": "x"}
    assert t.calls[0]["body"]["pass_token"] == "pt_h"


def test_missing_token():
    t = FakeTransport(ok({"valid": True}))
    app, _ = build(t)
    r = app.test_client().post("/login")
    assert r.get_json()["code"] == "empty_token" and t.calls == []


def test_verify_and_async_view():
    t = FakeTransport(ok({"valid": True, "uid": "u9"}))
    app = Flask(__name__)
    captcha = CaptchaLa(app, client=make(t))

    @app.post("/a")
    @captcha.required
    async def a():
        await asyncio.sleep(0)
        return {"uid": g.captchala.uid}

    r = app.test_client().post("/a", data={"captcha_token": "pt_a"})
    assert r.status_code == 200 and r.get_json() == {"uid": "u9"}

    with app.test_request_context("/v", method="POST", data={"captcha_token": "pt_v"}):
        assert captcha.verify(action="login").valid
