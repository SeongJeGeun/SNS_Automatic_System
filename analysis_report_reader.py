"""Read audience analysis summaries for downstream stages.

Importing this module performs no file I/O. Reads happen only when
`read_analysis_summary()` is called.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional


def _default_summary(job_id: Optional[str], reason: str) -> Dict[str, Any]:
    return {
        "available": False,
        "job_id": job_id,
        "content_clarity": "unknown",
        "improvement_vs_previous": "unknown",
        "theme_consistency": {
            "overlap_count": 0,
            "previous_available": False,
        },
        "warnings": [reason],
    }


def read_analysis_summary(job_id: Optional[str], jobs_root: str = "jobs") -> Dict[str, Any]:
    """Return key analysis metrics for downstream strategy/script stages.

    TODO: Use scheduler-owned job context instead of passing `job_id` manually.
    TODO: Add adaptive strategy recommendations after downstream ownership is
    defined.
    """
    if not job_id:
        return _default_summary(job_id, "job_id is required")

    report_path = Path(jobs_root) / job_id / "reports" / "analysis_report.json"
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return _default_summary(job_id, "analysis report unavailable")

    theme_consistency = report.get("theme_consistency") or {}
    return {
        "available": True,
        "job_id": job_id,
        "content_clarity": report.get("content_clarity", "unknown"),
        "improvement_vs_previous": report.get("improvement_vs_previous", "unknown"),
        "theme_consistency": {
            "overlap_count": int(theme_consistency.get("overlap_count") or 0),
            "previous_available": bool(theme_consistency.get("previous_available")),
        },
        "warnings": report.get("notes") or [],
    }
