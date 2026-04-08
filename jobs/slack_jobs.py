"""
jobs/slack_jobs.py
Job orchestration layer for the Slack-triggered blog pipeline.

Job lifecycle:
  requested -> running -> preview_ready -> published
                       -> failed
  preview_ready -> rejected
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Import config (DATA_DIR etc.)
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bots.blog_config import DATA_DIR, ensure_runtime_dirs

# Ensure data dirs exist on first import
ensure_runtime_dirs()

PENDING_DIR = DATA_DIR / "pending_review"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _job_path(job_id: str) -> Path:
    return PENDING_DIR / f"job_{job_id}.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Public CRUD
# ---------------------------------------------------------------------------

def create_job(topic: str, user_id: str, channel_id: str) -> str:
    """Create a new job record and persist it. Returns job_id."""
    job_id = str(uuid.uuid4())
    now = _now_iso()
    job = {
        "job_id": job_id,
        "topic": topic,
        "user_id": user_id,
        "channel_id": channel_id,
        "status": "requested",
        "created_at": now,
        "updated_at": now,
        "error": None,
        "result": {
            "title": None,
            "summary": None,
            "thumbnail_url": None,
            "draft_path": None,
        },
    }
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    _job_path(job_id).write_text(
        json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Job created: %s  topic=%r", job_id, topic)
    return job_id


def get_job(job_id: str) -> dict:
    """Load and return job dict. Raises FileNotFoundError if missing."""
    path = _job_path(job_id)
    if not path.exists():
        raise FileNotFoundError(f"Job not found: {job_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def update_job(job_id: str, **kwargs) -> dict:
    """
    Load job, apply keyword-argument updates, refresh updated_at, persist.
    Supports nested 'result' merging: pass result={...} to merge into existing result.
    Returns updated job dict.
    """
    job = get_job(job_id)
    # Merge result sub-dict rather than replacing entirely
    if "result" in kwargs and isinstance(kwargs["result"], dict):
        job["result"] = {**job.get("result", {}), **kwargs.pop("result")}
    job.update(kwargs)
    job["updated_at"] = _now_iso()
    _job_path(job_id).write_text(
        json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return job


# ---------------------------------------------------------------------------
# Slack notifications
# ---------------------------------------------------------------------------

def _notify_slack_preview(job_id: str) -> None:
    """Send a Block Kit preview message with Publish / Reject buttons."""
    job = get_job(job_id)
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    dashboard_url = os.environ.get("PUBLIC_DASHBOARD_URL", "http://localhost:8080")

    if not token:
        logger.warning("SLACK_BOT_TOKEN not set; skipping preview notification")
        return

    from slack_sdk import WebClient  # type: ignore

    client = WebClient(token=token)
    preview_url = f"{dashboard_url}/api/content/{job_id}"
    title = job["result"].get("title") or job["topic"]
    summary = job["result"].get("summary") or ""

    try:
        client.chat_postMessage(
            channel=job["channel_id"],
            text=f"✅ 미리보기 준비됨: {title}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{title}*\n{summary}",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "🔍 미리보기"},
                            "url": preview_url,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ 발행"},
                            "action_id": "publish",
                            "value": job_id,
                            "style": "primary",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ 반려"},
                            "action_id": "reject",
                            "value": job_id,
                            "style": "danger",
                        },
                    ],
                },
            ],
        )
        logger.info("Preview notification sent for job %s", job_id)
    except Exception as exc:
        logger.error("Failed to send Slack preview for job %s: %s", job_id, exc)


def _notify_slack_error(job_id: str, error: str) -> None:
    """Send a simple error message to the job's channel."""
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        logger.warning("SLACK_BOT_TOKEN not set; skipping error notification")
        return

    try:
        job = get_job(job_id)
    except FileNotFoundError:
        logger.error("Cannot notify error: job %s not found", job_id)
        return

    from slack_sdk import WebClient  # type: ignore

    client = WebClient(token=token)
    try:
        client.chat_postMessage(
            channel=job["channel_id"],
            text=f"❌ 작업 실패 (job: {job_id})\n{error}",
        )
        logger.info("Error notification sent for job %s", job_id)
    except Exception as exc:
        logger.error("Failed to send Slack error notification for job %s: %s", job_id, exc)


def _notify_slack_simple(job_id: str, text: str) -> None:
    """Send a plain text message to the job's channel."""
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        logger.warning("SLACK_BOT_TOKEN not set; skipping notification")
        return

    try:
        job = get_job(job_id)
    except FileNotFoundError:
        logger.error("Cannot notify: job %s not found", job_id)
        return

    from slack_sdk import WebClient  # type: ignore

    client = WebClient(token=token)
    try:
        client.chat_postMessage(channel=job["channel_id"], text=text)
    except Exception as exc:
        logger.error("Failed to send Slack message for job %s: %s", job_id, exc)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run_job(job_id: str) -> None:
    """
    Orchestrate the full pipeline for a job:
      research -> write -> media_prompts -> save draft -> notify Slack.
    Updates job status throughout; catches all exceptions and marks failed.
    """
    update_job(job_id, status="running")
    job = get_job(job_id)

    try:
        from agents.factory import get_agent  # type: ignore

        # 1. Research / collect
        agent = get_agent("research")
        research = agent.research(job["topic"])

        # 2. Write draft
        write_agent = get_agent("write")
        draft = write_agent.write(
            f"주제: {job['topic']}\n\n참고 자료:\n{research}",
            system="당신은 한국어 블로그 글 작성 전문가입니다.",
        )

        # 3. Generate media prompts
        media_agent = get_agent("media")
        image_prompts = media_agent.media_prompts(draft)

        # 4. Extract title (first non-empty line, stripped of leading #)
        lines = [l.strip() for l in draft.splitlines() if l.strip()]
        title = lines[0].lstrip("#").strip() if lines else job["topic"]

        # 5. Save draft to data/originals/
        originals_dir = DATA_DIR / "originals"
        originals_dir.mkdir(parents=True, exist_ok=True)
        draft_path = originals_dir / f"job_{job_id}_draft.txt"
        draft_path.write_text(draft, encoding="utf-8")

        # 6. Update job with preview_ready result
        update_job(
            job_id,
            status="preview_ready",
            result={
                "title": title,
                "summary": (draft[:200] + "...") if len(draft) > 200 else draft,
                "image_prompts": image_prompts,
                "draft_path": str(draft_path),
            },
        )

        logger.info("Job %s pipeline complete, notifying Slack", job_id)

        # 7. Notify Slack with preview
        _notify_slack_preview(job_id)

    except Exception as exc:
        err_msg = str(exc)
        logger.error("Job %s failed: %s", job_id, err_msg, exc_info=True)
        update_job(job_id, status="failed", error=err_msg)
        _notify_slack_error(job_id, err_msg)


# ---------------------------------------------------------------------------
# Publish / Reject
# ---------------------------------------------------------------------------

def publish_job(job_id: str, response_url: str) -> None:
    """
    Publish the job's draft to Blogger.
    Currently updates status to 'published' and notifies Slack.
    TODO: integrate bots.publisher_bot for actual Blogger upload.
    """
    job = get_job(job_id)

    if job["status"] != "preview_ready":
        logger.warning(
            "publish_job called on job %s with status=%r (expected 'preview_ready')",
            job_id,
            job["status"],
        )
        # Allow idempotent re-publish attempts by not raising here
        if job["status"] == "published":
            return

    # TODO: call bots.publisher_bot publish function when ready
    # from bots.publisher_bot import publish_article
    # publish_article(job["result"]["draft_path"], ...)

    update_job(job_id, status="published")
    logger.info("Job %s published", job_id)
    _notify_slack_simple(job_id, f"🚀 발행 완료! {job['result'].get('title', job_id)}")


def reject_job(job_id: str, response_url: str) -> None:
    """Mark job as rejected and notify Slack."""
    update_job(job_id, status="rejected")
    logger.info("Job %s rejected", job_id)
    _notify_slack_simple(job_id, "🗑️ 반려되었습니다.")
