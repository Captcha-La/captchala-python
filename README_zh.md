# CaptchaLa Python SDK

用于在 Python 服务端校验 CaptchaLa 令牌的 SDK。提供同步与异步客户端，带完整类型标注，并附带可选的 Django / Flask 集成。

[English](README.md) | **简体中文**

- [官网](https://captcha.la)
- [文档](https://docs.captcha.la/sdk/server-python)
- [Web SDK 文档](https://docs.captcha.la/web-sdk)
- [控制台](https://dash.captcha.la)

## 安装

```bash
pip install captchala             # 同步客户端，无任何依赖
pip install "captchala[async]"    # + AsyncClient（httpx）
pip install "captchala[django]"   # + Django 集成
pip install "captchala[flask]"    # + Flask 集成
```

需要 **Python 3.9+**。同步客户端只使用标准库。

## 快速开始

```python
from captchala import Client

# 未传入时读取环境变量 CAPTCHALA_APP_KEY / CAPTCHALA_APP_SECRET
captchala = Client("your_app_key", "your_app_secret")

result = captchala.validate(
    token,
    client_ip=user_ip,          # 可选，推荐传入
    expected_action="login",    # 可选：拒绝为其他 action 签发的令牌
)

if result.valid:
    ...  # 校验通过
else:
    print(result.error)  # 例如 "token_expired"
```

异步：

```python
from captchala import AsyncClient

async with AsyncClient() as captchala:
    result = await captchala.validate(token, client_ip=user_ip)
```

## API 参考

### `Client(app_key=None, app_secret=None, **options)` / `AsyncClient(...)`

| 选项 | 默认值 | 说明 |
|---|---|---|
| `app_key` | `$CAPTCHALA_APP_KEY` | App Key（控制台获取） |
| `app_secret` | `$CAPTCHALA_APP_SECRET` | App Secret（控制台获取），仅限服务端 |
| `base_url` | `https://verify.captcha.la` | API 地址 |
| `timeout` | `5.0` | 单次请求超时（秒） |
| `max_retries` | `2` | 首次请求之后的重试次数（`0` 关闭重试） |
| `retry_backoff` | `0.2` | 指数退避的基础间隔（秒） |
| `reject_client_only` | `False` | 始终拒绝纯客户端令牌，见下文 |
| `headers` | `None` | 每个请求附带的额外请求头 |
| `transport` | urllib | *（同步）* 自定义传输函数，见[测试](#测试你的集成) |
| `http_client` | 新建 `httpx.AsyncClient` | *（异步）* 复用你自己的 httpx 客户端 |

缺少 key 或 secret 时抛出 `ConfigurationError`。建议创建一个实例并复用，`Client` 线程安全。`AsyncClient` 用 `await client.aclose()` 或 `async with` 关闭。

### `client.validate(token, **options) -> ValidateResult`

校验前端 SDK 返回的 pass token。令牌无效、API 报错或网络故障都不会抛异常，请检查 `result.valid` 与 `result.error`。

| 选项 | 说明 |
|---|---|
| `client_ip` | *（可选，推荐）* 来自入站请求的终端用户 IP，用于额外的风险检查 |
| `keep_token` | `True` = 只检查不消费令牌（默认 `False`） |
| `expected_action` | 期望的 action，例如 `"login"`。令牌属于其他 action 时返回 `action_mismatch` |
| `expected_hostname` | 期望的域名（Web）或包名 / Bundle ID（原生），字符串或列表；`*.example.com` 匹配任意子域。不匹配时返回 `hostname_mismatch` |
| `bind_uid`、`bind_account`、`bind_email`、`bind_phone`、`scene` | 终端用户身份，与签发时绑定的身份比对（见 `binding_match`） |

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

| 属性 | 类型 | 说明 |
|---|---|---|
| `valid` | `bool` | 是否通过。唯一应当用于放行判断的字段 |
| `error` | `str \| None` | 错误码，例如 `token_expired`、`action_mismatch`、`request_failed` |
| `message` | `str \| None` | API 级错误的可读信息 |
| `action` | `str \| None` | 令牌对应的业务 action |
| `uid` | `str \| None` | 签发时通过 `bind_uid` 绑定的用户 ID |
| `challenge_id` | `str \| None` | 挑战 ID |
| `hostname` | `str \| None` | 完成验证的域名或包名 |
| `challenge_ts` | `str \| None` | 完成时间，ISO 8601 UTC |
| `risk_level` | `str \| None` | `low` / `medium` / `high` / `critical`，仅供参考 |
| `risk_labels` | `tuple[str, ...]` | 粗粒度风险类别，例如 `proxy`，仅供参考 |
| `captcha_args` | `CaptchaArgs \| None` | 验证时上下文：`platform`、`user_ip`、`referer`、`pkg`、`solved_at`、`risk_score`，仅供参考 |
| `user_ip` | `str \| None` | 验证时记录的用户 IP，仅供参考 |
| `binding` / `binding_match` | | 签发时绑定的身份，及逐字段比对结果 |
| `binding_mismatch` | `bool` | 任一 `binding_match` 字段为 `False` 时为 `True` |
| `degraded` / `degraded_reason` | | 配额耗尽时签发的 `dg_` 令牌，见下文 |
| `offline` / `client_only` / `warning` | | 故障兜底，见[令牌类型](#令牌类型) |
| `test` | `bool` | 来自公开测试 key 的结果，生产环境应拒绝 |
| `http_status`、`retry_after`、`retryable` | | 失败详情 |
| `cause` | `CaptchaLaError \| None` | API / 网络故障对应的类型化异常 |
| `raw` | `dict \| None` | 原始 `data` 对象 |

方法：`raise_if_invalid()`（未通过时抛出 `ValidationFailedError`）、`to_dict()`。

### 校验 `bind_uid`

若签发 server token 时传了 `bind_uid="user_42"`，校验后与期望用户比对：

```python
result = captchala.validate(token)
if result.valid and result.uid != expected_user_id:
    ...  # 该 pass token 属于其他用户，拒绝
```

也可以在校验时传入身份字段，再检查 `result.binding_mismatch`。

### `client.issue_server_token(action, **options) -> IssueResult`

签发一次性的 `sct_` server token，交给客户端 SDK 的 `serverToken` 参数。

| 选项 | 说明 |
|---|---|
| `bind_ip` | 终端用户 IP，从其他网络发起的挑战可能被拒绝 |
| `ttl` | 有效期（秒），服务端默认 300，最大 900 |
| `max_uses` | 可用于多少次通过流程（服务端默认 10） |
| `bind_uid` | 你的用户 ID，校验时以 `uid` 返回 |
| `bind_account`、`bind_email`、`bind_phone`、`scene` | 终端用户身份 |
| `bind_device_id`、`bind_fingerprint` | 绑定设备 ID / 浏览器指纹 |

```python
issue = captchala.issue_server_token("login", bind_uid=str(user.id), ttl=300)
if not issue.ok:
    return {"error": issue.error}, 503   # rate_limit_exceeded 等
return {"server_token": issue.token}
```

`IssueResult`：`ok`、`token`、`expires_in`、`issued_at`、`error`、`message`、`http_status`、`retry_after`、`retryable`、`cause`。

### `client.moderation_check(input, user_id=None)` / `client.moderation_text(text, user_id=None)`

多模态内容审核。`input` 为 OpenAI 兼容格式的列表，可用 `text_item()` / `image_url_item()` 构造。

```python
from captchala import text_item, image_url_item

m = captchala.moderation_check([text_item(comment), image_url_item(upload_url)], user_id=str(user.id))
if m.ok and m.flagged and m.has_category("violence", "csam"):
    ...  # 直接拦截

t = captchala.moderation_text("user comment here")
```

`ModerationResult`：`ok`、`flagged`、`categories`、`category_scores`、`content_type`、`raw`、`error`、`message`、`has_category(*names)`。类别集合取决于模型，请不要写死。

### `user_message(code)`

为错误码返回一条可以展示给终端用户的简短英文提示，用于表单错误。切勿向用户展示原始错误码；未知错误码返回通用提示。可用 gettext 等自行翻译。

## 错误、重试与超时

各方法总是返回结果对象，校验失败、API 错误、网络故障都不会抛异常。`result.error` 为简短错误码；若失败来自传输层或 API，`result.cause` 中是对应的类型化异常：

| 类 | 场景 |
|---|---|
| `NetworkError`（`connect_failed`） | DNS 失败、连接被拒 / 重置 |
| `RequestTimeoutError`（`NetworkError` 子类） | `timeout` 内无响应 |
| `AuthenticationError` | app key / secret 错误或缺失 |
| `RateLimitError` | 限流或配额，见 `retry_after` |
| `InvalidResponseError` | 响应体不是预期的 JSON |
| `APIError` | 其他 API 错误（以上三者的基类） |
| `ValidationFailedError` | 由 `result.raise_if_invalid()` 抛出 |

以上均继承 `CaptchaLaError`，带有 `code`。

重试采用带抖动的指数退避。连接失败和 HTTP 502 / 503 总会重试；超时、连接重置和 HTTP 504 对 `validate` 与 `issue_server_token` 重试，对内容审核不重试（内容可能已在处理）。限流响应（HTTP 429）不重试。注意 pass token 只能使用一次：如果首次请求已到达 API 并消费了令牌、但连接随后断开，重试会返回 `token_already_used`，结果仍是拒绝。

## Django

```python
# settings.py
CAPTCHALA_APP_KEY = "..."
CAPTCHALA_APP_SECRET = "..."
# 可选：CAPTCHALA_BASE_URL、CAPTCHALA_TIMEOUT、CAPTCHALA_REJECT_CLIENT_ONLY
```

表单字段。`cleaned_data` 中是 `ValidateResult`；错误文案来自 `user_message()`，`ValidationError` 的 code 为 API 错误码：

```python
from django import forms
from captchala.contrib.django import CaptchaLaField, CaptchaLaFormMixin

class LoginForm(CaptchaLaFormMixin, forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)
    captcha_token = CaptchaLaField(expected_action="login")

form = LoginForm(request.POST, request=request)   # 传 request= 以转发客户端 IP
if form.is_valid():
    result = form.cleaned_data["captcha_token"]
```

视图装饰器，同步和异步视图均可：

```python
from captchala.contrib.django import captchala_required

@captchala_required(action="login")
def login_view(request):
    request.captchala  # ValidateResult
    ...
```

失败时返回 HTTP 400 `{"error": "captcha_failed", "code": "<错误码>"}`，或 `on_failure(request, result)` 的返回值。其他选项：`hostname`、`fields`、`allow_degraded`、`client`。不用装饰器时可调用 `verify_request(request, ...)` 拿到结果。

## Flask

```python
from flask import Flask, g
from captchala.contrib.flask import CaptchaLa

app = Flask(__name__)
app.config.update(CAPTCHALA_APP_KEY="...", CAPTCHALA_APP_SECRET="...")
captcha = CaptchaLa(app)   # 或 captcha.init_app(app)

@app.post("/login")
@captcha.required(action="login")
def login():
    g.captchala  # ValidateResult
    ...
```

失败时返回 HTTP 400 `{"error": "captcha_failed", "code": "<错误码>"}`，或 `on_failure(result)` 的返回值。`captcha.verify(action=...)` 可自行校验当前请求。安装 `flask[async]` 后支持异步视图。

集成依次从表单 / JSON 字段 `captcha_token`（或 `captchala_token`）和请求头 `X-Captcha-Token` 读取令牌，并依次从 `CF-Connecting-IP`、`X-Forwarded-For` 第一项、`X-Real-IP` 和远端地址取用户 IP。如果你的应用前面没有会覆盖这些请求头的代理，任何人都可以伪造它们。IP 只是额外的风险信号。

## 令牌类型

| 前缀 | 来源 | 处理方式 |
|---|---|---|
| `pt_` | 主 API | 由 `validate()` 校验 |
| `offline_` | 服务中断期间由备用服务签发 | 自动向备用服务校验，`offline=True` |
| `dg_` | 主 API 降级（配额耗尽） | `valid` 恒为 `False`，检查 `degraded` 自行决定 |
| `client_` | 纯客户端占位令牌（原生 SDK） | 见下文 |
| `co_` | 纯客户端占位令牌（Web SDK） | 见下文 |

### 降级令牌

应用配额耗尽时，客户端 SDK 会直接以 `dg_` 令牌完成，不打断用户流程。`valid` 仍为 `False`。若希望在升级套餐前继续放行：

```python
if result.valid or result.degraded:
    ...  # 放行
```

Django / Flask 集成中对应 `allow_degraded=True`。

### 纯客户端令牌（`client_` / `co_`）

客户端 SDK 只有在 API 和备用服务都无法访问时才会生成此类令牌。它们没有签名，因此只有当你的服务器同样无法访问 API 时才会被接受：

1. 探测 API（2 秒超时）。只要有任何 HTTP 响应就说明没有故障：`valid=False`、`client_only=True`、`error="client_only_rejected_api_reachable"`。
2. 否则以同样方式探测备用服务。
3. 两者都不可达时：`valid=True`、`client_only=True`、`offline=True`，并带 `warning`。

探测结果在进程内缓存（可达 30 秒，不可达 5 秒），并发校验共享同一次探测。对登录、支付等敏感操作，可在故障期间也拒绝此类令牌：

```python
strict = Client(reject_client_only=True)
# client_ / co_ -> valid=False, error="client_only_rejected_by_policy"
```

## 测试你的集成

API 提供始终通过 / 始终失败的公开测试 key，无需完成验证码，见[测试 key](https://docs.captcha.la/api-reference#test-keys)。其结果 `test == True`，切勿在生产环境配置。

单元测试中可注入传输函数（同步）或 httpx mock transport（异步）：

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

## 开发

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
CAPTCHALA_APP_KEY=xxx CAPTCHALA_APP_SECRET=xxx .venv/bin/python scripts/live_smoke.py   # 线上冒烟，不会完成真实挑战
```

## 许可证

MIT
