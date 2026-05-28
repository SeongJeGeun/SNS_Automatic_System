"""Non-blocking validation report hooks.

Importing this module performs no file I/O. Hook functions must never raise
uncaught exceptions into the production pipeline.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from artifact_mirror import resolve_job_artifact_root
from artifact_validation_report import validate_artifact_report
from hooks.audit_logger import log_hook_event


DEFAULT_AUDIENCE_INSIGHT_ARTIFACT = None
DEFAULT_AUDIENCE_INSIGHT_REPORT = None


def write_audience_insight_validation_report(
    artifact_path: Optional[str] = DEFAULT_AUDIENCE_INSIGHT_ARTIFACT,
    report_path: Optional[str] = DEFAULT_AUDIENCE_INSIGHT_REPORT,
    audit_log_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Best-effort validation report for the mirrored audience insight artifact.

    TODO: Accept job context directly from the scheduler/job manager when
    orchestration owns job identity.
    TODO: Split audit reports by artifact once multiple mirrors are active.
    TODO: Replace text audit logging with structured monitor logging after
    logging ownership is approved.
    """
    try:
        if artifact_path is None or report_path is None or audit_log_path is None:
            job_root = resolve_job_artifact_root()
            artifact_path = artifact_path or f"{job_root.root}/audience_insight.json"
            report_path = report_path or f"{job_root.root}/reports/audit.json"
            audit_log_path = audit_log_path or f"{job_root.root}/reports/audit_log.txt"
        report = validate_artifact_report(
            artifact_path,
            artifact_type="audience_insight",
            platform="instagram",
        )
        if report.get("warnings") == ["artifact is missing"]:
            report["warnings"] = ["artifact missing"]

        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        log_hook_event("VALIDATION", artifact_path, report, log_path=audit_log_path)
        return report
    except Exception as exc:
        log_hook_event(
            "VALIDATION",
            artifact_path or "unknown",
            False,
            details=f"exception={exc}",
            log_path=audit_log_path or "jobs/active/latest/reports/audit_log.txt",
        )
        return None
