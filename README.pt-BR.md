# CaptchaLa Python SDK

[English](https://github.com/Captcha-La/captchala-python/blob/main/README.md) · [简体中文](https://github.com/Captcha-La/captchala-python/blob/main/README_zh.md) · [日本語](https://github.com/Captcha-La/captchala-python/blob/main/README.ja.md) · [한국어](https://github.com/Captcha-La/captchala-python/blob/main/README.ko.md) · [Español](https://github.com/Captcha-La/captchala-python/blob/main/README.es.md) · **Português (BR)** · [Deutsch](https://github.com/Captcha-La/captchala-python/blob/main/README.de.md)

SDK de servidor para validar tokens do CaptchaLa a partir do Python. Clientes síncrono e assíncrono, tipados, com helpers opcionais para Django e Flask.

- [Site](https://captcha.la)
- [Documentação](https://docs.captcha.la/sdk/server-python)
- [Documentação do Web SDK](https://docs.captcha.la/web-sdk)
- [Painel](https://dash.captcha.la)

## Instalação

```bash
pip install captchala             # sync client, no dependencies
pip install "captchala[async]"    # + AsyncClient (httpx)
pip install "captchala[django]"   # + Django helpers
pip install "captchala[flask]"    # + Flask helpers
```

Requer **Python 3.9+**. O cliente síncrono usa apenas a biblioteca padrão.

## Início rápido

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

Assíncrono:

```python
from captchala import AsyncClient

async with AsyncClient() as captchala:
    result = await captchala.validate(token, client_ip=user_ip)
```

## Referência da API

### `Client(app_key=None, app_secret=None, **options)` / `AsyncClient(...)`

| Opção | Padrão | Descrição |
|---|---|---|
| `app_key` | `$CAPTCHALA_APP_KEY` | App Key (do painel) |
| `app_secret` | `$CAPTCHALA_APP_SECRET` | App Secret (do painel). Somente no servidor |
| `base_url` | `https://verify.captcha.la` | URL base da API |
| `timeout` | `5.0` | Timeout por tentativa, em segundos |
| `max_retries` | `2` | Novas tentativas após a primeira (`0` desativa) |
| `retry_backoff` | `0.2` | Atraso base do backoff exponencial, em segundos |
| `reject_client_only` | `False` | Sempre rejeitar tokens somente do cliente, veja abaixo |
| `headers` | `None` | Cabeçalhos extras enviados em toda requisição |
| `transport` | urllib | *(síncrono)* Callable de transporte personalizado, veja [Testes](#testing-your-integration) |
| `http_client` | novo `httpx.AsyncClient` | *(assíncrono)* Compartilhe seu próprio cliente httpx |

Lança `ConfigurationError` quando a chave ou o segredo estiver ausente. Crie um único cliente e reutilize-o; `Client` é thread-safe. Feche um `AsyncClient` com `await client.aclose()` ou `async with`.

### `client.validate(token, **options) -> ValidateResult`

Valida um pass token vindo do SDK do cliente. Nunca lança exceção para tokens inválidos, erros da API ou falhas de rede. Verifique `result.valid` e `result.error`.

| Opção | Descrição |
|---|---|
| `client_ip` | *(opcional, recomendado)* O IP do usuário final obtido da requisição recebida. Usado em verificações de risco adicionais |
| `keep_token` | `True` = verificar sem consumir o token (padrão `False`) |
| `expected_action` | A ação esperada, por exemplo `"login"`. Um token emitido para outra ação falha com `action_mismatch` |
| `expected_hostname` | O hostname (web) ou package / bundle id (nativo) esperado, como string ou lista. `*.example.com` corresponde a qualquer subdomínio. Divergência: `hostname_mismatch` |
| `bind_uid`, `bind_account`, `bind_email`, `bind_phone`, `scene` | Identidade do usuário final, comparada com a identidade vinculada na emissão (veja `binding_match`) |

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

| Atributo | Tipo | Descrição |
|---|---|---|
| `valid` | `bool` | Se a validação passou. É o único campo para decidir liberar ou bloquear |
| `error` | `str \| None` | Código de erro, por exemplo `token_expired`, `action_mismatch`, `request_failed` |
| `message` | `str \| None` | Mensagem legível da API, para erros no nível da API |
| `action` | `str \| None` | Ação de negócio do token |
| `uid` | `str \| None` | ID do usuário vinculado via `bind_uid` na emissão |
| `challenge_id` | `str \| None` | ID do desafio |
| `hostname` | `str \| None` | Onde o desafio foi resolvido (hostname ou package id) |
| `challenge_ts` | `str \| None` | Momento da resolução, ISO 8601 UTC |
| `risk_level` | `str \| None` | `low` / `medium` / `high` / `critical`. Informativo |
| `risk_labels` | `tuple[str, ...]` | Categorias de risco gerais, por exemplo `proxy`. Informativo |
| `captcha_args` | `CaptchaArgs \| None` | Eco do contexto da resolução: `platform`, `user_ip`, `referer`, `pkg`, `solved_at`, `risk_score`. Informativo |
| `user_ip` | `str \| None` | IP do usuário final registrado no momento da resolução. Informativo |
| `binding` / `binding_match` | | Identidade vinculada na emissão e a comparação campo a campo |
| `binding_mismatch` | `bool` | `True` quando algum campo de `binding_match` é `False` |
| `degraded` / `degraded_reason` | | Token `dg_` emitido enquanto a cota está esgotada, veja abaixo |
| `offline` / `client_only` / `warning` | | Alternativas em caso de indisponibilidade, veja [Tipos de token](#token-types) |
| `test` | `bool` | Resposta de uma chave de teste pública. Rejeite em produção |
| `http_status`, `retry_after`, `retryable` | | Detalhes da falha |
| `cause` | `CaptchaLaError \| None` | Erro tipado para falhas de API / rede |
| `raw` | `dict \| None` | O objeto `data` bruto |

Métodos: `raise_if_invalid()` lança `ValidationFailedError` a menos que `valid`; `to_dict()`.

### Verificando `bind_uid`

Se você emitiu o server token com `bind_uid="user_42"`, compare o resultado com o usuário esperado:

```python
result = captchala.validate(token)
if result.valid and result.uid != expected_user_id:
    ...  # pass token was issued for a different user: reject
```

Ou envie a identidade no validate e verifique `result.binding_mismatch`.

### `client.issue_server_token(action, **options) -> IssueResult`

Gera um server token `sct_` de uso único. Entregue-o ao SDK do cliente como `serverToken`.

| Opção | Descrição |
|---|---|
| `bind_ip` | IP do usuário final. Um desafio iniciado a partir de outra rede pode ser rejeitado |
| `ttl` | Tempo de vida em segundos (padrão do servidor 300, máximo 900) |
| `max_uses` | Em quantos fluxos de pass o token pode ser usado (padrão do servidor 10) |
| `bind_uid` | Seu ID de usuário; devolvido pelo validate como `uid` |
| `bind_account`, `bind_email`, `bind_phone`, `scene` | Identidade do usuário final |
| `bind_device_id`, `bind_fingerprint` | Vincular a um device id / impressão digital do navegador |

```python
issue = captchala.issue_server_token("login", bind_uid=str(user.id), ttl=300)
if not issue.ok:
    return {"error": issue.error}, 503   # rate_limit_exceeded, ...
return {"server_token": issue.token}
```

`IssueResult`: `ok`, `token`, `expires_in`, `issued_at`, `error`, `message`, `http_status`, `retry_after`, `retryable`, `cause`.

### `client.moderation_check(input, user_id=None)` / `client.moderation_text(text, user_id=None)`

Moderação de conteúdo multimodal. `input` é uma lista de itens compatíveis com OpenAI; use os helpers `text_item()` / `image_url_item()`.

```python
from captchala import text_item, image_url_item

m = captchala.moderation_check([text_item(comment), image_url_item(upload_url)], user_id=str(user.id))
if m.ok and m.flagged and m.has_category("violence", "csam"):
    ...  # hard block

t = captchala.moderation_text("user comment here")
```

`ModerationResult`: `ok`, `flagged`, `categories`, `category_scores`, `content_type`, `raw`, `error`, `message`, `has_category(*names)`. As categorias dependem do modelo, então percorra-as de forma defensiva.

### `user_message(code)`

Uma mensagem curta em inglês, segura para exibir ao usuário, para um código de erro; útil em erros de formulário (`"CAPTCHA expired or was already used. Please refresh and try again."`). Nunca mostre códigos brutos aos usuários finais. Códigos desconhecidos recebem uma mensagem genérica.

## Erros, novas tentativas e timeouts

Os métodos retornam um resultado e não lançam exceção para falhas de verificação, da API ou de rede. `result.error` é um código curto. `result.cause` contém uma exceção tipada quando a falha veio do transporte ou da API:

| Classe | Quando |
|---|---|
| `NetworkError` (`connect_failed`) | Falha de DNS, conexão recusada / redefinida |
| `RequestTimeoutError` (subclasse de `NetworkError`) | Sem resposta dentro de `timeout` |
| `AuthenticationError` | App key / secret incorretos ou ausentes |
| `RateLimitError` | Limite de taxa ou cota; veja `retry_after` |
| `InvalidResponseError` | O corpo não era o JSON esperado |
| `APIError` | Qualquer outro erro da API (classe base das três acima) |
| `ValidationFailedError` | Lançada por `result.raise_if_invalid()` |

Todas derivam de `CaptchaLaError` e carregam `code`.

As novas tentativas usam backoff exponencial com jitter. Falhas de conexão e HTTP 502 / 503 sempre são repetidas. Timeouts, conexões redefinidas e HTTP 504 são repetidos em `validate` e `issue_server_token`, mas não na moderação, em que o conteúdo pode já estar sendo processado. Respostas de limite de taxa (HTTP 429) não são repetidas. Observe que um pass token é de uso único: se a primeira tentativa chegou à API e consumiu o token antes de a conexão cair, a nova tentativa informa `token_already_used`. A falha é segura (rejeita).

## Django

```python
# settings.py
CAPTCHALA_APP_KEY = "..."
CAPTCHALA_APP_SECRET = "..."
# optional: CAPTCHALA_BASE_URL, CAPTCHALA_TIMEOUT, CAPTCHALA_REJECT_CLIENT_ONLY
```

Campo de formulário. `cleaned_data` contém o `ValidateResult`; os erros usam os textos de `user_message()` e o código de erro da API como código do `ValidationError`:

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

Decorator de view, para views síncronas e assíncronas:

```python
from captchala.contrib.django import captchala_required

@captchala_required(action="login")
def login_view(request):
    request.captchala  # ValidateResult
    ...
```

Em caso de falha, retorna HTTP 400 `{"error": "captcha_failed", "code": "<error code>"}`, ou o que `on_failure(request, result)` retornar. Outras opções: `hostname`, `fields`, `allow_degraded`, `client`. `verify_request(request, ...)` retorna o resultado sem decorator.

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

Em caso de falha, retorna HTTP 400 `{"error": "captcha_failed", "code": "<error code>"}`, ou `on_failure(result)`. `captcha.verify(action=...)` permite que você mesmo valide a requisição atual. Views assíncronas são suportadas com `flask[async]`.

Os helpers leem o token do campo de formulário / JSON `captcha_token` (ou `captchala_token`) e, depois, do cabeçalho `X-Captcha-Token`. Eles repassam o IP do usuário final a partir de `CF-Connecting-IP`, da primeira entrada de `X-Forwarded-For`, de `X-Real-IP` ou do endereço remoto. Qualquer pessoa pode definir esses cabeçalhos quando sua aplicação não está atrás de um proxy que os sobrescreva. O IP é apenas um sinal de risco extra.

<a id="token-types"></a>
## Tipos de token

| Prefixo | Origem | Tratamento |
|---|---|---|
| `pt_` | API principal | Verificado por `validate()` |
| `offline_` | Serviço de backup, durante uma interrupção do serviço | Verificado automaticamente junto ao serviço de backup; `offline=True` |
| `dg_` | API principal, modo degradado (cota esgotada) | `valid` é sempre `False`; verifique `degraded` e decida você mesmo |
| `client_` | Placeholder somente do cliente (SDKs nativos) | Veja abaixo |
| `co_` | Placeholder somente do cliente (Web SDK) | Veja abaixo |

### Tokens degradados

Quando a cota de um app se esgota, o SDK do cliente conclui com um token `dg_` para que seus usuários não fiquem bloqueados. `valid` continua `False`. Para manter o fluxo aberto enquanto você faz o upgrade:

```python
if result.valid or result.degraded:
    ...  # allow
```

Os helpers de Django / Flask fazem isso com `allow_degraded=True`.

### Tokens somente do cliente (`client_` / `co_`)

O SDK do cliente só os gera quando não conseguiu alcançar nem a API nem o serviço de backup. Eles não têm assinatura, então o SDK só aceita um deles se o seu servidor também não conseguir alcançar a API:

1. Ele sonda a API (timeout de 2 s). Qualquer resposta HTTP significa que não há interrupção: `valid=False`, `client_only=True`, `error="client_only_rejected_api_reachable"`.
2. Caso contrário, sonda o serviço de backup da mesma forma.
3. Somente quando ambos estão inacessíveis: `valid=True`, `client_only=True`, `offline=True`, com um `warning`.

Os resultados da sondagem ficam em cache por processo (30 s quando acessível, 5 s quando não), e validações simultâneas compartilham uma única sondagem. Para ações sensíveis (login, pagamento), recuse-os mesmo durante uma interrupção:

```python
strict = Client(reject_client_only=True)
# client_ / co_ -> valid=False, error="client_only_rejected_by_policy"
```

<a id="testing-your-integration"></a>
## Testando sua integração

A API oferece chaves de teste públicas que sempre passam ou sempre falham, sem resolver um CAPTCHA. Veja [Chaves de teste](https://docs.captcha.la/api-reference#test-keys). Os resultados delas têm `test == True`. Nunca as configure em produção.

Em testes unitários, injete um transporte (síncrono) ou um transporte mock do httpx (assíncrono):

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

## Desenvolvimento

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
CAPTCHALA_APP_KEY=xxx CAPTCHALA_APP_SECRET=xxx .venv/bin/python scripts/live_smoke.py   # live check, no real challenge
```

## Licença

MIT
