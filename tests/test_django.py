import asyncio
import json

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        SECRET_KEY="test",
        ALLOWED_HOSTS=["*"],
        CAPTCHALA_APP_KEY="dj_key",
        CAPTCHALA_APP_SECRET="dj_secret",
        INSTALLED_APPS=[],
    )
    django.setup()

from django import forms  # noqa: E402
from django.http import HttpResponse  # noqa: E402
from django.test import RequestFactory  # noqa: E402

from captchala.contrib import django as cdj  # noqa: E402
from conftest import FakeTransport, make, ok  # noqa: E402

rf = RequestFactory()


def test_get_client_from_settings():
    assert cdj.get_client().app_key == "dj_key"


def test_field_valid_and_ip_forwarded():
    t = FakeTransport(ok({"valid": True, "action": "login"}))

    class LoginForm(cdj.CaptchaLaFormMixin, forms.Form):
        captcha_token = cdj.CaptchaLaField(expected_action="login", client=make(t))

    req = rf.post("/login", {"captcha_token": "pt_1"}, HTTP_X_FORWARDED_FOR="9.9.9.9")
    form = LoginForm(req.POST, request=req)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["captcha_token"].valid is True
    assert t.calls[0]["body"] == {"pass_token": "pt_1", "keep_token": False, "client_ip": "9.9.9.9", "expected_action": "login"}


def test_field_invalid():
    t = FakeTransport(ok({"valid": False, "error": "token_expired"}))

    class F(forms.Form):
        captcha_token = cdj.CaptchaLaField(client=make(t))

    form = F({"captcha_token": "pt_1"})
    assert not form.is_valid()
    err = form.errors.as_data()["captcha_token"][0]
    assert err.code == "token_expired" and "refresh" in err.message


def test_field_missing_token_no_network():
    t = FakeTransport(ok({"valid": True}))

    class F(forms.Form):
        captcha_token = cdj.CaptchaLaField(client=make(t))

    assert not F({}).is_valid()
    assert t.calls == []


def test_decorator_pass_and_fail():
    t = FakeTransport(ok({"valid": True, "uid": "u1"}), ok({"valid": False, "error": "action_mismatch"}))

    @cdj.captchala_required(action="login", client=make(t))
    def view(request):
        return HttpResponse(request.captchala.uid)

    r = view(rf.post("/x", {"captchala_token": "pt_1"}))
    assert r.status_code == 200 and r.content == b"u1"
    r = view(rf.post("/x", {"captcha_token": "pt_2"}))
    assert r.status_code == 400
    assert json.loads(r.content) == {"error": "captcha_failed", "code": "action_mismatch"}
    assert t.calls[0]["body"]["expected_action"] == "login"


def test_decorator_json_and_header():
    t = FakeTransport(ok({"valid": True}))

    @cdj.captchala_required(client=make(t))
    def view(request):
        return HttpResponse("ok")

    view(rf.post("/x", data=json.dumps({"captcha_token": "pt_json"}), content_type="application/json"))
    view(rf.post("/x", HTTP_X_CAPTCHA_TOKEN="pt_hdr"))
    assert [c["body"]["pass_token"] for c in t.calls] == ["pt_json", "pt_hdr"]


def test_decorator_degraded_and_async_view():
    t = FakeTransport(ok({"valid": False, "degraded": True, "reason": "quota_exhausted"}))

    @cdj.captchala_required(allow_degraded=True, client=make(t))
    async def view(request):
        return HttpResponse("degraded" if request.captchala.degraded else "no")

    r = asyncio.run(view(rf.post("/x", {"captcha_token": "dg_1"})))
    assert r.status_code == 200 and r.content == b"degraded"
