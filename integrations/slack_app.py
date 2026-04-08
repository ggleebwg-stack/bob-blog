from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def verify_slack_signature(
    request_body: bytes,
    timestamp: str,
    signature: str,
    secret: str,
) -> bool:
    """Return True only when the HMAC-SHA256 signature is valid and fresh."""
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False

    # Reject replayed requests older than 5 minutes
    if abs(time.time() - ts) > 300:
        return False

    base_string = f"v0:{timestamp}:{request_body.decode('utf-8')}".encode()
    computed = hmac.new(secret.encode(), base_string, hashlib.sha256).hexdigest()
    expected = f"v0={computed}"
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Background / placeholder helpers
# ---------------------------------------------------------------------------

async def queue_write_job(topic: str, user_id: str, channel_id: str) -> None:
    """Placeholder: log the job request. Will be wired to jobs/slack_jobs.py."""
    import logging
    logging.getLogger(__name__).info(
        "Job queued: topic=%r user=%r channel=%r", topic, user_id, channel_id
    )


def handle_publish(job_id: str, response_url: str) -> None:
    """Placeholder: log publish request."""
    import logging
    logging.getLogger(__name__).info("Publish requested for job %r", job_id)


def handle_reject(job_id: str, response_url: str) -> None:
    """Placeholder: log reject request."""
    import logging
    logging.getLogger(__name__).info("Reject requested for job %r", job_id)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/commands")
async def slack_commands(
    request: Request,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    import os

    # Read raw body FIRST so it is available for both signature check and parsing
    body = await request.body()

    # --- Signature verification ---
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    secret = os.environ.get("SLACK_SIGNING_SECRET", "")

    if not verify_slack_signature(body, timestamp, signature, secret):
        return JSONResponse({"error": "Invalid signature"}, status_code=403)

    # --- Parse URL-encoded form body manually ---
    form = dict(urllib.parse.parse_qsl(body.decode("utf-8")))
    command = form.get("command", "")
    text = form.get("text", "")
    user_id = form.get("user_id", "")
    channel_id = form.get("channel_id", "")

    # --- Command dispatch ---
    if command != "/write":
        return JSONResponse({"text": "Unknown command"}, status_code=200)

    if not text.strip():
        return JSONResponse(
            {"text": "사용법: /write <주제> [키워드] [톤]"},
            status_code=200,
        )

    # Enqueue background work; respond immediately (within 3 s)
    background_tasks.add_task(queue_write_job, text, user_id, channel_id)

    return JSONResponse(
        {
            "response_type": "ephemeral",
            "text": "✍️ 글 작성 요청을 접수했습니다. 잠시 후 미리보기 링크를 보내드립니다.",
        },
        status_code=200,
    )


@router.post("/interactivity")
async def slack_interactivity(request: Request) -> JSONResponse:
    import os

    # Read raw body FIRST
    body = await request.body()

    # --- Signature verification ---
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    secret = os.environ.get("SLACK_SIGNING_SECRET", "")

    if not verify_slack_signature(body, timestamp, signature, secret):
        return JSONResponse({"error": "Invalid signature"}, status_code=403)

    # --- Parse payload field from URL-encoded body ---
    form = dict(urllib.parse.parse_qsl(body.decode("utf-8")))
    raw_payload = form.get("payload", "")

    try:
        data = json.loads(raw_payload)
    except (json.JSONDecodeError, TypeError):
        return JSONResponse({"error": "Bad payload"}, status_code=400)

    actions = data.get("actions", [])
    if not actions:
        return JSONResponse({}, status_code=200)

    action = actions[0]
    action_id = action.get("action_id", "")
    job_id = action.get("value", "")
    response_url = data.get("response_url", "")

    if action_id == "publish":
        handle_publish(job_id, response_url)
    elif action_id == "reject":
        handle_reject(job_id, response_url)

    return JSONResponse({}, status_code=200)
