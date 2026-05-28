"""Scaffold for future structured artifact validation.

This module is intentionally passive. Importing it performs no file reads,
file writes, network calls, scheduling, publishing, or runtime integration.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


@dataclass(frozen=True)
class SchemaValidationRequest:
    """Minimal request contract for JSON-like artifact validation."""

    artifact_name: str
    payload: Mapping[str, Any]
    required_fields: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SchemaValidationResult:
    """Minimal result contract for structured validation."""

    ok: bool
    artifact_name: str
    findings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SchemaValidator:
    """Placeholder validator for generated JSON-like artifacts."""

    def validate(self, request: SchemaValidationRequest) -> SchemaValidationResult:
        """Run minimal structural checks without external dependencies.

        TODO: Add artifact-specific schemas for strategy, script, quality reports,
        TODO: publish plans, and final status outputs.
        TODO: Add path-aware validation when job-scoped artifacts are introduced.
        """
        findings: List[str] = []

        if not request.artifact_name.strip():
            findings.append("artifact_name is required")

        for field_name in request.required_fields:
            if field_name not in request.payload:
                findings.append(f"missing required field: {field_name}")

        return SchemaValidationResult(
            ok=not findings,
            artifact_name=request.artifact_name,
            findings=findings,
            metadata={"scaffold_only": True},
        )


def build_default_schema_validator() -> SchemaValidator:
    """Create the placeholder schema validator without side effects."""

    return SchemaValidator()


AUDIENCE_INSIGHT_DRAFT_FIELDS = [
    "artifact_type",
    "status",
    "source",
    "model",
    "endpoint",
    "generated_text",
    "context_notes",
    "insight_summary",
    "audience_signals",
    "content_angles",
    "audience_state",
    "core_pains",
    "emotional_keywords",
    "needed_message",
    "story_angle",
    "content_principles",
    "compatibility",
    "error",
]


def validate_audience_insight_draft(payload: Mapping[str, Any]) -> SchemaValidationResult:
    """Validate the standalone local audience insight draft shape.

    TODO: Align this helper with the production audience insight schema once that
    schema is approved for runtime use.
    """
    return SchemaValidator().validate(
        SchemaValidationRequest(
            artifact_name="audience_insight.local_draft.json",
            payload=payload,
            required_fields=AUDIENCE_INSIGHT_DRAFT_FIELDS,
        )
    )


def _has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _has_list_item(value: Any) -> bool:
    return isinstance(value, list) and any(str(item or "").strip() for item in value)


def validate_audience_insight_quality(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Check minimal audience-insight readiness without blocking runtime.

    TODO: Add deeper content quality scoring only after thresholds and ownership
    are approved.
    """
    warnings: List[str] = []

    if not _has_text(payload.get("audience_state")):
        warnings.append("audience_state is missing or empty")
    if not _has_list_item(payload.get("core_pains")):
        warnings.append("core_pains must contain at least one item")
    if not _has_list_item(payload.get("emotional_keywords")):
        warnings.append("emotional_keywords must contain at least one item")
    if not _has_text(payload.get("story_angle")):
        warnings.append("story_angle is missing or empty")
    if not _has_list_item(payload.get("content_principles")):
        warnings.append("content_principles must contain at least one item")

    return {
        "ok": not warnings,
        "warnings": warnings,
    }
