"""Non-destructive artifact mirror utility for future job-scoped migration.

This module is intentionally not connected to the production pipeline. Importing
it performs no file reads, file writes, API calls, publishing, or scheduling.
"""

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from shutil import copy2
from typing import Optional


_AUTO_JOB_ID: Optional[str] = None


@dataclass(frozen=True)
class MirrorResult:
    """Result of a best-effort artifact mirror operation."""

    ok: bool
    source: str
    target: str
    action: str
    error: Optional[str] = None


@dataclass(frozen=True)
class JobArtifactRoot:
    """Resolved artifact root for one runtime call."""

    root: str
    job_id: str
    warning: Optional[str] = None
    compatibility_mode: bool = False


def _truthy(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _safe_job_id(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "-"
        for char in value.strip()
    ).strip(".-/")
    return cleaned or "job-unknown"


def _auto_job_id() -> str:
    global _AUTO_JOB_ID
    if _AUTO_JOB_ID is None:
        _AUTO_JOB_ID = datetime.now().strftime("job-%Y%m%d-%H%M%S")
    return _AUTO_JOB_ID


def resolve_job_artifact_root() -> JobArtifactRoot:
    """Resolve the job artifact root without side effects.

    TODO: Replace env-based resolution with scheduler/job manager context after
    orchestration owns job identity.
    """
    if _truthy(os.getenv("USE_ACTIVE_LATEST")):
        return JobArtifactRoot(
            root="jobs/active/latest",
            job_id="active/latest",
            warning="USE_ACTIVE_LATEST=true; using compatibility artifact path",
            compatibility_mode=True,
        )

    raw_job_id = os.getenv("JOB_ID")
    if raw_job_id:
        job_id = _safe_job_id(raw_job_id)
        warning = None
        if job_id != raw_job_id.strip():
            warning = f"JOB_ID sanitized from {raw_job_id!r} to {job_id!r}"
        return JobArtifactRoot(root=f"jobs/{job_id}", job_id=job_id, warning=warning)

    job_id = _auto_job_id()
    return JobArtifactRoot(
        root=f"jobs/{job_id}",
        job_id=job_id,
        warning="JOB_ID not set; auto-generated job id",
    )


def mirror_artifact(
    source_path: str,
    target_path: str,
    *,
    overwrite: bool = False,
) -> MirrorResult:
    """Copy one current artifact to a future job-scoped path.

    Missing sources and existing targets are reported as non-raising results so
    callers can keep current runtime behavior unchanged.

    TODO: Add job-id/path helpers after the job context contract is approved.
    TODO: Add structured logging once this is wired into a non-blocking hook.
    """
    source = Path(source_path)
    target = Path(target_path)

    if not source.exists():
        return MirrorResult(
            ok=False,
            source=str(source),
            target=str(target),
            action="missing_source",
            error="source artifact does not exist",
        )

    if not source.is_file():
        return MirrorResult(
            ok=False,
            source=str(source),
            target=str(target),
            action="invalid_source",
            error="source artifact is not a file",
        )

    if target.exists() and not overwrite:
        return MirrorResult(
            ok=True,
            source=str(source),
            target=str(target),
            action="skipped_existing_target",
        )

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        copy2(source, target)
    except Exception as exc:
        return MirrorResult(
            ok=False,
            source=str(source),
            target=str(target),
            action="copy_failed",
            error=str(exc),
        )

    return MirrorResult(
        ok=True,
        source=str(source),
        target=str(target),
        action="copied",
    )
