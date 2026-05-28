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
1. ``update_job_status()`` is safer than a naive read-modify-write. It uses a
   non-blocking sidecar lock when immediately available, then writes via a
   sibling temp file + ``os.replace()``. If the sidecar lock is already held, it
   falls back to a lightweight optimistic compare/retry patch path.
2. ``write_job_status()`` links the global status view to the active job by
   patching ``agent_runs/agent_status.json`` with ``current_job_id`` when that
   global file already exists. The global file is never created here.
3. All status writes are best-effort and non-blocking: exceptions are logged and
   runtime/publish flow continues.

No import-time side effects: importing this module performs no I/O.

TODO (Batch 35+): Stream status deltas to a dashboard WebSocket endpoint once a
single dashboard component owns the subscription contract.
TODO (Batch 35+): Replace the file patch helper with an append-only event journal
if truly concurrent multi-writer status streams become a hard requirement.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, Optional


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _status_path(job_root: str) -> str:
    return os.path.join(job_root, "reports", "agent_status.json")


def _read_json_file(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _read_raw_file(path: str) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return b""
    except Exception:
        return b""


def _merge_status(payload: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(payload or {})
    merged.update(updates or {})
    merged["updated_at"] = _now()
    return merged


def _write_atomic(path: str, payload: Dict[str, Any]) -> None:
    """Serialise *payload* to *path* via a temp-file swap."""
    dir_name = os.path.dirname(path) or "."
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _try_acquire_lock(lock_path: str) -> Optional[int]:
    try:
        return os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None
    except Exception:
        return None


def _release_lock(lock_path: str, fd: Optional[int]) -> None:
    try:
        if fd is not None:
            os.close(fd)
    except Exception:
        pass
    try:
        os.unlink(lock_path)
    except Exception:
        pass


def _optimistic_patch(path: str, updates: Dict[str, Any], create_if_missing: bool, retries: int = 3) -> bool:
    """Best-effort compare/retry patch path used when the sidecar lock is busy."""
    for _ in range(max(1, retries)):
        if not os.path.exists(path) and not create_if_missing:
            return True

        before = _read_raw_file(path)
        payload = {}
        if before:
            try:
                payload = json.loads(before.decode("utf-8"))
                if not isinstance(payload, dict):
                    payload = {}
            except Exception:
                payload = {}

        patched = _merge_status(payload, updates)

        # If another stage patched the file between our read and this check,
        # retry with the fresh contents instead of writing over stale state.
        if _read_raw_file(path) != before:
            continue

        _write_atomic(path, patched)
        return True
    return False


def _patch_json_file(path: str, updates: Dict[str, Any], create_if_missing: bool = True) -> bool:
    if not os.path.exists(path) and not create_if_missing:
        return True

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    lock_path = f"{path}.lock"
    lock_fd = _try_acquire_lock(lock_path)

    if lock_fd is not None:
        try:
            payload = _read_json_file(path)
            _write_atomic(path, _merge_status(payload, updates))
            return True
        finally:
            _release_lock(lock_path, lock_fd)

    return _optimistic_patch(path, updates, create_if_missing=create_if_missing)


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
    """Write the initial job-scoped status artifact.

    This function also performs the Batch 34 global backlink patch by calling
    ``update_global_current_job_id()``. That helper only patches an existing
    global file and never creates one, so ownership stays with ``agent_monitor``.
    """
    try:
        status_path = _status_path(job_root)
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
            "updated_at": _now(),
        }

        if extra:
            for key, value in extra.items():
                payload.setdefault(key, value)

        _write_atomic(status_path, payload)
        update_global_current_job_id(job_id)

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


def update_job_status(job_root: str, updates: Dict[str, Any]) -> bool:
    """Patch an existing job status file without naive read-modify-write.

    The patch path is lightweight and non-blocking. It first tries an immediate
    sidecar lock and, if unavailable, falls back to a short optimistic retry.
    """
    try:
        status_path = _status_path(job_root)
        ok = _patch_json_file(status_path, updates, create_if_missing=True)
        if ok:
            print(
                f"[StatusWriter] job status 업데이트 완료: {status_path} "
                f"(fields={list(updates.keys())})"
            )
            return True
        print(f"[Warning] job status 업데이트 충돌로 스킵 (non-blocking): {status_path}")
        return False
    except Exception as exc:
        print(f"[Warning] job status 업데이트 실패 (non-blocking): {exc}")
        return False


def update_global_current_job_id(
    job_id: str,
    global_status_path: str = "agent_runs/agent_status.json",
) -> bool:
    """Patch ``current_job_id`` into an existing global agent status file.

    If the global file does not exist, the patch is skipped. This module never
    creates ``agent_runs/agent_status.json`` because that file is owned by the
    global monitor layer.
    """
    try:
        if not os.path.exists(global_status_path):
            print(
                f"[StatusWriter] global status 없음, current_job_id 패치 스킵: "
                f"{global_status_path}"
            )
            return True

        ok = _patch_json_file(
            global_status_path,
            {
                "current_job_id": job_id,
                "current_job_updated_at": _now(),
            },
            create_if_missing=False,
        )
        if ok:
            print(
                f"[StatusWriter] global status current_job_id 패치 완료: "
                f"{global_status_path} (job_id={job_id})"
            )
            return True
        print(f"[Warning] global current_job_id 패치 충돌로 스킵 (non-blocking): {global_status_path}")
        return False
    except Exception as exc:
        print(f"[Warning] global current_job_id 패치 실패 (non-blocking): {exc}")
        return False


def read_job_status(job_root: str) -> Dict[str, Any]:
    """Read the current job status file and return its contents."""
    try:
        with open(_status_path(job_root), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
