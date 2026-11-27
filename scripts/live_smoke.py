"""Live smoke test against the real API. Never solves a challenge.

    CAPTCHALA_APP_KEY=... CAPTCHALA_APP_SECRET=... python scripts/live_smoke.py

Prints no secrets and no full tokens.
"""

import asyncio
import sys

from captchala import AsyncClient, AuthenticationError, Client

PASS_KEY = ("test_pass_7f3c9a2e5b18d4f6", "test_secret_pass_c41e8b0d27a95f3e")
FAIL_KEY = ("test_fail_2d9e6b4a0c7f1835", "test_secret_fail_9b5f03e7d1a46c28")
failed = 0


def check(name, cond, detail=""):
    global failed
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    failed += 0 if cond else 1


client = Client()

r = client.validate("pt_sdk_smoke_bogus_token", client_ip="203.0.113.7", expected_action="login")
check("bogus token is invalid", not r.valid and isinstance(r.error, str) and r.cause is None, f"error={r.error}")

check("empty token rejected locally", client.validate("").error == "empty_token")

w = Client(client.app_key, "wrong-secret").validate("pt_x")
check("wrong secret -> AuthenticationError", isinstance(w.cause, AuthenticationError), f"error={w.error}")

i = client.issue_server_token("login", ttl=60, max_uses=1)
check("issue server token", i.ok and (i.token or "").startswith("sct_"),
      f"token={i.token[:8]}..., expires_in={i.expires_in}" if i.ok else f"error={i.error}")

p = Client(*PASS_KEY).validate("pt_anything")
check("public always-pass test key", p.valid and p.test, f"risk_level={p.risk_level}")

f = Client(*FAIL_KEY).validate("pt_anything")
check("public always-fail test key", not f.valid and f.error == "test_always_fail")

s = Client(PASS_KEY[0], FAIL_KEY[1]).validate("pt_anything")
check("test key with wrong secret -> invalid_app_secret", not s.valid and s.error == "invalid_app_secret")


async def run_async():
    async with AsyncClient() as ac:
        a = await ac.validate("pt_sdk_smoke_bogus_token")
        check("async: bogus token is invalid", not a.valid and a.cause is None, f"error={a.error}")
    async with AsyncClient(*PASS_KEY) as ac:
        a = await ac.validate("pt_anything")
        check("async: always-pass test key", a.valid and a.test)


asyncio.run(run_async())
sys.exit(1 if failed else 0)
