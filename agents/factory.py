from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

from .base import BlogAgent


def _build_agent(name: str) -> BlogAgent:
    name = name.strip().lower()
    if name == "claude":
        from .claude_agent import ClaudeAgent
        return ClaudeAgent()
    if name == "local":
        from .local_agent import LocalAgent
        return LocalAgent()
    raise ValueError(f"Unknown agent backend: {name!r}")


def _wrap_engine_loader() -> BlogAgent:
    """Thin adapter that wraps the legacy EngineLoader/BaseWriter as a BlogAgent."""
    from bots.engine_loader import EngineLoader

    writer = EngineLoader().get_writer()

    class _EngineLoaderAdapter:
        def research(self, topic: str) -> str:
            return writer.write(f"Research this topic for a blog post: {topic}")

        def write(self, prompt: str, system: str = "") -> str:
            return writer.write(prompt, system)

        def media_prompts(self, draft: str) -> list[str]:
            result = writer.write(
                f"Generate exactly 3 image or media generation prompts for the following blog draft. "
                f"Return each prompt on its own line, nothing else.\n\n{draft}"
            )
            return [line.strip() for line in result.splitlines() if line.strip()]

    return _EngineLoaderAdapter()


def get_agent(task: str = "write") -> BlogAgent:
    """
    Select agent backend.

    Priority:
    1. AGENT_BACKEND_{TASK.upper()} (e.g. AGENT_BACKEND_WRITE=local)
    2. AGENT_BACKEND
    3. AGENT_FALLBACK chain (e.g. AGENT_FALLBACK=claude,local)
    4. Fall back to EngineLoader (legacy)

    AGENT_FALLBACK works standalone (without AGENT_BACKEND).
    """
    task_key = f"AGENT_BACKEND_{task.upper()}"
    backend = os.environ.get(task_key) or os.environ.get("AGENT_BACKEND")

    fallback_env = os.environ.get("AGENT_FALLBACK", "")
    fallback_entries = [e.strip() for e in fallback_env.split(",") if e.strip()]

    if backend:
        chain = [backend] + fallback_entries
    elif fallback_entries:
        chain = fallback_entries
    else:
        chain = []

    last_exc: Exception | None = None
    for name in chain:
        try:
            return _build_agent(name)
        except Exception as exc:
            last_exc = exc
            logger.debug("Agent backend %r failed: %s", name, exc)
            continue

    if last_exc is not None:
        logger.debug("All chain backends failed, falling back to EngineLoader")
    # All chain entries failed (or chain is empty) — fall back to EngineLoader
    return _wrap_engine_loader()
