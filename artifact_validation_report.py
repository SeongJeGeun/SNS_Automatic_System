"""Read-only validation report helper for mirrored artifacts.

This module is not connected to the production pipeline. Importing it performs
no file I/O, network calls, publishing, scheduling, or runtime state mutation.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from schema_validator import SchemaValidationRequest, SchemaValidator
from tone_validator import ToneValidationRequest, ToneValidator


REQUIRED_FIELDS_BY_TYPE = {
    "audience_insight": ["audience_state"],
    "strategy": ["target_reader", "core_promise"],
    "script": ["title", "pages"],
}


def _base_summary(artifact_path: str, artifact_type: str) -> Dict[str, Any]:
    return {
        "artifact_path": artifact_path,
        "artifact_type": artifact_type,
        "schema_check": {"ok": False, "findings": []},
        "tone_check": {"ok": True, "findings": [], "platform": None},
        "warnings": [],
        "passed": False,
    }


def _tone_text(payload: Mapping[str, Any]) -> str:
    for field_name in ("audience_state", "needed_message", "title"):
        value = payload.get(field_name)
        if isinstance(value, str) and value.strip():
            return value

    pages = payload.get("pages")
    if isinstance(pages, list) and pages:
        first_page = pages[0]
        if isinstance(first_page, Mapping):
            parts = [
                str(first_page.get("heading", "")).strip(),
                str(first_page.get("sub_text", "")).strip(),
            ]
            return " ".join(part for part in parts if part)

    return ""


def validate_artifact_report(
    artifact_path: str,
    *,
    artifact_type: str = "audience_insight",
    platform: str = "instagram",
    schema_validator: Optional[SchemaValidator] = None,
    tone_validator: Optional[ToneValidator] = None,
) -> Dict[str, Any]:
    """Return a deterministic validation summary for one artifact path.

    Missing or invalid artifacts return graceful report dictionaries.

    TODO: Add artifact-type specific tone extraction rules.
    TODO: Persist reports under job-scoped `reports/` only after integration approval.
    TODO: Keep this report non-blocking unless a later batch explicitly changes policy.
    """
    summary = _base_summary(artifact_path, artifact_type)
    path = Path(artifact_path)

    if not path.exists():
        summary["warnings"].append("artifact is missing")
        summary["schema_check"]["findings"].append("artifact file does not exist")
        return summary

    if not path.is_file():
        summary["warnings"].append("artifact path is not a file")
        summary["schema_check"]["findings"].append("artifact path is not a file")
        return summary

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        summary["warnings"].append("artifact is not valid JSON")
        summary["schema_check"]["findings"].append(str(exc))
        return summary

    if not isinstance(payload, Mapping):
        summary["warnings"].append("artifact JSON root is not an object")
        summary["schema_check"]["findings"].append("payload must be a JSON object")
        return summary

    schema = schema_validator or SchemaValidator()
    required_fields = REQUIRED_FIELDS_BY_TYPE.get(artifact_type, [])
    schema_result = schema.validate(
        SchemaValidationRequest(
            artifact_name=path.name,
            payload=payload,
            required_fields=required_fields,
        )
    )
    summary["schema_check"] = {
        "ok": schema_result.ok,
        "findings": list(schema_result.findings),
    }

    tone_text = _tone_text(payload)
    if tone_text:
        tone = tone_validator or ToneValidator()
        tone_result = tone.validate(
            ToneValidationRequest(text=tone_text, platform=platform)
        )
        summary["tone_check"] = {
            "ok": tone_result.ok,
            "findings": list(tone_result.findings),
            "platform": tone_result.platform,
        }
    else:
        summary["warnings"].append("no tone-checkable text found")
        summary["tone_check"] = {
            "ok": True,
            "findings": [],
            "platform": platform,
        }

    summary["passed"] = bool(
        summary["schema_check"]["ok"] and summary["tone_check"]["ok"]
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate one artifact in read-only mode.")
    parser.add_argument("artifact_path")
    parser.add_argument("--artifact-type", default="audience_insight")
    parser.add_argument("--platform", default="instagram")
    args = parser.parse_args()

    summary = validate_artifact_report(
        args.artifact_path,
        artifact_type=args.artifact_type,
        platform=args.platform,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

