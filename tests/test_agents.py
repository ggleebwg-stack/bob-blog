"""Tests for the agents/ abstraction layer."""
import pytest


def test_factory_returns_claude_agent_when_env_set(monkeypatch):
    monkeypatch.setenv("AGENT_BACKEND", "claude")
    # Remove any task-specific override so AGENT_BACKEND is used
    monkeypatch.delenv("AGENT_BACKEND_WRITE", raising=False)
    monkeypatch.delenv("AGENT_FALLBACK", raising=False)
    # Provide a dummy key so ClaudeAgent.__init__ doesn't fail on missing key
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    from agents.factory import get_agent
    from agents.claude_agent import ClaudeAgent

    agent = get_agent()
    assert isinstance(agent, ClaudeAgent)


def test_factory_returns_local_agent_when_env_set(monkeypatch):
    monkeypatch.setenv("AGENT_BACKEND", "local")
    monkeypatch.delenv("AGENT_BACKEND_WRITE", raising=False)
    monkeypatch.delenv("AGENT_FALLBACK", raising=False)
    monkeypatch.setenv("LOCAL_AGENT_URL", "http://localhost:11434")

    from agents.factory import get_agent
    from agents.local_agent import LocalAgent

    agent = get_agent()
    assert isinstance(agent, LocalAgent)


def test_local_agent_raises_without_url(monkeypatch):
    monkeypatch.delenv("LOCAL_AGENT_URL", raising=False)

    from agents.local_agent import LocalAgent

    with pytest.raises(RuntimeError, match="LOCAL_AGENT_URL"):
        LocalAgent()


def test_fallback_chain_used_when_no_primary(monkeypatch):
    monkeypatch.delenv("AGENT_BACKEND", raising=False)
    monkeypatch.delenv("AGENT_BACKEND_WRITE", raising=False)
    monkeypatch.setenv("AGENT_FALLBACK", "local")
    monkeypatch.setenv("LOCAL_AGENT_URL", "http://x")

    from agents.factory import get_agent
    from agents.local_agent import LocalAgent

    agent = get_agent()
    assert isinstance(agent, LocalAgent)
