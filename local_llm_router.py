"""Local-only LLM router for CEO/agent workflows.

This module intentionally supports local OpenAI-compatible endpoints only.
Default target is Ollama at http://localhost:11434/v1, but LM Studio can be used
by changing LOCAL_LLM_BASE_URL and LOCAL_LLM_MODEL in .env.

No import-time network calls.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - handled at runtime
    OpenAI = None


@dataclass
class LocalLLMResult:
    ok: bool
    provider: str
    model: str
    content: str
    error: Optional[str] = None


class LocalLLMRouter:
    """Small local-only router for Ollama/LM Studio OpenAI-compatible APIs."""

    def __init__(self):
        self.provider = os.getenv("LOCAL_LLM_PROVIDER", "ollama")
        self.base_url = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
        self.api_key = os.getenv("LOCAL_LLM_API_KEY", "ollama")
        self.model = os.getenv("LOCAL_LLM_MODEL", "qwen3:30b")
        self.timeout = float(os.getenv("LOCAL_LLM_TIMEOUT_SECONDS", "120"))

    def _client(self):
        if OpenAI is None:
            raise RuntimeError("openai package is not installed. Add openai to requirements.txt if needed.")
        return OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=self.timeout)

    def chat(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: Optional[int] = 1200,
    ) -> LocalLLMResult:
        try:
            response = self._client().chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content or ""
            return LocalLLMResult(
                ok=True,
                provider=self.provider,
                model=self.model,
                content=content.strip(),
            )
        except Exception as exc:
            return LocalLLMResult(
                ok=False,
                provider=self.provider,
                model=self.model,
                content="",
                error=str(exc),
            )

    def is_configured(self) -> bool:
        return bool(self.base_url and self.model)
