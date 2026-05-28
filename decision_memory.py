"""Decision Maker memory journal.

Stores one JSONL event per publish cycle so the local CEO agent can later learn
from topics, quality, platform outcomes, and operational warnings.

No import-time side effects. All helpers are lightweight and local-file only.
"""

from __future__ import annotations

import glob
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

MEMORY_FILE = os.path.join("agent_runs", "decision_memory.jsonl")


def _load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _append_jsonl(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        f.write("\n")


def append_decision(event: Dict[str, Any], memory_file: str = MEMORY_FILE) -> bool:
    payload = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **event,
    }
    _append_jsonl(memory_file, payload)
    return True


def load_recent_decisions(limit: int = 20, memory_file: str = MEMORY_FILE) -> List[Dict[str, Any]]:
    if not os.path.exists(memory_file):
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with open(memory_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return rows[-limit:]


def _first_existing_json(paths: List[str], default: Any) -> Any:
    for path in paths:
        data = _load_json(path, None)
        if data is not None:
            return data
    return default


def _latest_matching_json(patterns: List[str]) -> Optional[Dict[str, Any]]:
    candidates: List[str] = []
    for pattern in patterns:
        candidates.extend(glob.glob(pattern))
    candidates = [p for p in candidates if os.path.isfile(p)]
    if not candidates:
        return None
    latest = max(candidates, key=lambda p: os.path.getmtime(p))
    data = _load_json(latest, {})
    if isinstance(data, dict):
        data["_source_path"] = latest
        return data
    return {"_source_path": latest, "value": data}


def _quality_summary() -> Dict[str, Any]:
    report = _first_existing_json(
        [
            "content_quality_report.json",
            "quality_report.json",
            os.path.join("agent_runs", "content_quality_report.json"),
        ],
        {},
    )
    feedback = _load_json("content_quality_feedback.json", {})
    if not isinstance(report, dict):
        report = {}
    if not isinstance(feedback, dict):
        feedback = {}
    return {
        "ok": report.get("ok") or report.get("passed") or report.get("quality_ok"),
        "score": report.get("score"),
        "minimum_score": report.get("minimum_score") or report.get("threshold"),
        "warnings": report.get("warnings") or feedback.get("warnings") or feedback.get("issues") or [],
    }


def _platform_summary() -> Dict[str, Any]:
    instagram_report = _latest_matching_json([
        "*instagram*report*.json",
        os.path.join("agent_runs", "*instagram*report*.json"),
        os.path.join("shared", "*instagram*report*.json"),
    ])
    threads_report = _latest_matching_json([
        "*threads*report*.json",
        os.path.join("agent_runs", "*threads*report*.json"),
        os.path.join("shared", "*threads*report*.json"),
    ])
    cooldown = _load_json(os.path.join("agent_runs", "instagram_publish_cooldown.json"), {})

    return {
        "instagram": {
            "cooldown_active": bool(cooldown),
            "report": instagram_report,
        },
        "threads": {
            "report": threads_report,
        },
    }


def build_publish_cycle_event(event_type: str = "publish_cycle_completed") -> Dict[str, Any]:
    script = _load_json("script.json", {})
    ceo_guidance = _load_json(os.path.join("agent_runs", "ceo_topic_guidance.json"), {})
    ceo_report = _load_json(os.path.join("agent_runs", "ceo_cycle_report.json"), {})
    alignment = _load_json(os.path.join("agent_runs", "script_alignment_report.json"), {})
    template_validation = _load_json(os.path.join("agent_runs", "template_pack_validation_report.json"), {})
    agent_status = _load_json(os.path.join("agent_runs", "agent_status.json"), {})
    performance = _load_json(os.path.join("shared", "performance_log.json"), [])

    if not isinstance(script, dict):
        script = {}
    if not isinstance(ceo_guidance, dict):
        ceo_guidance = {}
    if not isinstance(agent_status, dict):
        agent_status = {}

    quality_intent = script.get("quality_intent") if isinstance(script.get("quality_intent"), dict) else {}
    series = script.get("series") if isinstance(script.get("series"), dict) else {}

    return {
        "event_type": event_type,
        "job_id": agent_status.get("current_job_id") or os.getenv("JOB_ID"),
        "topic": {
            "title": script.get("title"),
            "ceo_topic_key": quality_intent.get("ceo_topic_key") or ceo_guidance.get("topic_key"),
            "ceo_emotion_axis": quality_intent.get("ceo_emotion_axis") or ceo_guidance.get("emotion_axis"),
            "template_id": quality_intent.get("template_id"),
            "template_title": quality_intent.get("template_title"),
        },
        "series": series,
        "quality": _quality_summary(),
        "platforms": _platform_summary(),
        "ceo": {
            "guidance": ceo_guidance,
            "recommendation": ceo_report.get("ceo_recommendation") if isinstance(ceo_report, dict) else None,
        },
        "guards": {
            "script_alignment": alignment,
            "template_validation": template_validation,
        },
        "performance_snapshot": {
            "row_count": len(performance) if isinstance(performance, list) else None,
            "latest": performance[-1] if isinstance(performance, list) and performance else None,
        },
        "next_learning_note": _next_learning_note(script, ceo_guidance, alignment),
    }


def _next_learning_note(script: Dict[str, Any], ceo_guidance: Dict[str, Any], alignment: Any) -> str:
    title = script.get("title") or ceo_guidance.get("topic_title") or "unknown"
    alignment_ok = alignment.get("ok") if isinstance(alignment, dict) else None
    if alignment_ok is False:
        return f"다음 회차에서는 CEO 주제와 실제 대본 정합성을 우선 보정하세요: {title}"
    return f"다음 회차 CEO 판단 시 최근 주제 '{title}'와 동일한 감정 축 반복을 피하세요."


def record_publish_cycle_memory(event_type: str = "publish_cycle_completed") -> bool:
    try:
        event = build_publish_cycle_event(event_type=event_type)
        append_decision(event)
        print(f"[Decision Memory] recorded: {event_type} -> {MEMORY_FILE}")
        return True
    except Exception as exc:
        print(f"[Decision Memory] skipped: {exc}")
        return False


if __name__ == "__main__":
    record_publish_cycle_memory()
