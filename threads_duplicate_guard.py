"""Lightweight duplicate guard for Threads text publishing.

This helper stores a hash of the last successful Threads text post and lets the
publisher skip identical text during the guard window. It has no network calls
and no import-time side effects.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Dict, Tuple

GUARD_FILE = os.path.join("agent_runs", "threads_publish_guard.json")
DEFAULT_WINDOW_SECONDS = 10800


def _normalize_text(text: str) -> str:
    return "\n".join(line.strip() for line in str(text or "").splitlines() if line.strip())


def text_hash(text: str) -> str:
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()


def _load_json(path: str, default=None):
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: str, payload: Dict):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def guard_window_seconds() -> int:
    raw = os.getenv("THREADS_DUPLICATE_GUARD_SECONDS") or os.getenv("PIPELINE_INTERVAL_SECONDS")
    try:
        return int(raw or DEFAULT_WINDOW_SECONDS)
    except Exception:
        return DEFAULT_WINDOW_SECONDS


def enabled() -> bool:
    return os.getenv("ENABLE_THREADS_DUPLICATE_GUARD", "true").strip().lower() in {"1", "true", "yes", "y", "on"}


def check_duplicate(text: str) -> Tuple[bool, Dict]:
    if not enabled():
        return False, {}
    current_hash = text_hash(text)
    guard = _load_json(GUARD_FILE, {})
    if guard.get("text_hash") != current_hash:
        return False, {"text_hash": current_hash}

    elapsed = int(time.time() - float(guard.get("created_ts", 0) or 0))
    window = guard_window_seconds()
    if elapsed < window:
        return True, {
            **guard,
            "text_hash": current_hash,
            "elapsed_seconds": elapsed,
            "remaining_seconds": window - elapsed,
        }
    return False, {"text_hash": current_hash}


def record_success(text: str, post_id: str):
    _write_json(GUARD_FILE, {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "created_ts": time.time(),
        "text_hash": text_hash(text),
        "post_id": post_id,
        "guard_seconds": guard_window_seconds(),
    })


def write_skip_report(report_file: str, text: str, guard: Dict):
    os.makedirs(os.path.dirname(report_file) or ".", exist_ok=True)
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "text",
            "ok": False,
            "skipped": True,
            "reason": "duplicate_guard",
            "post_id": None,
            "text_hash": text_hash(text),
            "previous_post_id": guard.get("post_id"),
            "remaining_seconds": guard.get("remaining_seconds"),
        }, f, ensure_ascii=False, indent=2)
        f.write("\n")
