# CaptchaLa Python SDK

[English](https://github.com/Captcha-La/captchala-python/blob/main/README.md) · [简体中文](https://github.com/Captcha-La/captchala-python/blob/main/README_zh.md) · [日本語](https://github.com/Captcha-La/captchala-python/blob/main/README.ja.md) · [한국어](https://github.com/Captcha-La/captchala-python/blob/main/README.ko.md) · [Español](https://github.com/Captcha-La/captchala-python/blob/main/README.es.md) · [Português (BR)](https://github.com/Captcha-La/captchala-python/blob/main/README.pt-BR.md) · **Deutsch**

Serverseitiges SDK zur Validierung von CaptchaLa-Tokens in Python. Synchroner und asynchroner Client, vollständig typisiert, mit optionalen Helfern für Django und Flask.

- [Website](https://captcha.la)
- [Dokumentation](https://docs.captcha.la/sdk/server-python)
- [Web-SDK-Dokumentation](https://docs.captcha.la/web-sdk)
- [Dashboard](https://dash.captcha.la)

## Installation

```bash
pip install captchala             # sync client, no dependencies
pip install "captchala[async]"    # + AsyncClient (httpx)
pip install "captchala[django]"   # + Django helpers
pip install "captchala[flask]"    # + Flask helpers
```

Erfordert **Python 3.9+**. Der synchrone Client nutzt nur die Standardbibliothek.

## Schnellstart

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

Asynchron:

```python
from captchala import AsyncClient

async with AsyncClient() as captchala:
    result = await captchala.validate(token, client_ip=user_ip)
```

## API-Referenz

### `Client(app_key=None, app_secret=None, **options)` / `AsyncClient(...)`

| Option | Standard | Beschreibung |
|---|---|---|
| `app_key` | `$CAPTCHALA_APP_KEY` | App Key (aus dem Dashboard) |
| `app_secret` | `$CAPTCHALA_APP_SECRET` | App Secret (aus dem Dashboard). Nur serverseitig verwenden |
| `timeout` | `5.0` | Timeout pro Versuch in Sekunden |
| `max_retries` | `2` | Wiederholungen nach dem ersten Versuch (`0` deaktiviert sie) |
| `retry_backoff` | `0.2` | Basisverzögerung für exponentielles Backoff in Sekunden |
| `reject_client_only` | `False` | Reine Client-Tokens immer ablehnen, siehe unten |
| `headers` | `None` | Zusätzliche Header, die bei jeder Anfrage gesendet werden |
| `transport` | urllib | *(sync)* Eigenes Transport-Callable, siehe [Tests](#testing-your-integration) |
| `http_client` | neuer `httpx.AsyncClient` | *(async)* Eigenen httpx-Client gemeinsam nutzen |

Wirft `ConfigurationError`, wenn Key oder Secret fehlt. Erstellen Sie einen Client und verwenden Sie ihn wieder; `Client` ist threadsicher. Einen `AsyncClient` schließen Sie mit `await client.aclose()` oder `async with`.

### `client.validate(token, **options) -> ValidateResult`

Validiert einen pass token aus dem Client-SDK. Bei ungültigen Tokens, API-Fehlern oder Netzwerkausfällen wird nie eine Exception geworfen. Prüfen Sie `result.valid` und `result.error`.

| Option | Beschreibung |
|---|---|
| `client_ip` | *(optional, empfohlen)* Die IP des Endnutzers aus Ihrer eingehenden Anfrage. Wird für zusätzliche Risikoprüfungen verwendet |
| `keep_token` | `True` = prüfen, ohne den Token zu verbrauchen (Standard `False`) |
| `expected_action` | Die erwartete Aktion, z. B. `"login"`. Ein für eine andere Aktion ausgestellter Token schlägt mit `action_mismatch` fehl |
| `expected_hostname` | Erwarteter Hostname (Web) oder Package- / Bundle-ID (nativ), als String oder Liste. `*.example.com` passt auf jede Subdomain. Abweichung: `hostname_mismatch` |
| `bind_uid`, `bind_account`, `bind_email`, `bind_phone`, `scene` | Identität des Endnutzers, verglichen mit der bei der Ausstellung gebundenen Identität (siehe `binding_match`) |

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

| Attribut | Typ | Beschreibung |
|---|---|---|
| `valid` | `bool` | Ob die Validierung bestanden wurde. Das einzige Feld, auf das Sie die Entscheidung stützen sollten |
| `error` | `str \| None` | Fehlercode, z. B. `token_expired`, `action_mismatch`, `request_failed` |
| `message` | `str \| None` | Lesbare API-Meldung bei Fehlern auf API-Ebene |
| `action` | `str \| None` | Geschäftsaktion des Tokens |
| `uid` | `str \| None` | Bei der Ausstellung über `bind_uid` gebundene Nutzer-ID |
| `challenge_id` | `str \| None` | Challenge-ID |
| `hostname` | `str \| None` | Wo die Challenge gelöst wurde (Hostname oder Package-ID) |
| `challenge_ts` | `str \| None` | Lösungszeitpunkt, ISO 8601 UTC |
| `risk_level` | `str \| None` | `low` / `medium` / `high` / `critical`. Nur zur Information |
| `risk_labels` | `tuple[str, ...]` | Grobe Risikokategorien, z. B. `proxy`. Nur zur Information |
| `captcha_args` | `CaptchaArgs \| None` | Echo des Lösungskontexts: `platform`, `user_ip`, `referer`, `pkg`, `solved_at`, `risk_score`. Nur zur Information |
| `user_ip` | `str \| None` | Beim Lösen erfasste IP des Endnutzers. Nur zur Information |
| `binding` / `binding_match` | | Bei der Ausstellung gebundene Identität und der Vergleich pro Feld |
| `binding_mismatch` | `bool` | `True`, wenn ein Feld in `binding_match` `False` ist |
| `degraded` / `degraded_reason` | | `dg_`-Token, ausgestellt bei erschöpftem Kontingent, siehe unten |
| `offline` / `client_only` / `warning` | | Ausweichpfade bei Ausfällen, siehe [Token-Typen](#token-types) |
| `test` | `bool` | Antwort von einem öffentlichen Test-Key. In Produktion ablehnen |
| `http_status`, `retry_after`, `retryable` | | Fehlerdetails |
| `cause` | `CaptchaLaError \| None` | Typisierter Fehler bei API- / Netzwerkausfällen |
| `raw` | `dict \| None` | Das rohe `data`-Objekt |

Methoden: `raise_if_invalid()` wirft `ValidationFailedError`, sofern nicht `valid`; `to_dict()`.

### `bind_uid` prüfen

Wenn Sie den server token mit `bind_uid="user_42"` ausgestellt haben, vergleichen Sie das Ergebnis mit dem erwarteten Nutzer:

```python
result = captchala.validate(token)
if result.valid and result.uid != expected_user_id:
    ...  # pass token was issued for a different user: reject
```

Oder senden Sie die Identität beim Validieren mit und prüfen Sie `result.binding_mismatch`.

### `client.issue_server_token(action, **options) -> IssueResult`

Erzeugt einen einmalig verwendbaren `sct_` server token. Übergeben Sie ihn dem Client-SDK als `serverToken`.

| Option | Beschreibung |
|---|---|
| `bind_ip` | IP des Endnutzers. Eine aus einem anderen Netzwerk gestartete Challenge kann abgelehnt werden |
| `ttl` | Gültigkeitsdauer in Sekunden (Server-Standard 300, maximal 900) |
| `max_uses` | Für wie viele pass-Abläufe der Token verwendet werden darf (Server-Standard 10) |
| `bind_uid` | Ihre Nutzer-ID; wird von validate als `uid` zurückgegeben |
| `bind_account`, `bind_email`, `bind_phone`, `scene` | Identität des Endnutzers |
| `bind_device_id`, `bind_fingerprint` | An eine Geräte-ID / einen Browser-Fingerprint binden |

```python
issue = captchala.issue_server_token("login", bind_uid=str(user.id), ttl=300)
if not issue.ok:
    return {"error": issue.error}, 503   # rate_limit_exceeded, ...
return {"server_token": issue.token}
```

`IssueResult`: `ok`, `token`, `expires_in`, `issued_at`, `error`, `message`, `http_status`, `retry_after`, `retryable`, `cause`.

### `client.moderation_check(input, user_id=None)` / `client.moderation_text(text, user_id=None)`

Multimodale Inhaltsmoderation. `input` ist eine Liste OpenAI-kompatibler Elemente; verwenden Sie die Helfer `text_item()` / `image_url_item()`.

```python
from captchala import text_item, image_url_item

m = captchala.moderation_check([text_item(comment), image_url_item(upload_url)], user_id=str(user.id))
if m.ok and m.flagged and m.has_category("violence", "csam"):
    ...  # hard block

t = captchala.moderation_text("user comment here")
```

`ModerationResult`: `ok`, `flagged`, `categories`, `category_scores`, `content_type`, `raw`, `error`, `message`, `has_category(*names)`. Die Kategorien hängen vom Modell ab; iterieren Sie daher defensiv darüber.

### `user_message(code)`

Eine kurze, für Endnutzer unbedenkliche englische Meldung zu einem Fehlercode, gedacht für Formularfehler (`"CAPTCHA expired or was already used. Please refresh and try again."`). Zeigen Sie Endnutzern niemals rohe Codes. Unbekannte Codes erhalten eine allgemeine Meldung.

## Fehler, Wiederholungen und Timeouts

Die Methoden geben ein Ergebnis zurück und werfen bei Verifizierungs-, API- oder Netzwerkfehlern keine Exception. `result.error` ist ein kurzer Code. `result.cause` enthält eine typisierte Exception, wenn der Fehler vom Transport oder von der API stammt:

| Klasse | Wann |
|---|---|
| `NetworkError` (`connect_failed`) | DNS-Fehler, Verbindung abgelehnt / zurückgesetzt |
| `RequestTimeoutError` (Unterklasse von `NetworkError`) | Keine Antwort innerhalb von `timeout` |
| `AuthenticationError` | App Key / Secret falsch oder fehlend |
| `RateLimitError` | Rate-Limit oder Kontingent erreicht; siehe `retry_after` |
| `InvalidResponseError` | Der Body war nicht das erwartete JSON |
| `APIError` | Jeder andere API-Fehler (Basisklasse der drei obigen) |
| `ValidationFailedError` | Wird von `result.raise_if_invalid()` geworfen |

Alle erben von `CaptchaLaError` und tragen `code`.

Wiederholungen nutzen exponentielles Backoff mit Jitter. Verbindungsfehler und HTTP 502 / 503 werden immer wiederholt. Timeouts, zurückgesetzte Verbindungen und HTTP 504 werden bei `validate` und `issue_server_token` wiederholt, nicht aber bei der Moderation, wo der Inhalt möglicherweise bereits verarbeitet wird. Rate-Limit-Antworten (HTTP 429) werden nicht wiederholt. Beachten Sie, dass ein pass token nur einmal verwendbar ist: Hat ein erster Versuch die API erreicht und den Token verbraucht, bevor die Verbindung abbrach, meldet die Wiederholung `token_already_used`. Im Zweifel wird also abgelehnt.

## Django

```python
# settings.py
CAPTCHALA_APP_KEY = "..."
CAPTCHALA_APP_SECRET = "..."
# optional: CAPTCHALA_TIMEOUT, CAPTCHALA_REJECT_CLIENT_ONLY
```

Formularfeld. `cleaned_data` enthält das `ValidateResult`; Fehler verwenden die Texte aus `user_message()` und den API-Fehlercode als Code des `ValidationError`:

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

View-Decorator, für synchrone und asynchrone Views:

```python
from captchala.contrib.django import captchala_required

@captchala_required(action="login")
def login_view(request):
    request.captchala  # ValidateResult
    ...
```

Bei einem Fehlschlag wird HTTP 400 `{"error": "captcha_failed", "code": "<error code>"}` zurückgegeben oder das, was `on_failure(request, result)` liefert. Weitere Optionen: `hostname`, `fields`, `allow_degraded`, `client`. `verify_request(request, ...)` liefert das Ergebnis ohne Decorator.

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

Bei einem Fehlschlag wird HTTP 400 `{"error": "captcha_failed", "code": "<error code>"}` zurückgegeben oder `on_failure(result)`. Mit `captcha.verify(action=...)` validieren Sie die aktuelle Anfrage selbst. Asynchrone Views werden mit `flask[async]` unterstützt.

Die Helfer lesen den Token aus dem Formular- / JSON-Feld `captcha_token` (oder `captchala_token`) und danach aus dem Header `X-Captcha-Token`. Die IP des Endnutzers übergeben sie aus `CF-Connecting-IP`, dem ersten Eintrag von `X-Forwarded-For`, `X-Real-IP` oder der Remote-Adresse. Jeder kann diese Header setzen, wenn Ihre App nicht hinter einem Proxy läuft, der sie überschreibt. Die IP ist nur ein zusätzliches Risikosignal.

<a id="token-types"></a>
## Token-Typen

| Präfix | Quelle | Behandlung |
|---|---|---|
| `pt_` | Haupt-API | Von `validate()` verifiziert |
| `offline_` | Backup-Dienst, während einer Dienststörung | Wird automatisch gegen den Backup-Dienst verifiziert; `offline=True` |
| `dg_` | Haupt-API, eingeschränkter Modus (Kontingent erschöpft) | `valid` ist immer `False`; prüfen Sie `degraded` und entscheiden Sie selbst |
| `client_` | Reiner Client-Platzhalter (native SDKs) | Siehe unten |
| `co_` | Reiner Client-Platzhalter (Web-SDK) | Siehe unten |

### Degraded-Tokens

Ist das Kontingent einer App erschöpft, schließt das Client-SDK mit einem `dg_`-Token ab, damit Ihre Nutzer nicht blockiert werden. `valid` bleibt `False`. Um den Ablauf offen zu halten, während Sie upgraden:

```python
if result.valid or result.degraded:
    ...  # allow
```

Die Django- / Flask-Helfer tun dies mit `allow_degraded=True`.

### Reine Client-Tokens (`client_` / `co_`)

Das Client-SDK erzeugt diese nur, wenn es weder die API noch den Backup-Dienst erreichen konnte. Sie tragen keine Signatur, daher akzeptiert das SDK einen solchen Token nur, wenn auch Ihr Server die API nicht erreichen kann:

1. Es prüft die API (Timeout 2 s). Jede HTTP-Antwort bedeutet, dass kein Ausfall vorliegt: `valid=False`, `client_only=True`, `error="client_only_rejected_api_reachable"`.
2. Andernfalls prüft es den Backup-Dienst auf dieselbe Weise.
3. Nur wenn beide nicht erreichbar sind: `valid=True`, `client_only=True`, `offline=True`, mit einer `warning`.

Die Prüfergebnisse werden pro Prozess zwischengespeichert (30 s bei Erreichbarkeit, 5 s sonst), und gleichzeitige Validierungen teilen sich eine Prüfung. Für sensible Aktionen (Login, Zahlung) lehnen Sie sie auch während eines Ausfalls ab:

```python
strict = Client(reject_client_only=True)
# client_ / co_ -> valid=False, error="client_only_rejected_by_policy"
```

<a id="testing-your-integration"></a>
## Ihre Integration testen

Die API stellt öffentliche Test-Keys bereit, die immer bestehen oder immer fehlschlagen, ohne dass ein CAPTCHA gelöst wird. Siehe [Test-Keys](https://docs.captcha.la/api-reference#test-keys). Ergebnisse davon haben `test == True`. Konfigurieren Sie sie niemals in Produktion.

In Unit-Tests injizieren Sie einen Transport (sync) oder einen httpx-Mock-Transport (async):

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

## Entwicklung

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
CAPTCHALA_APP_KEY=xxx CAPTCHALA_APP_SECRET=xxx .venv/bin/python scripts/live_smoke.py   # live check, no real challenge
```

## Lizenz

MIT
