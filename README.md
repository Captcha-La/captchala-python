# CaptchaLa Python SDK

**English** · [简体中文](https://github.com/Captcha-La/captchala-python/blob/main/README_zh.md) · [日本語](https://github.com/Captcha-La/captchala-python/blob/main/README.ja.md) · [한국어](https://github.com/Captcha-La/captchala-python/blob/main/README.ko.md) · [Español](https://github.com/Captcha-La/captchala-python/blob/main/README.es.md) · [Português (BR)](https://github.com/Captcha-La/captchala-python/blob/main/README.pt-BR.md) · [Deutsch](https://github.com/Captcha-La/captchala-python/blob/main/README.de.md)

Server-side SDK for validating CaptchaLa tokens from Python. Sync and async clients, typed, with optional Django and Flask helpers.

- [Website](https://captcha.la)
- [Documentation](https://docs.captcha.la/sdk/server-python)
- [Web SDK Documentation](https://docs.captcha.la/web-sdk)
- [Dashboard](https://dash.captcha.la)

## Installation

```bash
pip install captchala             # sync client, no dependencies
pip install "captchala[async]"    # + AsyncClient (httpx)
pip install "captchala[django]"   # + Django helpers
pip install "captchala[flask]"    # + Flask helpers
```

Requires **Python 3.9+**. The sync client uses only the standard library.

## Quick Start

```python
from captchala import Client

# Reads CAPTCHALA_APP_KEY / CAPTCHALA_APP_SECRET when not passed.
captchala = Client("your_app_key", "your_app_secret")

result = captchala.validate(
    token,
    client_ip=user_ip,          # optional, recommended
    expected_action="login",    # optional: reject tokens issued for another action
)

if result.valid:
    ...  # Verification passed
else:
    print(result.error)  # e.g. "token_expired"
```

Async:

```python
from captchala import AsyncClient

async with AsyncClient() as captchala:
    result = await captchala.validate(token, client_ip=user_ip)
```

## API Reference

### `Client(app_key=None, app_secret=None, **options)` / `AsyncClient(...)`

| Option | Default | Description |
|---|---|---|
| `app_key` | `$CAPTCHALA_APP_KEY` | App Key (from dashboard) |
| `app_secret` | `$CAPTCHALA_APP_SECRET` | App Secret (from dashboard). Server-side only |
| `base_url` | `https://verify.captcha.la` | API base URL |
| `timeout` | `5.0` | Timeout per attempt, in seconds |
| `max_retries` | `2` | Retries after the first attempt (`0` disables) |
| `retry_backoff` | `0.2` | Base delay for exponential backoff, in seconds |
| `reject_client_only` | `False` | Always reject client-only tokens, see below |
| `headers` | `None` | Extra headers sent with every request |
| `transport` | urllib | *(sync)* Custom transport callable, see [Testing](#testing-your-integration) |
| `http_client` | new `httpx.AsyncClient` | *(async)* Share your own httpx client |

Raises `ConfigurationError` when the key or secret is missing. Create one client and reuse it; `Client` is thread-safe. Close an `AsyncClient` with `await client.aclose()` or `async with`.

### `client.validate(token, **options) -> ValidateResult`

Validate a pass token from the client SDK. It never raises for invalid tokens, API errors or network failures. Check `result.valid` and `result.error`.

| Option | Description |
|---|---|
| `client_ip` | *(optional, recommended)* The end-user's IP from your inbound request. Used for additional risk checks |
| `keep_token` | `True` = check without consuming the token (default `False`) |
| `expected_action` | Action you expect, e.g. `"login"`. A token issued for another action fails with `action_mismatch` |
| `expected_hostname` | Hostname (web) or package / bundle id (native) you expect, as a string or a list. `*.example.com` matches any subdomain. Mismatch: `hostname_mismatch` |
| `bind_uid`, `bind_account`, `bind_email`, `bind_phone`, `scene` | End-user identity, compared with the identity bound at issue (see `binding_match`) |

```python
result = captchala.validate(
    request.POST["captcha_token"],
    client_ip=ip,
    expected_action="login",
    expected_hostname=["www.example.com", "*.example.com"],
    bind_uid=str(user.id),
)
```

### `ValidateResult`

| Attribute | Type | Description |
|---|---|---|
| `valid` | `bool` | Whether validation passed. The only field to gate on |
| `error` | `str \| None` | Error code, e.g. `token_expired`, `action_mismatch`, `request_failed` |
| `message` | `str \| None` | Human-readable API message, for API-level errors |
| `action` | `str \| None` | Business action of the token |
| `uid` | `str \| None` | User ID bound via `bind_uid` at issue |
| `challenge_id` | `str \| None` | Challenge ID |
| `hostname` | `str \| None` | Where the challenge was solved (hostname or package id) |
| `challenge_ts` | `str \| None` | Solve time, ISO 8601 UTC |
| `risk_level` | `str \| None` | `low` / `medium` / `high` / `critical`. Informational |
| `risk_labels` | `tuple[str, ...]` | Coarse risk categories, e.g. `proxy`. Informational |
| `captcha_args` | `CaptchaArgs \| None` | Solve-context echo: `platform`, `user_ip`, `referer`, `pkg`, `solved_at`, `risk_score`. Informational |
| `user_ip` | `str \| None` | End-user IP recorded at solve time. Informational |
| `binding` / `binding_match` | | Identity bound at issue, and the per-field comparison |
| `binding_mismatch` | `bool` | `True` when any `binding_match` field is `False` |
| `degraded` / `degraded_reason` | | `dg_` token issued while the quota is exhausted, see below |
| `offline` / `client_only` / `warning` | | Outage fallbacks, see [Token Types](#token-types) |
| `test` | `bool` | Answer from a public test key. Reject it in production |
| `http_status`, `retry_after`, `retryable` | | Failure details |
| `cause` | `CaptchaLaError \| None` | Typed error for API / network failures |
| `raw` | `dict \| None` | The raw `data` object |

Methods: `raise_if_invalid()` raises `ValidationFailedError` unless `valid`; `to_dict()`.

### Verifying `bind_uid`

If you issued the server token with `bind_uid="user_42"`, compare the result with the user you expect:

```python
result = captchala.validate(token)
if result.valid and result.uid != expected_user_id:
    ...  # pass token was issued for a different user: reject
```

Or send the identity at validate and check `result.binding_mismatch`.

### `client.issue_server_token(action, **options) -> IssueResult`

Mint a one-time `sct_` server token. Hand it to the client SDK as `serverToken`.

| Option | Description |
|---|---|
| `bind_ip` | End-user IP. A challenge started from another network may be rejected |
| `ttl` | Lifetime in seconds (server default 300, max 900) |
| `max_uses` | How many pass flows the token may be used for (server default 10) |
| `bind_uid` | Your user ID; echoed by validate as `uid` |
| `bind_account`, `bind_email`, `bind_phone`, `scene` | End-user identity |
| `bind_device_id`, `bind_fingerprint` | Bind to a device id / browser fingerprint |

```python
issue = captchala.issue_server_token("login", bind_uid=str(user.id), ttl=300)
if not issue.ok:
    return {"error": issue.error}, 503   # rate_limit_exceeded, ...
return {"server_token": issue.token}
```

`IssueResult`: `ok`, `token`, `expires_in`, `issued_at`, `error`, `message`, `http_status`, `retry_after`, `retryable`, `cause`.

### `client.moderation_check(input, user_id=None)` / `client.moderation_text(text, user_id=None)`

Multi-modal content moderation. `input` is a list of OpenAI-compatible items; use the `text_item()` / `image_url_item()` helpers.

```python
from captchala import text_item, image_url_item

m = captchala.moderation_check([text_item(comment), image_url_item(upload_url)], user_id=str(user.id))
if m.ok and m.flagged and m.has_category("violence", "csam"):
    ...  # hard block

t = captchala.moderation_text("user comment here")
```

`ModerationResult`: `ok`, `flagged`, `categories`, `category_scores`, `content_type`, `raw`, `error`, `message`, `has_category(*names)`. Categories depend on the model, so iterate them defensively.

### `user_message(code)`

A short, user-safe English message for an error code, for form errors (`"CAPTCHA expired or was already used. Please refresh and try again."`). Never show raw codes to end users. Unknown codes fall back to a generic message.

## Errors, retries and timeouts

Methods return a result and do not raise for verification, API or network failures. `result.error` is a short code. `result.cause` holds a typed exception when the failure came from the transport or the API:

| Class | When |
|---|---|
| `NetworkError` (`connect_failed`) | DNS failure, connection refused / reset |
| `RequestTimeoutError` (subclass of `NetworkError`) | No answer within `timeout` |
| `AuthenticationError` | Wrong or missing app key / secret |
| `RateLimitError` | Rate limit or quota; see `retry_after` |
| `InvalidResponseError` | Body was not the expected JSON |
| `APIError` | Any other API error (base class of the three above) |
| `ValidationFailedError` | Raised by `result.raise_if_invalid()` |

All derive from `CaptchaLaError` and carry `code`.

Retries use exponential backoff with jitter. Connection failures and HTTP 502 / 503 are always retried. Timeouts, connection resets and HTTP 504 are retried for `validate` and `issue_server_token`, but not for moderation, where the content may already be processing. Rate-limit answers (HTTP 429) are not retried. Note that a pass token is single-use: if a first attempt reached the API and was consumed before the connection dropped, the retry reports `token_already_used`. It fails closed.

## Django

```python
# settings.py
CAPTCHALA_APP_KEY = "..."
CAPTCHALA_APP_SECRET = "..."
# optional: CAPTCHALA_BASE_URL, CAPTCHALA_TIMEOUT, CAPTCHALA_REJECT_CLIENT_ONLY
```

Form field. `cleaned_data` holds the `ValidateResult`; errors use `user_message()` texts and the API error code as the `ValidationError` code:

```python
from django import forms
from captchala.contrib.django import CaptchaLaField, CaptchaLaFormMixin

class LoginForm(CaptchaLaFormMixin, forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)
    captcha_token = CaptchaLaField(expected_action="login")

form = LoginForm(request.POST, request=request)   # request= forwards the client IP
if form.is_valid():
    result = form.cleaned_data["captcha_token"]
```

View decorator, for sync and async views:

```python
from captchala.contrib.django import captchala_required

@captchala_required(action="login")
def login_view(request):
    request.captchala  # ValidateResult
    ...
```

On failure it returns HTTP 400 `{"error": "captcha_failed", "code": "<error code>"}`, or whatever `on_failure(request, result)` returns. Other options: `hostname`, `fields`, `allow_degraded`, `client`. `verify_request(request, ...)` returns the result without a decorator.

## Flask

```python
from flask import Flask, g
from captchala.contrib.flask import CaptchaLa

app = Flask(__name__)
app.config.update(CAPTCHALA_APP_KEY="...", CAPTCHALA_APP_SECRET="...")
captcha = CaptchaLa(app)   # or captcha.init_app(app)

@app.post("/login")
@captcha.required(action="login")
def login():
    g.captchala  # ValidateResult
    ...
```

On failure it returns HTTP 400 `{"error": "captcha_failed", "code": "<error code>"}`, or `on_failure(result)`. `captcha.verify(action=...)` validates the current request yourself. Async views are supported with `flask[async]`.

The helpers read the token from the `captcha_token` (or `captchala_token`) form / JSON field, then from the `X-Captcha-Token` header. They pass the end-user IP from `CF-Connecting-IP`, the first `X-Forwarded-For` entry, `X-Real-IP` or the remote address. Anyone can set these headers when your app is not behind a proxy that overwrites them. The IP is only an extra risk signal.

## Token Types

| Prefix | Source | Handling |
|---|---|---|
| `pt_` | Main API | Verified by `validate()` |
| `offline_` | Backup service, during a service disruption | Verified automatically against the backup service; `offline=True` |
| `dg_` | Main API, degraded (quota exhausted) | `valid` is always `False`; check `degraded` and decide yourself |
| `client_` | Client-only placeholder (native SDKs) | See below |
| `co_` | Client-only placeholder (web SDK) | See below |

### Degraded tokens

When an app's quota is exhausted the client SDK completes with a `dg_` token so your users are not blocked. `valid` stays `False`. To keep the flow open while you upgrade:

```python
if result.valid or result.degraded:
    ...  # allow
```

The Django / Flask helpers do this with `allow_degraded=True`.

### Client-only tokens (`client_` / `co_`)

The client SDK mints these only when it could reach neither the API nor the backup service. They carry no signature, so the SDK accepts one only if your server cannot reach the API either:

1. It probes the API (2 s timeout). Any HTTP answer means there is no outage: `valid=False`, `client_only=True`, `error="client_only_rejected_api_reachable"`.
2. Otherwise it probes the backup service the same way.
3. Only when both are unreachable: `valid=True`, `client_only=True`, `offline=True`, with a `warning`.

Probe results are cached per process (30 s when reachable, 5 s when not), and concurrent validations share one probe. For sensitive actions (login, payment) refuse them even during an outage:

```python
strict = Client(reject_client_only=True)
# client_ / co_ -> valid=False, error="client_only_rejected_by_policy"
```

## Testing your integration

The API provides public test keys that always pass or always fail, without solving a CAPTCHA. See [Test keys](https://docs.captcha.la/api-reference#test-keys). Results from them have `test == True`. Never configure them in production.

In unit tests, inject a transport (sync) or an httpx mock transport (async):

```python
import json
from captchala import Client

def fake(url, body, headers, timeout):
    return 200, {}, json.dumps({"code": 0, "data": {"valid": True, "action": "login"}}).encode()

client = Client("k", "s", transport=fake)
```

```python
import httpx
from captchala import AsyncClient

mock = httpx.MockTransport(lambda req: httpx.Response(200, json={"code": 0, "data": {"valid": True}}))
client = AsyncClient("k", "s", http_client=httpx.AsyncClient(transport=mock))
```

## Development

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
CAPTCHALA_APP_KEY=xxx CAPTCHALA_APP_SECRET=xxx .venv/bin/python scripts/live_smoke.py   # live check, no real challenge
```

## License

MIT
