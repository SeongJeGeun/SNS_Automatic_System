"""Scaffold-safe adapter for Ollama-style local model requests.

Importing this module performs no network calls and does not require Ollama to
be installed or running.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib import error, request


@dataclass(frozen=True)
class OllamaRequest:
    """Minimal request contract for a local Ollama generation call."""

    prompt: str
    model_name: str = "tinyllama"
    mode: str = "text"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OllamaResponse:
    """Structured result for an optional Ollama call."""

    text: str
    ok: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class OllamaAdapter:
    """Small optional adapter for a local Ollama HTTP endpoint."""

    def __init__(
        self,
        endpoint: str = "http://localhost:11434",
        model_name: str = "tinyllama",
        timeout_seconds: Optional[float] = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model_name = model_name
        self.timeout_seconds = coerce_timeout_seconds(timeout_seconds)

    def generate(self, request_data: OllamaRequest) -> OllamaResponse:
        """Attempt a local Ollama call and fail gracefully if unavailable.

        TODO: Add streaming support after runtime integration is approved.
        TODO: Add schema-aware response handling for JSON generation modes.
        TODO: Add explicit allow/deny policy before any production use.
        """
        if not request_data.prompt.strip():
            return OllamaResponse(
                text="",
                ok=False,
                error="prompt is required",
                metadata={"model_name": request_data.model_name, "mode": request_data.mode},
            )

        payload = {
            "model": request_data.model_name or self.model_name,
            "prompt": request_data.prompt,
            "stream": False,
        }
        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            f"{self.endpoint}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
            data = json.loads(raw)
        except (OSError, error.URLError, json.JSONDecodeError) as exc:
            return OllamaResponse(
                text="",
                ok=False,
                error=str(exc),
                metadata={
                    "endpoint": self.endpoint,
                    "model_name": payload["model"],
                    "timeout_seconds": self.timeout_seconds,
                },
            )

        return OllamaResponse(
            text=str(data.get("response", "")),
            ok=True,
            metadata={
                "endpoint": self.endpoint,
                "model_name": payload["model"],
                "timeout_seconds": self.timeout_seconds,
            },
        )


def coerce_timeout_seconds(value: Optional[Any] = None, default: float = 3.0) -> float:
    """Resolve the optional Ollama timeout without touching the network.

    TODO: Move timeout policy into a shared runtime config object if this path is
    approved for production use.
    """
    raw_value = value
    if raw_value is None:
        raw_value = os.getenv("OLLAMA_TIMEOUT_SECONDS")

    try:
        timeout = float(raw_value)
    except (TypeError, ValueError):
        timeout = default

    return max(0.1, timeout)


def build_default_ollama_adapter(
    model_name: str = "tinyllama",
    endpoint: str = "http://localhost:11434",
    timeout_seconds: Optional[float] = None,
) -> OllamaAdapter:
    """Create an Ollama adapter without checking the endpoint."""

    return OllamaAdapter(
        endpoint=endpoint,
        model_name=model_name,
        timeout_seconds=timeout_seconds,
    )
