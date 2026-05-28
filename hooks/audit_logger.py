"""Non-blocking audit logging for scaffold hooks.

Importing this module performs no file I/O. Logging failures are intentionally
swallowed so hook logging cannot affect pipeline behavior.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional


DEFAULT_AUDIT_LOG_PATH = None


def _result_ok(result: Any) -> bool:
    if isinstance(result, bool):
        return result
    if isinstance(result, dict):
        return bool(result.get("passed", result.get("ok", False)))
    return bool(getattr(result, "ok", False))


def _short_details(result: Any, details: Optional[str]) -> str:
    parts = []
    if details:
        parts.append(str(details))

    action = getattr(result, "action", None)
    if action:
        parts.append(f"action={action}")

    error = getattr(result, "error", None)
    if error:
        parts.append(f"error={error}")

    if isinstance(result, dict):
        warnings = result.get("warnings") or []
        if warnings:
            parts.append("warnings=" + ",".join(str(item) for item in warnings[:3]))

    text = " ".join(parts).strip()
    return text[:240]


def log_hook_event(
    event_type: str,
    artifact_path: str,
    result: Any,
    details: Optional[str] = None,
    log_path: Optional[str] = DEFAULT_AUDIT_LOG_PATH,
) -> None:
    """Append one simple hook audit line.

    TODO: Replace this text file with the approved monitoring/logging framework.
    TODO: Surface hook audit events in the dashboard after ownership is defined.
    """
    try:
        if log_path is None:
            from artifact_mirror import resolve_job_artifact_root
            job_root = resolve_job_artifact_root()
            log_path = f"{job_root.root}/reports/audit_log.txt"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ok = _result_ok(result)
        line = (
            f"{timestamp}\t{event_type}\t{artifact_path}\t"
            f"ok={str(ok).lower()}\t{_short_details(result, details)}\n"
        )
        target = Path(log_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.open("a", encoding="utf-8").write(line)
    except Exception:
        return
