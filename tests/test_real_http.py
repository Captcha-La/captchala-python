"""Exercises the default urllib transport against a local HTTP server."""

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import captchala
from captchala import NetworkError, RequestTimeoutError

hits = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
        hits.append({"path": self.path, "headers": dict(self.headers), "body": body})
        token = body.get("pass_token")
        if token == "pt_slow":
            threading.Event().wait(1.0)
            return
        if token == "pt_flaky" and sum(h["body"].get("pass_token") == "pt_flaky" for h in hits) == 1:
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b"busy")
            return
        if token == "pt_401":
            data = json.dumps({"code": -1, "error": "token_not_found", "message": "x"}).encode()
            self.send_response(401)
        else:
            valid = token in ("pt_good", "pt_flaky")
            data = json.dumps({"code": 0, "data": {"valid": True, "action": "login"} if valid else {"valid": False, "error": "token_not_found"}}).encode()
            self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture(scope="module")
def base():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    srv.daemon_threads = True
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def closed_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return f"http://127.0.0.1:{port}"


def client(base, **kw):
    kw.setdefault("retry_backoff", 0)
    return captchala.Client("k", "s", base_url=base, **kw)


def test_success_and_invalid(base):
    assert client(base).validate("pt_good").valid
    bad = client(base).validate("pt_bogus")
    assert not bad.valid and bad.error == "token_not_found"
    h = hits[-1]
    assert h["path"] == "/v1/validate" and h["headers"]["X-App-Key"] == "k" and h["headers"]["X-App-Secret"] == "s"


def test_non_2xx_body_is_read(base):
    r = client(base).validate("pt_401")
    assert r.error == "token_not_found" and r.http_status == 401


def test_503_then_success(base):
    assert client(base).validate("pt_flaky").valid


def test_timeout(base):
    r = client(base, timeout=0.2, max_retries=0).validate("pt_slow")
    assert isinstance(r.cause, RequestTimeoutError)


def test_connection_refused():
    r = client(closed_port(), max_retries=1).validate("pt_x")
    assert r.error == "request_failed" and isinstance(r.cause, NetworkError) and r.cause.connect_failed


def test_client_only_total_outage(base):
    down = captchala.Client("k", "s", base_url=closed_port(), backup_url=closed_port())
    assert down.validate("co_x").valid
    captchala.reset_reachability_cache()
    assert not client(base, backup_url=closed_port()).validate("co_x").valid
