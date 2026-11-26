# CaptchaLa Python SDK

[English](https://github.com/Captcha-La/captchala-python/blob/main/README.md) · [简体中文](https://github.com/Captcha-La/captchala-python/blob/main/README_zh.md) · [日本語](https://github.com/Captcha-La/captchala-python/blob/main/README.ja.md) · [한국어](https://github.com/Captcha-La/captchala-python/blob/main/README.ko.md) · **Español** · [Português (BR)](https://github.com/Captcha-La/captchala-python/blob/main/README.pt-BR.md) · [Deutsch](https://github.com/Captcha-La/captchala-python/blob/main/README.de.md)

SDK de servidor para validar tokens de CaptchaLa desde Python. Clientes síncrono y asíncrono, con tipos, y helpers opcionales para Django y Flask.

- [Sitio web](https://captcha.la)
- [Documentación](https://docs.captcha.la/sdk/server-python)
- [Documentación del Web SDK](https://docs.captcha.la/web-sdk)
- [Panel de control](https://dash.captcha.la)

## Instalación

```bash
pip install captchala             # sync client, no dependencies
pip install "captchala[async]"    # + AsyncClient (httpx)
pip install "captchala[django]"   # + Django helpers
pip install "captchala[flask]"    # + Flask helpers
```

Requiere **Python 3.9+**. El cliente síncrono solo usa la biblioteca estándar.

## Inicio rápido

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

Asíncrono:

```python
from captchala import AsyncClient

async with AsyncClient() as captchala:
    result = await captchala.validate(token, client_ip=user_ip)
```

## Referencia de la API

### `Client(app_key=None, app_secret=None, **options)` / `AsyncClient(...)`

| Opción | Valor predeterminado | Descripción |
|---|---|---|
| `app_key` | `$CAPTCHALA_APP_KEY` | App Key (del panel de control) |
| `app_secret` | `$CAPTCHALA_APP_SECRET` | App Secret (del panel de control). Solo en el servidor |
| `base_url` | `https://verify.captcha.la` | URL base de la API |
| `timeout` | `5.0` | Tiempo de espera por intento, en segundos |
| `max_retries` | `2` | Reintentos tras el primer intento (`0` los desactiva) |
| `retry_backoff` | `0.2` | Retardo base del backoff exponencial, en segundos |
| `reject_client_only` | `False` | Rechazar siempre los tokens solo de cliente, ver más abajo |
| `headers` | `None` | Cabeceras adicionales enviadas en cada solicitud |
| `transport` | urllib | *(síncrono)* Callable de transporte personalizado, ver [Pruebas](#testing-your-integration) |
| `http_client` | nuevo `httpx.AsyncClient` | *(asíncrono)* Comparte tu propio cliente httpx |

Lanza `ConfigurationError` si falta la clave o el secreto. Crea un único cliente y reutilízalo; `Client` es thread-safe. Cierra un `AsyncClient` con `await client.aclose()` o con `async with`.

### `client.validate(token, **options) -> ValidateResult`

Valida un pass token recibido del SDK de cliente. Nunca lanza excepciones por tokens inválidos, errores de la API ni fallos de red. Comprueba `result.valid` y `result.error`.

| Opción | Descripción |
|---|---|
| `client_ip` | *(opcional, recomendado)* La IP del usuario final tomada de tu solicitud entrante. Se usa para comprobaciones de riesgo adicionales |
| `keep_token` | `True` = comprobar sin consumir el token (por defecto `False`) |
| `expected_action` | La acción que esperas, p. ej. `"login"`. Un token emitido para otra acción falla con `action_mismatch` |
| `expected_hostname` | El hostname (web) o el package / bundle id (nativo) que esperas, como cadena o lista. `*.example.com` coincide con cualquier subdominio. Si no coincide: `hostname_mismatch` |
| `bind_uid`, `bind_account`, `bind_email`, `bind_phone`, `scene` | Identidad del usuario final, comparada con la identidad vinculada al emitir (ver `binding_match`) |

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

| Atributo | Tipo | Descripción |
|---|---|---|
| `valid` | `bool` | Si la validación se superó. Es el único campo en el que basar la decisión |
| `error` | `str \| None` | Código de error, p. ej. `token_expired`, `action_mismatch`, `request_failed` |
| `message` | `str \| None` | Mensaje legible de la API, para errores a nivel de API |
| `action` | `str \| None` | Acción de negocio del token |
| `uid` | `str \| None` | ID de usuario vinculado mediante `bind_uid` al emitir |
| `challenge_id` | `str \| None` | ID del desafío |
| `hostname` | `str \| None` | Dónde se resolvió el desafío (hostname o package id) |
| `challenge_ts` | `str \| None` | Momento de la resolución, ISO 8601 UTC |
| `risk_level` | `str \| None` | `low` / `medium` / `high` / `critical`. Informativo |
| `risk_labels` | `tuple[str, ...]` | Categorías de riesgo generales, p. ej. `proxy`. Informativo |
| `captcha_args` | `CaptchaArgs \| None` | Eco del contexto de resolución: `platform`, `user_ip`, `referer`, `pkg`, `solved_at`, `risk_score`. Informativo |
| `user_ip` | `str \| None` | IP del usuario final registrada al resolver. Informativo |
| `binding` / `binding_match` | | Identidad vinculada al emitir y la comparación campo por campo |
| `binding_mismatch` | `bool` | `True` cuando algún campo de `binding_match` es `False` |
| `degraded` / `degraded_reason` | | Token `dg_` emitido con la cuota agotada, ver más abajo |
| `offline` / `client_only` / `warning` | | Alternativas ante caídas del servicio, ver [Tipos de token](#token-types) |
| `test` | `bool` | Respuesta de una clave de prueba pública. Recházala en producción |
| `http_status`, `retry_after`, `retryable` | | Detalles del fallo |
| `cause` | `CaptchaLaError \| None` | Error tipado para fallos de API / red |
| `raw` | `dict \| None` | El objeto `data` sin procesar |

Métodos: `raise_if_invalid()` lanza `ValidationFailedError` salvo que `valid`; `to_dict()`.

### Verificar `bind_uid`

Si emitiste el server token con `bind_uid="user_42"`, compara el resultado con el usuario que esperas:

```python
result = captchala.validate(token)
if result.valid and result.uid != expected_user_id:
    ...  # pass token was issued for a different user: reject
```

O envía la identidad al validar y comprueba `result.binding_mismatch`.

### `client.issue_server_token(action, **options) -> IssueResult`

Genera un server token `sct_` de un solo uso. Pásalo al SDK de cliente como `serverToken`.

| Opción | Descripción |
|---|---|
| `bind_ip` | IP del usuario final. Un desafío iniciado desde otra red puede ser rechazado |
| `ttl` | Vida útil en segundos (por defecto en el servidor 300, máximo 900) |
| `max_uses` | En cuántos flujos de pass se puede usar el token (por defecto en el servidor 10) |
| `bind_uid` | Tu ID de usuario; validate lo devuelve como `uid` |
| `bind_account`, `bind_email`, `bind_phone`, `scene` | Identidad del usuario final |
| `bind_device_id`, `bind_fingerprint` | Vincular a un device id / huella digital del navegador |

```python
issue = captchala.issue_server_token("login", bind_uid=str(user.id), ttl=300)
if not issue.ok:
    return {"error": issue.error}, 503   # rate_limit_exceeded, ...
return {"server_token": issue.token}
```

`IssueResult`: `ok`, `token`, `expires_in`, `issued_at`, `error`, `message`, `http_status`, `retry_after`, `retryable`, `cause`.

### `client.moderation_check(input, user_id=None)` / `client.moderation_text(text, user_id=None)`

Moderación de contenido multimodal. `input` es una lista de elementos compatibles con OpenAI; usa los helpers `text_item()` / `image_url_item()`.

```python
from captchala import text_item, image_url_item

m = captchala.moderation_check([text_item(comment), image_url_item(upload_url)], user_id=str(user.id))
if m.ok and m.flagged and m.has_category("violence", "csam"):
    ...  # hard block

t = captchala.moderation_text("user comment here")
```

`ModerationResult`: `ok`, `flagged`, `categories`, `category_scores`, `content_type`, `raw`, `error`, `message`, `has_category(*names)`. Las categorías dependen del modelo, así que recórrelas de forma defensiva.

### `user_message(code)`

Un mensaje breve en inglés, seguro para mostrar al usuario, para un código de error; pensado para errores de formulario (`"CAPTCHA expired or was already used. Please refresh and try again."`). Nunca muestres los códigos sin procesar a los usuarios finales. Los códigos desconocidos usan un mensaje genérico.

## Errores, reintentos y tiempos de espera

Los métodos devuelven un resultado y no lanzan excepciones por fallos de verificación, de la API ni de red. `result.error` es un código corto. `result.cause` contiene una excepción tipada cuando el fallo vino del transporte o de la API:

| Clase | Cuándo |
|---|---|
| `NetworkError` (`connect_failed`) | Fallo de DNS, conexión rechazada / restablecida |
| `RequestTimeoutError` (subclase de `NetworkError`) | Sin respuesta dentro de `timeout` |
| `AuthenticationError` | App key / secret incorrectos o ausentes |
| `RateLimitError` | Límite de tasa o cuota; ver `retry_after` |
| `InvalidResponseError` | El cuerpo no era el JSON esperado |
| `APIError` | Cualquier otro error de la API (clase base de las tres anteriores) |
| `ValidationFailedError` | Lanzada por `result.raise_if_invalid()` |

Todas derivan de `CaptchaLaError` y llevan `code`.

Los reintentos usan backoff exponencial con jitter. Los fallos de conexión y los HTTP 502 / 503 siempre se reintentan. Los tiempos de espera agotados, las conexiones restablecidas y los HTTP 504 se reintentan en `validate` e `issue_server_token`, pero no en la moderación, donde el contenido puede estar ya procesándose. Las respuestas de límite de tasa (HTTP 429) no se reintentan. Ten en cuenta que un pass token es de un solo uso: si un primer intento llegó a la API y consumió el token antes de que se cortara la conexión, el reintento informa `token_already_used`. Falla de forma segura (rechaza).

## Django

```python
# settings.py
CAPTCHALA_APP_KEY = "..."
CAPTCHALA_APP_SECRET = "..."
# optional: CAPTCHALA_BASE_URL, CAPTCHALA_TIMEOUT, CAPTCHALA_REJECT_CLIENT_ONLY
```

Campo de formulario. `cleaned_data` contiene el `ValidateResult`; los errores usan los textos de `user_message()` y el código de error de la API como código del `ValidationError`:

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

Decorador de vista, para vistas síncronas y asíncronas:

```python
from captchala.contrib.django import captchala_required

@captchala_required(action="login")
def login_view(request):
    request.captchala  # ValidateResult
    ...
```

Si falla, devuelve HTTP 400 `{"error": "captcha_failed", "code": "<error code>"}`, o lo que devuelva `on_failure(request, result)`. Otras opciones: `hostname`, `fields`, `allow_degraded`, `client`. `verify_request(request, ...)` devuelve el resultado sin decorador.

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

Si falla, devuelve HTTP 400 `{"error": "captcha_failed", "code": "<error code>"}`, o `on_failure(result)`. `captcha.verify(action=...)` te permite validar tú mismo la solicitud actual. Las vistas asíncronas son compatibles con `flask[async]`.

Los helpers leen el token del campo de formulario / JSON `captcha_token` (o `captchala_token`) y, si no está, de la cabecera `X-Captcha-Token`. Pasan la IP del usuario final tomada de `CF-Connecting-IP`, la primera entrada de `X-Forwarded-For`, `X-Real-IP` o la dirección remota. Cualquiera puede establecer estas cabeceras si tu aplicación no está detrás de un proxy que las sobrescriba. La IP es solo una señal de riesgo adicional.

<a id="token-types"></a>
## Tipos de token

| Prefijo | Origen | Tratamiento |
|---|---|---|
| `pt_` | API principal | Verificado por `validate()` |
| `offline_` | Servicio de respaldo, durante una interrupción del servicio | Se verifica automáticamente contra el servicio de respaldo; `offline=True` |
| `dg_` | API principal, modo degradado (cuota agotada) | `valid` siempre es `False`; comprueba `degraded` y decide tú |
| `client_` | Marcador solo de cliente (SDK nativos) | Ver más abajo |
| `co_` | Marcador solo de cliente (Web SDK) | Ver más abajo |

### Tokens degradados

Cuando la cuota de una aplicación se agota, el SDK de cliente termina con un token `dg_` para que tus usuarios no queden bloqueados. `valid` sigue siendo `False`. Para mantener el flujo abierto mientras actualizas tu plan:

```python
if result.valid or result.degraded:
    ...  # allow
```

Los helpers de Django / Flask hacen esto con `allow_degraded=True`.

### Tokens solo de cliente (`client_` / `co_`)

El SDK de cliente solo los genera cuando no pudo llegar ni a la API ni al servicio de respaldo. No llevan firma, así que el SDK solo los acepta si tu servidor tampoco puede llegar a la API:

1. Sondea la API (tiempo de espera de 2 s). Cualquier respuesta HTTP significa que no hay interrupción: `valid=False`, `client_only=True`, `error="client_only_rejected_api_reachable"`.
2. Si no, sondea el servicio de respaldo de la misma forma.
3. Solo cuando ambos son inalcanzables: `valid=True`, `client_only=True`, `offline=True`, con un `warning`.

Los resultados del sondeo se almacenan en caché por proceso (30 s si es alcanzable, 5 s si no), y las validaciones concurrentes comparten un mismo sondeo. Para acciones sensibles (inicio de sesión, pagos), recházalos incluso durante una interrupción:

```python
strict = Client(reject_client_only=True)
# client_ / co_ -> valid=False, error="client_only_rejected_by_policy"
```

<a id="testing-your-integration"></a>
## Probar tu integración

La API ofrece claves de prueba públicas que siempre aprueban o siempre fallan, sin resolver un CAPTCHA. Consulta [Claves de prueba](https://docs.captcha.la/api-reference#test-keys). Sus resultados tienen `test == True`. Nunca las configures en producción.

En las pruebas unitarias, inyecta un transporte (síncrono) o un transporte simulado de httpx (asíncrono):

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

## Desarrollo

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
CAPTCHALA_APP_KEY=xxx CAPTCHALA_APP_SECRET=xxx .venv/bin/python scripts/live_smoke.py   # live check, no real challenge
```

## Licencia

MIT
