"""Scaffold for future interchangeable local model calls.

This module is intentionally not integrated with the production pipeline.
It must remain import-safe: no model loading, environment reads, network calls,
or subprocess execution should happen at import time.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class LocalModelRequest:
    """Minimal request contract for a future local model adapter."""

    prompt: str
    mode: str = "text"
    schema_hint: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LocalModelResponse:
    """Minimal response contract for future model output."""

    text: str
    ok: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class LocalModelBridge:
    """Placeholder adapter for future local model inference."""

    SUPPORTED_MODEL_FAMILIES = ("tinyllama", "gemma", "qwen", "llama3.2:3b")

    def __init__(self, model_name: str = "gemma") -> None:
        self.model_name = model_name

    def generate(self, request: LocalModelRequest) -> LocalModelResponse:
        """Return a non-executing placeholder response.

        TODO: Route to an approved local adapter, such as Ollama, outside import time.
        TODO: Add JSON/schema validation for structured generation modes.
        TODO: Add timeouts and deterministic error reporting before integration.
        """
        if not request.prompt.strip():
            return LocalModelResponse(
                text="",
                ok=False,
                error="prompt is required",
                metadata={"model_name": self.model_name, "mode": request.mode},
            )

        return LocalModelResponse(
            text="",
            ok=False,
            error="LocalModelBridge is scaffold-only and not connected to a model runtime.",
            metadata={"model_name": self.model_name, "mode": request.mode},
        )


GemmaRequest = LocalModelRequest
GemmaResponse = LocalModelResponse


class GemmaBridge(LocalModelBridge):
    """Backward-compatible name for the generic local model bridge."""


def build_default_bridge(model_name: str = "gemma") -> LocalModelBridge:
    """Create the placeholder bridge without side effects."""

    return LocalModelBridge(model_name=model_name)


def build_gemma_bridge(model_name: str = "gemma") -> GemmaBridge:
    """Create the backward-compatible Gemma bridge without side effects."""

    return GemmaBridge(model_name=model_name)
