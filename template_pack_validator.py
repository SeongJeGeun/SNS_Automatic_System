"""Validate CEO topic pool and content topic template pack compatibility.

Checks that every CEO topic_key has at least one matching content template
that can generate the requested script. Warning-only by default.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Set

CEO_TOPIC_POOL_FILE = os.getenv("CEO_TOPIC_POOL_FILE", os.path.join("templates", "ceo_topic_pool.json"))
CONTENT_TEMPLATE_PACK_FILE = os.getenv("CONTENT_TEMPLATE_PACK_FILE", os.path.join("templates", "content_topics.json"))
REPORT_FILE = os.path.join("agent_runs", "template_pack_validation_report.json")


def _load_json(path: str, default: Any):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        return {"_load_error": str(exc), "_path": path}


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _topic_keys_from_content_pack(pack: Dict[str, Any]) -> Set[str]:
    keys: Set[str] = set()
    for template in pack.get("templates", []) if isinstance(pack, dict) else []:
        if not isinstance(template, dict):
            continue
        for key in template.get("topic_keys", []) or []:
            keys.add(str(key))
    return keys


def _topic_keys_from_ceo_pool(pool: Dict[str, Any]) -> Set[str]:
    keys: Set[str] = set()
    for topic in pool.get("topics", []) if isinstance(pool, dict) else []:
        if isinstance(topic, dict) and topic.get("topic_key"):
            keys.add(str(topic["topic_key"]))
    return keys


def _content_template_ids_for_key(pack: Dict[str, Any], topic_key: str) -> List[str]:
    template_ids = []
    for template in pack.get("templates", []) if isinstance(pack, dict) else []:
        if not isinstance(template, dict):
            continue
        if topic_key in (template.get("topic_keys") or []):
            template_ids.append(str(template.get("template_id", "unknown")))
    return template_ids


def validate_template_packs(
    ceo_pool_file: str = CEO_TOPIC_POOL_FILE,
    content_pack_file: str = CONTENT_TEMPLATE_PACK_FILE,
    report_file: str = REPORT_FILE,
) -> Dict[str, Any]:
    ceo_pool = _load_json(ceo_pool_file, {})
    content_pack = _load_json(content_pack_file, {})

    warnings = []
    errors = []

    if not isinstance(ceo_pool, dict) or ceo_pool.get("_load_error"):
        errors.append(f"CEO topic pool load failed: {ceo_pool}")
        ceo_pool = {}
    if not isinstance(content_pack, dict) or content_pack.get("_load_error"):
        errors.append(f"Content template pack load failed: {content_pack}")
        content_pack = {}

    ceo_keys = _topic_keys_from_ceo_pool(ceo_pool)
    content_keys = _topic_keys_from_content_pack(content_pack)
    missing_in_content = sorted(ceo_keys - content_keys)
    orphan_content_keys = sorted(content_keys - ceo_keys)

    for key in missing_in_content:
        errors.append(f"CEO topic_key has no content template: {key}")
    for key in orphan_content_keys:
        warnings.append(f"Content topic_key is not used by CEO pool: {key}")

    mapping = {
        key: _content_template_ids_for_key(content_pack, key)
        for key in sorted(ceo_keys)
    }

    report = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ok": not errors,
        "warnings": warnings,
        "errors": errors,
        "ceo_topic_pool_file": ceo_pool_file,
        "content_template_pack_file": content_pack_file,
        "ceo_topic_keys": sorted(ceo_keys),
        "content_topic_keys": sorted(content_keys),
        "missing_in_content": missing_in_content,
        "orphan_content_keys": orphan_content_keys,
        "topic_to_template_ids": mapping,
    }
    _write_json(report_file, report)

    if report["ok"]:
        print("[Template Pack Validator] OK: CEO topic pool matches content templates")
        if warnings:
            print(f"[Template Pack Validator] warnings: {warnings}")
    else:
        print(f"[Template Pack Validator] WARNING: {errors}")
    return report


if __name__ == "__main__":
    validate_template_packs()
