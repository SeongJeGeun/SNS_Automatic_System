"""Lightweight job-scoped status artifact writer.

Batch 33 — Status Heartbeat / Dashboard Visibility
Batch 34 — Atomic status updates + current_job_id global linkage
--------------------------------------------------------------------
Writes ``jobs/{JOB_ID}/reports/agent_status.json`` (job-scoped) after key
generation stages so that 24/7 local operation can monitor:

  - which local model was used
  - generation success/failure
  - audience quality gate result
  - analysis availability
  - strategy mode active this run
  - whether Obsidian context enrichment was applied
  - how long generation took

Batch 34 additions
------------------
1. **Atomic writes** — ``update_job_status()`` now uses a temp-file +
   ``os.replace()`` swap so a crash mid-write never leaves a corrupt
   ``agent_status.json``.  ``write_job_status()`` uses the same path.
2. **Global linkage** — ``update_global_current_job_id()`` writes
   ``current_job_id`` into ``agent_runs/agent_status.json`` (the global
   pipeline-state file owned by ``agent_monitor.py``) using the same atomic
   pattern.  Only the ``current_job_id`` key is patched; no other keys are
   touched.  If the global file does not exist yet the patch is silently
   skipped.

All writes are **best-effort and non-blocking**:
- Any exception is caught, logged to stdout, and execution continues.
- Missing data fields are filled with graceful defaults (``null`` / ``False``).
- No import-time side effects: importing this module performs no I/O.

Integration points
------------------
Called from:
  - ``audience_research.py`` → ``_write_job_status()`` after insight + signals
    are fully assembled; also calls ``update_global_current_job_id()``
  - ``self_healing_generator.py`` → ``update_job_status()`` after Obsidian
    context flag is resolved, and again at the very end of ``main()`` to
    set ``story_agent_stage="completed"`` (or ``"failed"``)

**Does NOT touch** ``agent_runs/agent_status.json`` outside of the narrow
``current_job_id`` linkage written by ``update_global_current_job_id()``.

TODO (Batch 35+): Stream status deltas to a dashboard WebSocket endpoint
    instead of (or in addition to) writing the file, once a dashboard server
    owns the status subscription contract.
TODO (Batch 35+): Include per-stage timing breakdown once stage boundaries
    are tracked via a job-context object rather than individual timers.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write_atomic(path: str, payload: Dict[str, Any]) -> None:
    """Serialise *payload* to *path* via an atomic temp-file swap.

    Writes to a sibling temp file in the same directory, then calls
    ``os.replace()`` which is atomic on POSIX (and best-effort on Windows).
    This guarantees readers never see a partially-written file.

    Raises any OS / serialisation exception to the caller.
    """
    dir_name = os.path.dirname(path) or "."
    # NamedTemporaryFile with delete=False in the same directory ensures
    # os.replace() works as a same-filesystem rename.
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        # Clean up the temp file if anything went wrong.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def write_job_status(
    *,
    job_id: str,
    job_root: str,
    model: Optional[str] = None,
    generation_status: Optional[str] = None,
    quality_ok: Optional[bool] = None,
    quality_warnings: Optional[list] = None,
    analysis_available: Optional[bool] = None,
    strategy_mode: Optional[str] = None,
    obsidian_context_enabled: Optional[bool] = None,
    generation_time_seconds: Optional[float] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> bool:
    """Write a lightweight job-scoped status artifact (atomic).

    All parameters are keyword-only.  Any parameter that is ``None`` will be
    written as ``null`` in the JSON output rather than omitting the field,
    so downstream readers can distinguish "not yet written" from "known null".

    Parameters
    ----------
    job_id:
        Current job identifier string.
    job_root:
        Root directory for job-scoped artifacts (e.g. ``"jobs/job-20260528"``).
    model:
        Local model name used for generation (e.g. ``"gemma4:26b"``).
    generation_status:
        Stage status string (e.g. ``"local_obsidian_ollama_json_parsed"``
        or ``"antigravity_search_fallback"`` or ``"failed"``).
    quality_ok:
        Whether the audience insight quality gate passed.
    quality_warnings:
        List of non-blocking quality gate warning strings.
    analysis_available:
        Whether ``analysis_summary`` was successfully read.
    strategy_mode:
        Active strategy mode (``"conservative"``, ``"reinforce_theme"``,
        ``"normal"``).
    obsidian_context_enabled:
        Whether Obsidian context enrichment was applied to the generator prompt.
    generation_time_seconds:
        Wall-clock seconds spent generating the audience insight.
    extra:
        Optional dict of additional advisory fields (merged shallowly into the
        status payload).

    Returns
    -------
    bool
        ``True`` if the file was written successfully; ``False`` on any error.
    """
    try:
        report_dir = os.path.join(job_root, "reports")
        os.makedirs(report_dir, exist_ok=True)
        status_path = os.path.join(report_dir, "agent_status.json")

        payload: Dict[str, Any] = {
            "job_id": job_id,
            "model": model,
            "generation_status": generation_status,
            "quality_ok": quality_ok,
            "quality_warnings": quality_warnings or [],
            "analysis_available": analysis_available,
            "strategy_mode": strategy_mode,
            "obsidian_context_enabled": obsidian_context_enabled,
            "generation_time_seconds": (
                round(float(generation_time_seconds), 2)
                if generation_time_seconds is not None
                else None
            ),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        if extra:
            # Merge extra advisory fields — existing keys are NOT overwritten.
            for key, value in extra.items():
                payload.setdefault(key, value)

        _write_atomic(status_path, payload)

        print(
            f"[StatusWriter] job status 기록 완료: {status_path} "
            f"(strategy_mode={strategy_mode}, "
            f"obsidian={obsidian_context_enabled}, "
            f"quality_ok={quality_ok})"
        )
        return True

    except Exception as exc:
        print(f"[Warning] job status 기록 실패 (non-blocking): {exc}")
        return False


def update_job_status(
    job_root: str,
    updates: Dict[str, Any],
) -> bool:
    """Merge *updates* into an existing job status file (atomic).

    Reads the current file (if present), shallow-merges *updates*, and
    re-writes the file via an atomic temp-file swap so readers never see a
    partially-written result.  The ``updated_at`` field is always refreshed.

    If the file does not yet exist, writes a minimal status containing only
    the given *updates* plus ``updated_at``.

    Non-blocking: all exceptions are caught and logged.

    TODO (Batch 35+): Replace with a proper patch-append journal once
        multi-stage concurrent writes are required (WebSocket streaming path).
    """
    try:
        report_dir = os.path.join(job_root, "reports")
        os.makedirs(report_dir, exist_ok=True)
        status_path = os.path.join(report_dir, "agent_status.json")

        payload: Dict[str, Any] = {}
        if os.path.exists(status_path):
            try:
                with open(status_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception:
                payload = {}

        payload.update(updates)
        payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        _write_atomic(status_path, payload)

        print(
            f"[StatusWriter] job status 업데이트 완료: {status_path} "
            f"(fields={list(updates.keys())})"
        )
        return True

    except Exception as exc:
        print(f"[Warning] job status 업데이트 실패 (non-blocking): {exc}")
        return False


def update_global_current_job_id(
    job_id: str,
    global_status_path: str = "agent_runs/agent_status.json",
) -> bool:
    """Patch ``current_job_id`` into the global agent status file (atomic).

    This provides a lightweight linkage so the global pipeline view
    (``agent_runs/agent_status.json``, owned by ``agent_monitor.py``) always
    reflects which job is currently running, without requiring a full merge of
    job-scoped fields into the global file.

    Behaviour
    ---------
    - If the global file **does not exist**, the patch is silently skipped
      (returns ``True``).  We never create ``agent_runs/agent_status.json``
      from scratch — that file is owned by ``agent_monitor.py``.
    - If the global file **exists**, only the ``current_job_id`` and
      ``current_job_updated_at`` keys are updated; all other keys are
      preserved verbatim.
    - The write uses the same atomic temp-file swap as all other writes.

    Non-blocking: all exceptions are caught and logged.

    TODO (Batch 35+): Also write ``current_job_stage`` once the global
        dashboard needs per-stage visibility without reading job-scoped files.
    """
    try:
        if not os.path.exists(global_status_path):
            # Global file not yet created — skip silently.
            print(
                f"[StatusWriter] global status 없음, current_job_id 패치 스킵: "
                f"{global_status_path}"
            )
            return True

        try:
            with open(global_status_path, "r", encoding="utf-8") as f:
                global_payload: Dict[str, Any] = json.load(f)
        except Exception:
            global_payload = {}

        global_payload["current_job_id"] = job_id
        global_payload["current_job_updated_at"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        _write_atomic(global_status_path, global_payload)

        print(
            f"[StatusWriter] global status current_job_id 패치 완료: "
            f"{global_status_path} (job_id={job_id})"
        )
        return True

    except Exception as exc:
        print(f"[Warning] global current_job_id 패치 실패 (non-blocking): {exc}")
        return False


def read_job_status(job_root: str) -> Dict[str, Any]:
    """Read the current job status file and return its contents.

    Returns an empty dict if the file does not exist or cannot be parsed.
    Non-blocking: all exceptions return an empty dict.
    """
    try:
        status_path = os.path.join(job_root, "reports", "agent_status.json")
        with open(status_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
