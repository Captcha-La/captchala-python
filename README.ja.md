# CaptchaLa Python SDK

[English](https://github.com/Captcha-La/captchala-python/blob/main/README.md) · [简体中文](https://github.com/Captcha-La/captchala-python/blob/main/README_zh.md) · **日本語** · [한국어](https://github.com/Captcha-La/captchala-python/blob/main/README.ko.md) · [Español](https://github.com/Captcha-La/captchala-python/blob/main/README.es.md) · [Português (BR)](https://github.com/Captcha-La/captchala-python/blob/main/README.pt-BR.md) · [Deutsch](https://github.com/Captcha-La/captchala-python/blob/main/README.de.md)

Python から CaptchaLa のトークンを検証するためのサーバーサイド SDK です。同期・非同期クライアントを備え、型付きで、Django / Flask 用のヘルパーもオプションで利用できます。

- [Web サイト](https://captcha.la)
- [ドキュメント](https://docs.captcha.la/sdk/server-python)
- [Web SDK ドキュメント](https://docs.captcha.la/web-sdk)
- [ダッシュボード](https://dash.captcha.la)

## インストール

```bash
pip install captchala             # sync client, no dependencies
pip install "captchala[async]"    # + AsyncClient (httpx)
pip install "captchala[django]"   # + Django helpers
pip install "captchala[flask]"    # + Flask helpers
```

**Python 3.9 以上**が必要です。同期クライアントは標準ライブラリのみを使用します。

## クイックスタート

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

非同期の場合:

```python
from captchala import AsyncClient

async with AsyncClient() as captchala:
    result = await captchala.validate(token, client_ip=user_ip)
```

## API リファレンス

### `Client(app_key=None, app_secret=None, **options)` / `AsyncClient(...)`

| オプション | デフォルト | 説明 |
|---|---|---|
| `app_key` | `$CAPTCHALA_APP_KEY` | App Key(ダッシュボードで取得) |
| `app_secret` | `$CAPTCHALA_APP_SECRET` | App Secret(ダッシュボードで取得)。サーバー側でのみ使用 |
| `base_url` | `https://verify.captcha.la` | API のベース URL |
| `timeout` | `5.0` | 1 回の試行あたりのタイムアウト(秒) |
| `max_retries` | `2` | 初回試行後のリトライ回数(`0` で無効) |
| `retry_backoff` | `0.2` | 指数バックオフの基本待機時間(秒) |
| `reject_client_only` | `False` | クライアント専用トークンを常に拒否する。後述 |
| `headers` | `None` | すべてのリクエストに付与する追加ヘッダー |
| `transport` | urllib | *(同期)* カスタムのトランスポート関数。[テスト](#testing-your-integration)を参照 |
| `http_client` | 新規の `httpx.AsyncClient` | *(非同期)* 独自の httpx クライアントを共有 |

キーまたはシークレットが未指定の場合は `ConfigurationError` を送出します。クライアントは 1 つ作成して使い回してください。`Client` はスレッドセーフです。`AsyncClient` は `await client.aclose()` または `async with` でクローズします。

### `client.validate(token, **options) -> ValidateResult`

クライアント SDK から受け取った pass token を検証します。トークンが無効な場合や API エラー、ネットワーク障害が発生しても例外は送出しません。`result.valid` と `result.error` を確認してください。

| オプション | 説明 |
|---|---|
| `client_ip` | *(任意・推奨)* 受信リクエストから取得したエンドユーザーの IP。追加のリスクチェックに使用されます |
| `keep_token` | `True` = トークンを消費せずにチェック(デフォルトは `False`) |
| `expected_action` | 想定するアクション(例: `"login"`)。別のアクション向けに発行されたトークンは `action_mismatch` で失敗します |
| `expected_hostname` | 想定するホスト名(Web)またはパッケージ名 / バンドル ID(ネイティブ)。文字列またはリストで指定します。`*.example.com` は任意のサブドメインにマッチします。不一致時: `hostname_mismatch` |
| `bind_uid`, `bind_account`, `bind_email`, `bind_phone`, `scene` | エンドユーザーの識別情報。発行時にバインドされた情報と比較されます(`binding_match` を参照) |

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

| 属性 | 型 | 説明 |
|---|---|---|
| `valid` | `bool` | 検証に合格したかどうか。判定に使うべき唯一のフィールドです |
| `error` | `str \| None` | エラーコード(例: `token_expired`, `action_mismatch`, `request_failed`) |
| `message` | `str \| None` | API レベルのエラー時の、人が読める API メッセージ |
| `action` | `str \| None` | トークンのビジネスアクション |
| `uid` | `str \| None` | 発行時に `bind_uid` でバインドされたユーザー ID |
| `challenge_id` | `str \| None` | チャレンジ ID |
| `hostname` | `str \| None` | チャレンジが解かれた場所(ホスト名またはパッケージ ID) |
| `challenge_ts` | `str \| None` | 解答時刻(ISO 8601 UTC) |
| `risk_level` | `str \| None` | `low` / `medium` / `high` / `critical`。参考情報 |
| `risk_labels` | `tuple[str, ...]` | 大まかなリスクカテゴリ(例: `proxy`)。参考情報 |
| `captcha_args` | `CaptchaArgs \| None` | 解答時コンテキストのエコー: `platform`, `user_ip`, `referer`, `pkg`, `solved_at`, `risk_score`。参考情報 |
| `user_ip` | `str \| None` | 解答時に記録されたエンドユーザーの IP。参考情報 |
| `binding` / `binding_match` | | 発行時にバインドされた識別情報と、フィールドごとの比較結果 |
| `binding_mismatch` | `bool` | `binding_match` のいずれかのフィールドが `False` のとき `True` |
| `degraded` / `degraded_reason` | | クォータ枯渇中に発行された `dg_` トークン。後述 |
| `offline` / `client_only` / `warning` | | 障害時のフォールバック。[トークンの種類](#token-types)を参照 |
| `test` | `bool` | 公開テストキーによる応答。本番環境では拒否してください |
| `http_status`, `retry_after`, `retryable` | | 失敗の詳細 |
| `cause` | `CaptchaLaError \| None` | API / ネットワーク障害時の型付きエラー |
| `raw` | `dict \| None` | 生の `data` オブジェクト |

メソッド: `raise_if_invalid()` は `valid` でない場合に `ValidationFailedError` を送出します。`to_dict()`。

### `bind_uid` の検証

`bind_uid="user_42"` を指定して server token を発行した場合は、結果を想定するユーザーと比較します:

```python
result = captchala.validate(token)
if result.valid and result.uid != expected_user_id:
    ...  # pass token was issued for a different user: reject
```

または、validate 時に識別情報を送信して `result.binding_mismatch` を確認します。

### `client.issue_server_token(action, **options) -> IssueResult`

使い捨ての `sct_` server token を発行します。これを `serverToken` としてクライアント SDK に渡してください。

| オプション | 説明 |
|---|---|
| `bind_ip` | エンドユーザーの IP。別のネットワークから開始されたチャレンジは拒否される場合があります |
| `ttl` | 有効期間(秒。サーバー側のデフォルトは 300、最大 900) |
| `max_uses` | このトークンを使える pass フローの回数(サーバー側のデフォルトは 10) |
| `bind_uid` | 自社のユーザー ID。validate で `uid` として返されます |
| `bind_account`, `bind_email`, `bind_phone`, `scene` | エンドユーザーの識別情報 |
| `bind_device_id`, `bind_fingerprint` | デバイス ID / ブラウザフィンガープリントへのバインド |

```python
issue = captchala.issue_server_token("login", bind_uid=str(user.id), ttl=300)
if not issue.ok:
    return {"error": issue.error}, 503   # rate_limit_exceeded, ...
return {"server_token": issue.token}
```

`IssueResult`: `ok`, `token`, `expires_in`, `issued_at`, `error`, `message`, `http_status`, `retry_after`, `retryable`, `cause`。

### `client.moderation_check(input, user_id=None)` / `client.moderation_text(text, user_id=None)`

マルチモーダルのコンテンツモデレーションです。`input` は OpenAI 互換のアイテムのリストです。`text_item()` / `image_url_item()` ヘルパーを使ってください。

```python
from captchala import text_item, image_url_item

m = captchala.moderation_check([text_item(comment), image_url_item(upload_url)], user_id=str(user.id))
if m.ok and m.flagged and m.has_category("violence", "csam"):
    ...  # hard block

t = captchala.moderation_text("user comment here")
```

`ModerationResult`: `ok`, `flagged`, `categories`, `category_scores`, `content_type`, `raw`, `error`, `message`, `has_category(*names)`。カテゴリはモデルによって異なるため、防御的に走査してください。

### `user_message(code)`

エラーコードに対応する、ユーザーに表示しても安全な短い英語メッセージを返します。フォームのエラー表示用です(`"CAPTCHA expired or was already used. Please refresh and try again."`)。生のコードをエンドユーザーに表示しないでください。未知のコードには汎用メッセージが返されます。

## エラー、リトライ、タイムアウト

各メソッドは結果オブジェクトを返し、検証・API・ネットワークの失敗で例外を送出しません。`result.error` は短いコードです。失敗がトランスポートまたは API に起因する場合、`result.cause` に型付きの例外が入ります:

| クラス | 発生条件 |
|---|---|
| `NetworkError` (`connect_failed`) | DNS 解決の失敗、接続の拒否 / リセット |
| `RequestTimeoutError` (`NetworkError` のサブクラス) | `timeout` 内に応答がない |
| `AuthenticationError` | App Key / Secret が誤っている、または未指定 |
| `RateLimitError` | レート制限またはクォータ超過。`retry_after` を参照 |
| `InvalidResponseError` | レスポンスボディが想定した JSON ではない |
| `APIError` | その他の API エラー(上記 3 つの基底クラス) |
| `ValidationFailedError` | `result.raise_if_invalid()` が送出 |

いずれも `CaptchaLaError` を継承し、`code` を持ちます。

リトライはジッター付きの指数バックオフで行われます。接続失敗と HTTP 502 / 503 は常にリトライされます。タイムアウト、接続リセット、HTTP 504 は `validate` と `issue_server_token` ではリトライされますが、コンテンツがすでに処理中の可能性があるモデレーションではリトライされません。レート制限の応答(HTTP 429)はリトライされません。なお pass token は 1 回限りです。初回の試行が API に到達してトークンが消費された後に接続が切れた場合、リトライは `token_already_used` を返します。つまり安全側(拒否)に倒れます。

## Django

```python
# settings.py
CAPTCHALA_APP_KEY = "..."
CAPTCHALA_APP_SECRET = "..."
# optional: CAPTCHALA_BASE_URL, CAPTCHALA_TIMEOUT, CAPTCHALA_REJECT_CLIENT_ONLY
```

フォームフィールド。`cleaned_data` には `ValidateResult` が入ります。エラーには `user_message()` のテキストが使われ、API のエラーコードが `ValidationError` の code になります:

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

ビューデコレーター(同期・非同期ビューの両方に対応):

```python
from captchala.contrib.django import captchala_required

@captchala_required(action="login")
def login_view(request):
    request.captchala  # ValidateResult
    ...
```

失敗時は HTTP 400 `{"error": "captcha_failed", "code": "<error code>"}`、または `on_failure(request, result)` の戻り値を返します。その他のオプション: `hostname`, `fields`, `allow_degraded`, `client`。`verify_request(request, ...)` を使うと、デコレーターなしで結果を取得できます。

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

失敗時は HTTP 400 `{"error": "captcha_failed", "code": "<error code>"}`、または `on_failure(result)` の戻り値を返します。`captcha.verify(action=...)` を使うと、現在のリクエストを自分で検証できます。`flask[async]` を使えば非同期ビューにも対応します。

ヘルパーはトークンを `captcha_token`(または `captchala_token`)のフォーム / JSON フィールドから読み取り、なければ `X-Captcha-Token` ヘッダーから読み取ります。エンドユーザーの IP は `CF-Connecting-IP`、`X-Forwarded-For` の先頭エントリ、`X-Real-IP`、またはリモートアドレスの順で取得して渡します。アプリがこれらのヘッダーを上書きするプロキシの背後にない場合、誰でもこれらのヘッダーを設定できます。IP はあくまで追加のリスクシグナルです。

<a id="token-types"></a>
## トークンの種類

| プレフィックス | 発行元 | 扱い |
|---|---|---|
| `pt_` | メイン API | `validate()` で検証 |
| `offline_` | バックアップサービス(サービス障害時) | バックアップサービスに対して自動的に検証。`offline=True` |
| `dg_` | メイン API(デグレード、クォータ枯渇) | `valid` は常に `False`。`degraded` を確認して自分で判断 |
| `client_` | クライアント専用のプレースホルダー(ネイティブ SDK) | 後述 |
| `co_` | クライアント専用のプレースホルダー(Web SDK) | 後述 |

### デグレードトークン

アプリのクォータが枯渇すると、ユーザーがブロックされないよう、クライアント SDK は `dg_` トークンで処理を完了します。`valid` は `False` のままです。アップグレードするまでフローを通したい場合は次のようにします:

```python
if result.valid or result.degraded:
    ...  # allow
```

Django / Flask ヘルパーでは `allow_degraded=True` で同じ動作になります。

### クライアント専用トークン(`client_` / `co_`)

クライアント SDK は、API とバックアップサービスのどちらにも到達できなかった場合にのみこれらを発行します。署名を持たないため、SDK はサーバー側からも API に到達できない場合に限り受け入れます:

1. API をプローブします(タイムアウト 2 秒)。何らかの HTTP 応答があれば障害は起きていないと判断し、`valid=False`, `client_only=True`, `error="client_only_rejected_api_reachable"` となります。
2. 到達できなければ、同じ方法でバックアップサービスをプローブします。
3. 両方に到達できない場合に限り、`valid=True`, `client_only=True`, `offline=True` となり、`warning` が付きます。

プローブ結果はプロセスごとにキャッシュされ(到達可能なら 30 秒、不可なら 5 秒)、同時に行われる検証は 1 回のプローブを共有します。機密性の高いアクション(ログイン、決済)では、障害中であってもこれらを拒否できます:

```python
strict = Client(reject_client_only=True)
# client_ / co_ -> valid=False, error="client_only_rejected_by_policy"
```

<a id="testing-your-integration"></a>
## 統合のテスト

API には、CAPTCHA を解かずに常に合格または常に失敗する公開テストキーが用意されています。[テストキー](https://docs.captcha.la/api-reference#test-keys)を参照してください。これらによる結果は `test == True` になります。本番環境には絶対に設定しないでください。

ユニットテストでは、トランスポート(同期)または httpx のモックトランスポート(非同期)を注入します:

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

## 開発

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
CAPTCHALA_APP_KEY=xxx CAPTCHALA_APP_SECRET=xxx .venv/bin/python scripts/live_smoke.py   # live check, no real challenge
```

## ライセンス

MIT
