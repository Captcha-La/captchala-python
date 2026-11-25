import json
from typing import Any, List

import pytest

import captchala
from captchala.errors import NetworkError, RequestTimeoutError


def ok(data: Any):
    return (200, {"Content-Type": "application/json"}, json.dumps({"code": 0, "msg": "success", "data": data}).encode())


def reply(status: int, body: Any, headers=None):
    raw = body.encode() if isinstance(body, str) else json.dumps(body).encode()
    return (status, {"Content-Type": "application/json", **(headers or {})}, raw)


REFUSED = NetworkError("connection refused", connect_failed=True)
RESET = NetworkError("connection reset")
TIMEOUT = RequestTimeoutError("timed out")


class FakeTransport:
    """Scripted transport: each step is a response tuple, an exception, or a callable. The last step repeats."""

    def __init__(self, *steps: Any) -> None:
        self.steps = steps
        self.calls: List[dict] = []

    def __call__(self, url, body, headers, timeout):
        self.calls.append({"url": url, "body": json.loads(body), "headers": dict(headers), "timeout": timeout})
        step = self.steps[min(len(self.calls) - 1, len(self.steps) - 1)]
        if isinstance(step, BaseException):
            raise step
        if callable(step):
            return step(url, body, headers, timeout)
        return step


@pytest.fixture(autouse=True)
def _reset_cache():
    captchala.reset_reachability_cache()
    yield
    captchala.reset_reachability_cache()


def make(transport, **kw):
    kw.setdefault("retry_backoff", 0)
    return captchala.Client("key_1", "secret_1", transport=transport, **kw)


SUCCESS = {
    "valid": True,
    "challenge_id": "ch_1",
    "action": "login",
    "uid": "user_42",
    "captcha_args": {"platform": "web", "user_ip": "1.2.3.4", "referer": "https://a.example/login", "pkg": None, "solved_at": 1750000000, "risk_score": 12},
    "hostname": "a.example",
    "challenge_ts": "2025-06-15T15:06:40Z",
    "risk_level": "low",
    "risk_labels": ["proxy"],
    "binding": {"uid": "user_42", "account": None, "email": "A@example.com", "phone": None, "scene": "login"},
    "binding_match": {"uid": True},
}
