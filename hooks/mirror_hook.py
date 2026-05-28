"""Non-blocking artifact mirror hooks.

Importing this module performs no file I/O. Hook functions must never raise
uncaught exceptions into the production pipeline.
"""

from typing import Optional

from artifact_mirror import MirrorResult, mirror_artifact, resolve_job_artifact_root
from hooks.audit_logger import log_hook_event


DEFAULT_AUDIENCE_INSIGHT_TARGET = None


def mirror_audience_insight(
    source_path: str = "audience_insight.json",
    target_path: Optional[str] = DEFAULT_AUDIENCE_INSIGHT_TARGET,
    audit_log_path: Optional[str] = None,
) -> Optional[MirrorResult]:
    """Best-effort mirror for the audience insight artifact.

    TODO: Accept job context directly from the scheduler/job manager when
    orchestration owns job identity.
    TODO: Replace text audit logging with structured monitor logging after
    logging ownership is approved.
    """
    try:
        if target_path is None or audit_log_path is None:
            job_root = resolve_job_artifact_root()
            target_path = target_path or f"{job_root.root}/audience_insight.json"
            audit_log_path = audit_log_path or f"{job_root.root}/reports/audit_log.txt"
        result = mirror_artifact(source_path, target_path, overwrite=True)
        log_hook_event("MIRROR", source_path, result, log_path=audit_log_path)
        return result
    except Exception as exc:
        log_hook_event(
            "MIRROR",
            source_path,
            False,
            details=f"exception={exc}",
            log_path=audit_log_path or "jobs/active/latest/reports/audit_log.txt",
        )
        return None
