from __future__ import annotations

import os


class ClaudeAgent:
    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-6"):
        import anthropic

        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = anthropic.Anthropic(api_key=resolved_key)
        self._model = model

    def _call(self, prompt: str, system: str = "") -> str:
        import anthropic

        kwargs: dict = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        message = self._client.messages.create(**kwargs)
        text = message.content[0].text if message.content else ""
        if not text:
            raise RuntimeError("Claude returned empty response")
        return text

    def research(self, topic: str) -> str:
        return self._call(f"Research this topic for a blog post: {topic}")

    def write(self, prompt: str, system: str = "") -> str:
        return self._call(prompt, system=system)

    def media_prompts(self, draft: str) -> list[str]:
        result = self._call(
            f"Generate exactly 3 image or media generation prompts for the following blog draft. "
            f"Return each prompt on its own line, nothing else.\n\n{draft}"
        )
        lines = [line.strip() for line in result.splitlines() if line.strip()]
        return lines
