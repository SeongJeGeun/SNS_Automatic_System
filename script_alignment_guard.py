"""CEO topic guidance vs script alignment guard.

Best-effort validation only. This module does not block publishing.
It compares agent_runs/ceo_topic_guidance.json with script.json and writes a
small report to agent_runs/script_alignment_report.json.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict

GUIDANCE_FILE = os.path.join("agent_runs", "ceo_topic_guidance.json")
SCRIPT_FILE = "script.json"
REPORT_FILE = os.path.join("agent_runs", "script_alignment_report.json")


def _load_json(path: str, default: Any):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def check_alignment(
    guidance_path: str = GUIDANCE_FILE,
    script_path: str = SCRIPT_FILE,
    report_path: str = REPORT_FILE,
) -> Dict[str, Any]:
    guidance = _load_json(guidance_path, {})
    script = _load_json(script_path, {})
    quality_intent = script.get("quality_intent") if isinstance(script, dict) else {}
    if not isinstance(quality_intent, dict):
        quality_intent = {}

    expected_topic_key = guidance.get("topic_key") if isinstance(guidance, dict) else None
    actual_topic_key = quality_intent.get("ceo_topic_key")
    expected_title = guidance.get("topic_title") if isinstance(guidance, dict) else None
    actual_title = script.get("title") if isinstance(script, dict) else None

    ok = True
    warnings = []

    if not guidance:
        ok = True
        warnings.append("CEO topic guidance missing; fallback generator mode assumed.")
    elif not script:
        ok = False
        warnings.append("script.json missing; cannot validate alignment.")
    else:
        if expected_topic_key and actual_topic_key != expected_topic_key:
            ok = False
            warnings.append(
                f"topic_key mismatch: expected={expected_topic_key}, actual={actual_topic_key}"
            )
        if expected_title and actual_title and expected_title not in actual_title and actual_title not in expected_title:
            warnings.append(
                f"title differs from guidance: expected~={expected_title}, actual={actual_title}"
            )

    report = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ok": ok,
        "warnings": warnings,
        "expected_topic_key": expected_topic_key,
        "actual_topic_key": actual_topic_key,
        "expected_title": expected_title,
        "actual_title": actual_title,
        "script_template_id": quality_intent.get("template_id"),
        "script_template_title": quality_intent.get("template_title"),
    }
    _write_json(report_path, report)

    if ok:
        print("[Script Alignment] OK: CEO guidance and script are aligned")
    else:
        print(f"[Script Alignment] WARNING: {warnings}")
    return report


if __name__ == "__main__":
    check_alignment()
