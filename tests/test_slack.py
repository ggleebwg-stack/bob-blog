from __future__ import annotations

import hashlib
import hmac
import time
import urllib.parse

import pytest
from fastapi.testclient import TestClient

from integrations.slack_app import router, verify_slack_signature

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SECRET = "test_signing_secret"


def _make_signature(body: str, timestamp: str, secret: str = SECRET) -> str:
    """Return a valid Slack-format HMAC-SHA256 signature."""
    base = f"v0:{timestamp}:{body}".encode()
    digest = hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def _fresh_ts() -> str:
    return str(int(time.time()))


def _old_ts() -> str:
    """Timestamp 6 minutes in the past — beyond the 5-minute replay window."""
    return str(int(time.time()) - 361)


# ---------------------------------------------------------------------------
# Unit tests for verify_slack_signature
# ---------------------------------------------------------------------------

def test_valid_signature_accepted():
    body = "command=%2Fwrite&text=hello"
    ts = _fresh_ts()
    sig = _make_signature(body, ts)
    assert verify_slack_signature(body.encode(), ts, sig, SECRET) is True


def test_invalid_signature_rejected():
    body = "command=%2Fwrite&text=hello"
    ts = _fresh_ts()
    wrong_sig = "v0=deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    assert verify_slack_signature(body.encode(), ts, wrong_sig, SECRET) is False


def test_replay_attack_rejected():
    body = "command=%2Fwrite&text=hello"
    old_ts = _old_ts()
    sig = _make_signature(body, old_ts)
    # Even a cryptographically valid signature must be rejected if too old
    assert verify_slack_signature(body.encode(), old_ts, sig, SECRET) is False


# ---------------------------------------------------------------------------
# Integration tests via TestClient
# ---------------------------------------------------------------------------

def _build_app():
    """Build a minimal FastAPI app with the slack router and test secret."""
    import os
    os.environ["SLACK_SIGNING_SECRET"] = SECRET

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/slack")
    return app


def _signed_headers(body: str) -> dict:
    ts = _fresh_ts()
    sig = _make_signature(body, ts)
    return {
        "X-Slack-Request-Timestamp": ts,
        "X-Slack-Signature": sig,
        "Content-Type": "application/x-www-form-urlencoded",
    }


def test_empty_text_returns_usage_hint():
    app = _build_app()
    client = TestClient(app, raise_server_exceptions=True)

    form_data = {"command": "/write", "text": "", "user_id": "U123", "channel_id": "C123"}
    body = urllib.parse.urlencode(form_data)

    resp = client.post(
        "/slack/commands",
        content=body,
        headers=_signed_headers(body),
    )
    assert resp.status_code == 200
    assert "사용법" in resp.json()["text"]


def test_unknown_command_returns_unknown():
    app = _build_app()
    client = TestClient(app, raise_server_exceptions=True)

    form_data = {"command": "/unknown", "text": "hello", "user_id": "U123", "channel_id": "C123"}
    body = urllib.parse.urlencode(form_data)

    resp = client.post(
        "/slack/commands",
        content=body,
        headers=_signed_headers(body),
    )
    assert resp.status_code == 200
    assert resp.json()["text"] == "Unknown command"


def test_valid_write_command_accepted():
    app = _build_app()
    client = TestClient(app, raise_server_exceptions=True)

    form_data = {
        "command": "/write",
        "text": "Python 비동기 프로그래밍",
        "user_id": "U123",
        "channel_id": "C123",
        "response_url": "https://hooks.slack.com/actions/xxx",
    }
    body = urllib.parse.urlencode(form_data)

    resp = client.post(
        "/slack/commands",
        content=body,
        headers=_signed_headers(body),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["response_type"] == "ephemeral"
    assert "접수" in data["text"]


def test_invalid_signature_returns_403():
    app = _build_app()
    client = TestClient(app, raise_server_exceptions=True)

    form_data = {"command": "/write", "text": "hello"}
    body = urllib.parse.urlencode(form_data)

    resp = client.post(
        "/slack/commands",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": _fresh_ts(),
            "X-Slack-Signature": "v0=badhash",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    assert resp.status_code == 403
