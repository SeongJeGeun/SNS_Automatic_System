"""Scaffold for future platform-aware tone validation.

This module is intentionally not connected to the production pipeline.
Importing it performs no file I/O, network calls, publishing, scheduling, or
runtime state mutation.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ToneValidationRequest:
    """Minimal request contract for future tone checks."""

    text: str
    platform: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToneValidationResult:
    """Minimal result contract for future tone checks."""

    ok: bool
    findings: List[str] = field(default_factory=list)
    platform: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToneValidator:
    """Placeholder validator for platform-specific writing tone."""

    SUPPORTED_PLATFORMS = ("instagram", "threads")

    def validate(self, request: ToneValidationRequest) -> ToneValidationResult:
        """Run scaffold-only validation.

        TODO: Add Instagram tone rules for concise, structured, save-oriented copy.
        TODO: Add Threads tone rules for conversational, reply-oriented copy.
        TODO: Return actionable line/page findings when artifact paths are added.
        """
        platform = request.platform.strip().lower()
        findings: List[str] = []

        if platform not in self.SUPPORTED_PLATFORMS:
            findings.append(f"unsupported platform: {request.platform}")

        if not request.text.strip():
            findings.append("text is required")

        return ToneValidationResult(
            ok=not findings,
            findings=findings,
            platform=platform or None,
            metadata={"scaffold_only": True},
        )


def build_default_tone_validator() -> ToneValidator:
    """Create the placeholder tone validator without side effects."""

    return ToneValidator()

