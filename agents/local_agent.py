from __future__ import annotations

import os


class LocalAgent:
    def __init__(self):
        url = os.environ.get("LOCAL_AGENT_URL")
        if not url:
            raise RuntimeError("LOCAL_AGENT_URL environment variable is not set")

        self._url = url.rstrip("/")
        self._token = os.environ.get("LOCAL_AGENT_TOKEN")
        self._schema = os.environ.get("LOCAL_AGENT_SCHEMA", "openai")
        self._model = os.environ.get("LOCAL_AGENT_MODEL", "llama3")

        import httpx

        headers: dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        self._client = httpx.Client(headers=headers, timeout=120.0)

    def _call(self, prompt: str, system: str = "") -> str:
        if self._schema == "openai":
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            body = {"model": self._model, "messages": messages}
            response = self._client.post(f"{self._url}/v1/chat/completions", json=body)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        else:
            body = {"prompt": prompt, "system": system}
            response = self._client.post(f"{self._url}/run", json=body)
            response.raise_for_status()
            data = response.json()
            return data["result"]

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
