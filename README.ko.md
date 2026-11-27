# CaptchaLa Python SDK

[English](https://github.com/Captcha-La/captchala-python/blob/main/README.md) · [简体中文](https://github.com/Captcha-La/captchala-python/blob/main/README_zh.md) · [日本語](https://github.com/Captcha-La/captchala-python/blob/main/README.ja.md) · **한국어** · [Español](https://github.com/Captcha-La/captchala-python/blob/main/README.es.md) · [Português (BR)](https://github.com/Captcha-La/captchala-python/blob/main/README.pt-BR.md) · [Deutsch](https://github.com/Captcha-La/captchala-python/blob/main/README.de.md)

Python에서 CaptchaLa 토큰을 검증하기 위한 서버 사이드 SDK입니다. 동기 및 비동기 클라이언트를 제공하고, 타입이 지정되어 있으며, Django와 Flask 헬퍼를 선택적으로 사용할 수 있습니다.

- [웹사이트](https://captcha.la)
- [문서](https://docs.captcha.la/sdk/server-python)
- [Web SDK 문서](https://docs.captcha.la/web-sdk)
- [대시보드](https://dash.captcha.la)

## 설치

```bash
pip install captchala             # sync client, no dependencies
pip install "captchala[async]"    # + AsyncClient (httpx)
pip install "captchala[django]"   # + Django helpers
pip install "captchala[flask]"    # + Flask helpers
```

**Python 3.9 이상**이 필요합니다. 동기 클라이언트는 표준 라이브러리만 사용합니다.

## 빠른 시작

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

비동기:

```python
from captchala import AsyncClient

async with AsyncClient() as captchala:
    result = await captchala.validate(token, client_ip=user_ip)
```

## API 레퍼런스

### `Client(app_key=None, app_secret=None, **options)` / `AsyncClient(...)`

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `app_key` | `$CAPTCHALA_APP_KEY` | App Key (대시보드에서 발급) |
| `app_secret` | `$CAPTCHALA_APP_SECRET` | App Secret (대시보드에서 발급). 서버 측에서만 사용 |
| `timeout` | `5.0` | 시도당 타임아웃(초) |
| `max_retries` | `2` | 첫 시도 이후의 재시도 횟수 (`0`이면 비활성화) |
| `retry_backoff` | `0.2` | 지수 백오프의 기본 지연 시간(초) |
| `reject_client_only` | `False` | 클라이언트 전용 토큰을 항상 거부합니다. 아래 참조 |
| `headers` | `None` | 모든 요청에 함께 보내는 추가 헤더 |
| `transport` | urllib | *(동기)* 사용자 정의 transport 호출 객체. [테스트](#testing-your-integration) 참조 |
| `http_client` | 새 `httpx.AsyncClient` | *(비동기)* 직접 만든 httpx 클라이언트를 공유 |

키 또는 시크릿이 없으면 `ConfigurationError`가 발생합니다. 클라이언트는 하나만 만들어 재사용하세요. `Client`는 스레드 안전합니다. `AsyncClient`는 `await client.aclose()` 또는 `async with`로 닫습니다.

### `client.validate(token, **options) -> ValidateResult`

클라이언트 SDK에서 받은 pass token을 검증합니다. 토큰이 유효하지 않거나 API 오류, 네트워크 장애가 발생해도 예외를 던지지 않습니다. `result.valid`와 `result.error`를 확인하세요.

| 옵션 | 설명 |
|---|---|
| `client_ip` | *(선택, 권장)* 수신한 요청에서 얻은 최종 사용자의 IP. 추가 위험 검사에 사용됩니다 |
| `keep_token` | `True` = 토큰을 소비하지 않고 검사 (기본값 `False`) |
| `expected_action` | 기대하는 액션(예: `"login"`). 다른 액션용으로 발급된 토큰은 `action_mismatch`로 실패합니다 |
| `expected_hostname` | 기대하는 호스트 이름(웹) 또는 패키지 / 번들 ID(네이티브). 문자열이나 리스트로 지정합니다. `*.example.com`은 모든 서브도메인과 일치합니다. 불일치 시: `hostname_mismatch` |
| `bind_uid`, `bind_account`, `bind_email`, `bind_phone`, `scene` | 최종 사용자 신원 정보. 발급 시 바인딩된 신원과 비교됩니다 (`binding_match` 참조) |

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

| 속성 | 타입 | 설명 |
|---|---|---|
| `valid` | `bool` | 검증 통과 여부. 통과/차단 판단에 사용할 유일한 필드입니다 |
| `error` | `str \| None` | 오류 코드(예: `token_expired`, `action_mismatch`, `request_failed`) |
| `message` | `str \| None` | API 수준 오류일 때 사람이 읽을 수 있는 API 메시지 |
| `action` | `str \| None` | 토큰의 비즈니스 액션 |
| `uid` | `str \| None` | 발급 시 `bind_uid`로 바인딩된 사용자 ID |
| `challenge_id` | `str \| None` | 챌린지 ID |
| `hostname` | `str \| None` | 챌린지를 푼 위치(호스트 이름 또는 패키지 ID) |
| `challenge_ts` | `str \| None` | 풀이 시각, ISO 8601 UTC |
| `risk_level` | `str \| None` | `low` / `medium` / `high` / `critical`. 참고용 |
| `risk_labels` | `tuple[str, ...]` | 대략적인 위험 카테고리(예: `proxy`). 참고용 |
| `captcha_args` | `CaptchaArgs \| None` | 풀이 시점 컨텍스트 에코: `platform`, `user_ip`, `referer`, `pkg`, `solved_at`, `risk_score`. 참고용 |
| `user_ip` | `str \| None` | 풀이 시점에 기록된 최종 사용자 IP. 참고용 |
| `binding` / `binding_match` | | 발급 시 바인딩된 신원과 필드별 비교 결과 |
| `binding_mismatch` | `bool` | `binding_match` 필드 중 하나라도 `False`이면 `True` |
| `degraded` / `degraded_reason` | | 할당량이 소진된 동안 발급된 `dg_` 토큰. 아래 참조 |
| `offline` / `client_only` / `warning` | | 장애 시 폴백. [토큰 유형](#token-types) 참조 |
| `test` | `bool` | 공개 테스트 키에서 나온 응답. 프로덕션에서는 거부하세요 |
| `http_status`, `retry_after`, `retryable` | | 실패 상세 정보 |
| `cause` | `CaptchaLaError \| None` | API / 네트워크 장애에 대한 타입이 지정된 오류 |
| `raw` | `dict \| None` | 원본 `data` 객체 |

메서드: `raise_if_invalid()`는 `valid`가 아니면 `ValidationFailedError`를 발생시킵니다. `to_dict()`.

### `bind_uid` 검증

`bind_uid="user_42"`로 server token을 발급했다면, 결과를 기대하는 사용자와 비교하세요:

```python
result = captchala.validate(token)
if result.valid and result.uid != expected_user_id:
    ...  # pass token was issued for a different user: reject
```

또는 validate 시 신원 정보를 보내고 `result.binding_mismatch`를 확인합니다.

### `client.issue_server_token(action, **options) -> IssueResult`

일회용 `sct_` server token을 발급합니다. 이 토큰을 `serverToken`으로 클라이언트 SDK에 전달하세요.

| 옵션 | 설명 |
|---|---|
| `bind_ip` | 최종 사용자 IP. 다른 네트워크에서 시작된 챌린지는 거부될 수 있습니다 |
| `ttl` | 유효 기간(초. 서버 기본값 300, 최대 900) |
| `max_uses` | 토큰을 사용할 수 있는 pass 흐름 횟수 (서버 기본값 10) |
| `bind_uid` | 서비스의 사용자 ID. validate에서 `uid`로 그대로 반환됩니다 |
| `bind_account`, `bind_email`, `bind_phone`, `scene` | 최종 사용자 신원 정보 |
| `bind_device_id`, `bind_fingerprint` | 디바이스 ID / 브라우저 핑거프린트에 바인딩 |

```python
issue = captchala.issue_server_token("login", bind_uid=str(user.id), ttl=300)
if not issue.ok:
    return {"error": issue.error}, 503   # rate_limit_exceeded, ...
return {"server_token": issue.token}
```

`IssueResult`: `ok`, `token`, `expires_in`, `issued_at`, `error`, `message`, `http_status`, `retry_after`, `retryable`, `cause`.

### `client.moderation_check(input, user_id=None)` / `client.moderation_text(text, user_id=None)`

멀티모달 콘텐츠 모더레이션입니다. `input`은 OpenAI 호환 항목의 리스트이며, `text_item()` / `image_url_item()` 헬퍼를 사용하세요.

```python
from captchala import text_item, image_url_item

m = captchala.moderation_check([text_item(comment), image_url_item(upload_url)], user_id=str(user.id))
if m.ok and m.flagged and m.has_category("violence", "csam"):
    ...  # hard block

t = captchala.moderation_text("user comment here")
```

`ModerationResult`: `ok`, `flagged`, `categories`, `category_scores`, `content_type`, `raw`, `error`, `message`, `has_category(*names)`. 카테고리는 모델에 따라 다르므로 방어적으로 순회하세요.

### `user_message(code)`

오류 코드에 대한 짧고 사용자에게 보여줘도 안전한 영어 메시지로, 폼 오류 표시에 사용합니다(`"CAPTCHA expired or was already used. Please refresh and try again."`). 원본 코드를 최종 사용자에게 보여주지 마세요. 알 수 없는 코드는 일반 메시지로 대체됩니다.

## 오류, 재시도, 타임아웃

메서드는 결과 객체를 반환하며 검증, API, 네트워크 실패에 대해 예외를 던지지 않습니다. `result.error`는 짧은 코드입니다. 실패가 transport 또는 API에서 발생한 경우 `result.cause`에 타입이 지정된 예외가 담깁니다:

| 클래스 | 발생 조건 |
|---|---|
| `NetworkError` (`connect_failed`) | DNS 실패, 연결 거부 / 재설정 |
| `RequestTimeoutError` (`NetworkError`의 하위 클래스) | `timeout` 내에 응답 없음 |
| `AuthenticationError` | App Key / Secret이 잘못되었거나 누락됨 |
| `RateLimitError` | 속도 제한 또는 할당량 초과. `retry_after` 참조 |
| `InvalidResponseError` | 응답 본문이 기대한 JSON이 아님 |
| `APIError` | 그 밖의 모든 API 오류 (위 세 클래스의 기본 클래스) |
| `ValidationFailedError` | `result.raise_if_invalid()`가 발생시킴 |

모두 `CaptchaLaError`를 상속하며 `code`를 가집니다.

재시도는 지터가 포함된 지수 백오프를 사용합니다. 연결 실패와 HTTP 502 / 503은 항상 재시도합니다. 타임아웃, 연결 재설정, HTTP 504는 `validate`와 `issue_server_token`에서는 재시도하지만, 콘텐츠가 이미 처리 중일 수 있는 모더레이션에서는 재시도하지 않습니다. 속도 제한 응답(HTTP 429)은 재시도하지 않습니다. pass token은 일회용이라는 점에 유의하세요. 첫 시도가 API에 도달해 토큰이 소비된 뒤 연결이 끊겼다면, 재시도는 `token_already_used`를 보고합니다. 즉 안전하게 실패(거부)합니다.

## Django

```python
# settings.py
CAPTCHALA_APP_KEY = "..."
CAPTCHALA_APP_SECRET = "..."
# optional: CAPTCHALA_TIMEOUT, CAPTCHALA_REJECT_CLIENT_ONLY
```

폼 필드. `cleaned_data`에는 `ValidateResult`가 담깁니다. 오류에는 `user_message()` 텍스트가 사용되고, API 오류 코드가 `ValidationError`의 code가 됩니다:

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

뷰 데코레이터(동기 및 비동기 뷰 모두 지원):

```python
from captchala.contrib.django import captchala_required

@captchala_required(action="login")
def login_view(request):
    request.captchala  # ValidateResult
    ...
```

실패하면 HTTP 400 `{"error": "captcha_failed", "code": "<error code>"}` 또는 `on_failure(request, result)`의 반환값을 응답합니다. 기타 옵션: `hostname`, `fields`, `allow_degraded`, `client`. `verify_request(request, ...)`는 데코레이터 없이 결과를 반환합니다.

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

실패하면 HTTP 400 `{"error": "captcha_failed", "code": "<error code>"}` 또는 `on_failure(result)`의 반환값을 응답합니다. `captcha.verify(action=...)`로 현재 요청을 직접 검증할 수 있습니다. `flask[async]`를 사용하면 비동기 뷰도 지원됩니다.

헬퍼는 `captcha_token`(또는 `captchala_token`) 폼 / JSON 필드에서 토큰을 읽고, 없으면 `X-Captcha-Token` 헤더에서 읽습니다. 최종 사용자 IP는 `CF-Connecting-IP`, `X-Forwarded-For`의 첫 번째 항목, `X-Real-IP`, 또는 원격 주소에서 가져와 전달합니다. 앱이 이러한 헤더를 덮어쓰는 프록시 뒤에 있지 않다면 누구나 이 헤더를 설정할 수 있습니다. IP는 추가적인 위험 신호일 뿐입니다.

<a id="token-types"></a>
## 토큰 유형

| 접두사 | 출처 | 처리 방식 |
|---|---|---|
| `pt_` | 메인 API | `validate()`로 검증 |
| `offline_` | 백업 서비스, 서비스 장애 중 | 백업 서비스에 대해 자동으로 검증. `offline=True` |
| `dg_` | 메인 API, 성능 저하 모드(할당량 소진) | `valid`는 항상 `False`. `degraded`를 확인하고 직접 판단 |
| `client_` | 클라이언트 전용 플레이스홀더(네이티브 SDK) | 아래 참조 |
| `co_` | 클라이언트 전용 플레이스홀더(웹 SDK) | 아래 참조 |

### 성능 저하(degraded) 토큰

앱의 할당량이 소진되면 사용자가 차단되지 않도록 클라이언트 SDK가 `dg_` 토큰으로 완료합니다. `valid`는 `False`로 유지됩니다. 업그레이드하는 동안 흐름을 열어 두려면:

```python
if result.valid or result.degraded:
    ...  # allow
```

Django / Flask 헬퍼에서는 `allow_degraded=True`로 같은 동작을 합니다.

### 클라이언트 전용 토큰 (`client_` / `co_`)

클라이언트 SDK는 API와 백업 서비스 모두에 도달하지 못했을 때만 이 토큰을 발급합니다. 서명이 없으므로, SDK는 서버에서도 API에 도달할 수 없는 경우에만 이를 받아들입니다:

1. API를 프로브합니다(타임아웃 2초). 어떤 HTTP 응답이든 있으면 장애가 아니라는 뜻입니다: `valid=False`, `client_only=True`, `error="client_only_rejected_api_reachable"`.
2. 그렇지 않으면 같은 방식으로 백업 서비스를 프로브합니다.
3. 둘 다 도달할 수 없을 때만: `valid=True`, `client_only=True`, `offline=True`이며 `warning`이 함께 반환됩니다.

프로브 결과는 프로세스별로 캐시되며(도달 가능하면 30초, 불가능하면 5초), 동시에 진행되는 검증은 하나의 프로브를 공유합니다. 민감한 액션(로그인, 결제)에서는 장애 중에도 이 토큰을 거부하세요:

```python
strict = Client(reject_client_only=True)
# client_ / co_ -> valid=False, error="client_only_rejected_by_policy"
```

<a id="testing-your-integration"></a>
## 연동 테스트

API는 CAPTCHA를 풀지 않아도 항상 통과하거나 항상 실패하는 공개 테스트 키를 제공합니다. [테스트 키](https://docs.captcha.la/api-reference#test-keys)를 참조하세요. 이 키로 얻은 결과는 `test == True`입니다. 프로덕션에는 절대 설정하지 마세요.

단위 테스트에서는 transport(동기) 또는 httpx 모의 transport(비동기)를 주입합니다:

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

## 개발

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
CAPTCHALA_APP_KEY=xxx CAPTCHALA_APP_SECRET=xxx .venv/bin/python scripts/live_smoke.py   # live check, no real challenge
```

## 라이선스

MIT
