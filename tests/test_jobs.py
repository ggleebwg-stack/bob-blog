"""
tests/test_jobs.py
Unit tests for jobs/slack_jobs.py
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on sys.path (conftest.py does this, but be explicit)
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_jobs():
    """Import after sys.path is set."""
    from jobs import slack_jobs
    return slack_jobs


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCreateJob:
    def test_returns_valid_uuid(self, tmp_path, monkeypatch):
        jobs = _import_jobs()
        monkeypatch.setattr(jobs, "PENDING_DIR", tmp_path)

        job_id = jobs.create_job("봄 캠핑 용품", "U123", "C123")

        # Must be a valid UUID4
        parsed = uuid.UUID(job_id, version=4)
        assert str(parsed) == job_id

    def test_saves_file(self, tmp_path, monkeypatch):
        jobs = _import_jobs()
        monkeypatch.setattr(jobs, "PENDING_DIR", tmp_path)

        job_id = jobs.create_job("봄 캠핑 용품", "U123", "C123")

        expected_file = tmp_path / f"job_{job_id}.json"
        assert expected_file.exists(), "Job file must be created in pending_review dir"

    def test_file_has_correct_structure(self, tmp_path, monkeypatch):
        jobs = _import_jobs()
        monkeypatch.setattr(jobs, "PENDING_DIR", tmp_path)

        job_id = jobs.create_job("봄 캠핑 용품", "U123", "C456")

        data = json.loads((tmp_path / f"job_{job_id}.json").read_text(encoding="utf-8"))
        assert data["job_id"] == job_id
        assert data["topic"] == "봄 캠핑 용품"
        assert data["user_id"] == "U123"
        assert data["channel_id"] == "C456"
        assert data["status"] == "requested"
        assert data["error"] is None
        assert isinstance(data["result"], dict)
        assert "title" in data["result"]
        assert "draft_path" in data["result"]


class TestGetJob:
    def test_returns_correct_data(self, tmp_path, monkeypatch):
        jobs = _import_jobs()
        monkeypatch.setattr(jobs, "PENDING_DIR", tmp_path)

        job_id = jobs.create_job("테스트 주제", "U999", "C999")
        retrieved = jobs.get_job(job_id)

        assert retrieved["job_id"] == job_id
        assert retrieved["topic"] == "테스트 주제"
        assert retrieved["user_id"] == "U999"

    def test_raises_file_not_found_for_missing_job(self, tmp_path, monkeypatch):
        jobs = _import_jobs()
        monkeypatch.setattr(jobs, "PENDING_DIR", tmp_path)

        with pytest.raises(FileNotFoundError):
            jobs.get_job("nonexistent-job-id")


class TestUpdateJob:
    def test_changes_status(self, tmp_path, monkeypatch):
        jobs = _import_jobs()
        monkeypatch.setattr(jobs, "PENDING_DIR", tmp_path)

        job_id = jobs.create_job("업데이트 테스트", "U1", "C1")
        updated = jobs.update_job(job_id, status="running")

        assert updated["status"] == "running"
        # Persisted to disk as well
        on_disk = jobs.get_job(job_id)
        assert on_disk["status"] == "running"

    def test_updated_at_changes(self, tmp_path, monkeypatch):
        jobs = _import_jobs()
        monkeypatch.setattr(jobs, "PENDING_DIR", tmp_path)

        job_id = jobs.create_job("업데이트 테스트", "U1", "C1")
        original = jobs.get_job(job_id)
        updated = jobs.update_job(job_id, status="running")

        # updated_at must be >= created_at (might equal if sub-ms precision)
        assert updated["updated_at"] >= original["created_at"]

    def test_result_is_merged_not_replaced(self, tmp_path, monkeypatch):
        jobs = _import_jobs()
        monkeypatch.setattr(jobs, "PENDING_DIR", tmp_path)

        job_id = jobs.create_job("머지 테스트", "U1", "C1")
        jobs.update_job(job_id, result={"title": "첫 번째 제목"})
        jobs.update_job(job_id, result={"draft_path": "/some/path.txt"})

        final = jobs.get_job(job_id)
        # Both fields should survive independent updates
        assert final["result"]["title"] == "첫 번째 제목"
        assert final["result"]["draft_path"] == "/some/path.txt"


class TestRunJob:
    def test_marks_preview_ready_on_success(self, tmp_path, monkeypatch):
        jobs = _import_jobs()
        monkeypatch.setattr(jobs, "PENDING_DIR", tmp_path)

        # Mock DATA_DIR / "originals" to use tmp_path
        originals = tmp_path / "originals"
        originals.mkdir()
        monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)

        job_id = jobs.create_job("성공 테스트", "U1", "C1")

        # Mock agents
        mock_agent = MagicMock()
        mock_agent.research.return_value = "리서치 결과물"
        mock_agent.write.return_value = "# 멋진 제목\n\n본문 내용입니다."
        mock_agent.media_prompts.return_value = ["프롬프트1", "프롬프트2"]

        # Mock Slack notification so no real token needed
        monkeypatch.setattr(jobs, "_notify_slack_preview", lambda jid: None)

        with patch("agents.factory.get_agent", return_value=mock_agent):
            jobs.run_job(job_id)

        result_job = jobs.get_job(job_id)
        assert result_job["status"] == "preview_ready"
        assert result_job["result"]["title"] == "멋진 제목"
        assert result_job["result"]["draft_path"] is not None
        # Draft file should exist
        assert Path(result_job["result"]["draft_path"]).exists()

    def test_marks_failed_on_agent_error(self, tmp_path, monkeypatch):
        jobs = _import_jobs()
        monkeypatch.setattr(jobs, "PENDING_DIR", tmp_path)
        monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)

        job_id = jobs.create_job("실패 테스트", "U1", "C1")

        # Mock get_agent to raise
        def boom(task):
            raise RuntimeError("에이전트 초기화 실패!")

        # Suppress Slack error notification
        monkeypatch.setattr(jobs, "_notify_slack_error", lambda jid, err: None)

        with patch("agents.factory.get_agent", side_effect=boom):
            jobs.run_job(job_id)

        result_job = jobs.get_job(job_id)
        assert result_job["status"] == "failed"
        assert "에이전트 초기화 실패!" in result_job["error"]

    def test_run_job_sets_running_before_pipeline(self, tmp_path, monkeypatch):
        """run_job must flip status to 'running' even if pipeline immediately fails."""
        jobs = _import_jobs()
        monkeypatch.setattr(jobs, "PENDING_DIR", tmp_path)
        monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)
        monkeypatch.setattr(jobs, "_notify_slack_error", lambda jid, err: None)

        job_id = jobs.create_job("러닝 테스트", "U1", "C1")

        status_seen: list[str] = []

        original_update = jobs.update_job

        def spy_update(jid, **kwargs):
            result = original_update(jid, **kwargs)
            status_seen.append(result["status"])
            return result

        monkeypatch.setattr(jobs, "update_job", spy_update)

        with patch("agents.factory.get_agent", side_effect=RuntimeError("boom")):
            jobs.run_job(job_id)

        assert "running" in status_seen
        assert "failed" in status_seen


class TestPublishJob:
    def test_publish_sets_published_status(self, tmp_path, monkeypatch):
        jobs = _import_jobs()
        monkeypatch.setattr(jobs, "PENDING_DIR", tmp_path)
        monkeypatch.setattr(jobs, "_notify_slack_simple", lambda jid, text: None)

        job_id = jobs.create_job("발행 테스트", "U1", "C1")
        # Fast-forward to preview_ready
        jobs.update_job(job_id, status="preview_ready", result={"title": "발행 제목"})

        jobs.publish_job(job_id, response_url="https://hooks.slack.com/fake")

        final = jobs.get_job(job_id)
        assert final["status"] == "published"


class TestRejectJob:
    def test_reject_sets_rejected_status(self, tmp_path, monkeypatch):
        jobs = _import_jobs()
        monkeypatch.setattr(jobs, "PENDING_DIR", tmp_path)
        monkeypatch.setattr(jobs, "_notify_slack_simple", lambda jid, text: None)

        job_id = jobs.create_job("반려 테스트", "U1", "C1")
        jobs.update_job(job_id, status="preview_ready")

        jobs.reject_job(job_id, response_url="https://hooks.slack.com/fake")

        final = jobs.get_job(job_id)
        assert final["status"] == "rejected"
