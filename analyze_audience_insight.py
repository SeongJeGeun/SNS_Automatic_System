"""Deterministic audience insight analysis report writer.

Importing this module performs no file I/O. Analysis runs only when called by
the audience research flow or CLI entry point.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


ESSENTIAL_FIELDS = [
    "audience_state",
    "core_pains",
    "emotional_keywords",
    "story_angle",
    "content_principles",
]


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _has_value(value: Any) -> bool:
    if isinstance(value, list):
        return any(str(item or "").strip() for item in value)
    return bool(str(value or "").strip())


def _field_completeness(insight: Dict[str, Any]) -> Dict[str, Any]:
    present = [field for field in ESSENTIAL_FIELDS if _has_value(insight.get(field))]
    missing = [field for field in ESSENTIAL_FIELDS if field not in present]
    return {
        "ok": not missing,
        "present": present,
        "missing": missing,
        "ratio": round(len(present) / len(ESSENTIAL_FIELDS), 2),
    }


def _terms_from_value(value: Any) -> Set[str]:
    if isinstance(value, list):
        source = " ".join(str(item or "") for item in value)
    else:
        source = str(value or "")
    terms = {
        token.strip(".,:;!?()[]{}\"'").lower()
        for token in source.replace("-", " ").split()
    }
    return {term for term in terms if len(term) >= 4}


def _theme_terms(insight: Dict[str, Any]) -> Set[str]:
    terms: Set[str] = set()
    for field in [
        "audience_state",
        "core_pains",
        "emotional_keywords",
        "story_angle",
        "content_principles",
        "trending_topics",
        "hot_pain_keywords",
    ]:
        terms.update(_terms_from_value(insight.get(field)))
    return terms


def _content_clarity(insight: Dict[str, Any], quality_report: Dict[str, Any]) -> str:
    completeness = _field_completeness(insight)
    quality_ok = quality_report.get("quality_ok")
    warnings = quality_report.get("warnings") or []
    terms = _theme_terms(insight)

    if completeness["ok"] and quality_ok is True and not warnings and len(terms) >= 8:
        return "clear"
    if completeness["ratio"] >= 0.8 and len(terms) >= 5:
        return "usable_with_review"
    return "needs_review"


def _find_previous_job_root(current_job_root: Path, jobs_root: Path = Path("jobs")) -> Optional[Path]:
    if not jobs_root.exists():
        return None

    candidates: List[Path] = []
    current_resolved = current_job_root.resolve()
    for path in jobs_root.iterdir():
        if not path.is_dir() or path.name == "active":
            continue
        try:
            if path.resolve() == current_resolved:
                continue
        except Exception:
            continue
        if (path / "audience_insight.json").exists() or (
            path / "reports" / "quality_report.json"
        ).exists():
            candidates.append(path)

    if not candidates:
        return None

    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates[0]


def build_analysis_report(job_root: str, previous_job_root: Optional[str] = None) -> Dict[str, Any]:
    """Build deterministic analysis metadata for one audience insight job.

    TODO: Add trend drift analysis after scheduler-owned job history exists.
    TODO: Add dashboard-facing rollups once monitoring ownership is defined.
    """
    current_root = Path(job_root)
    current_insight = _load_json(current_root / "audience_insight.json")
    current_quality = _load_json(current_root / "reports" / "quality_report.json")

    previous_root = Path(previous_job_root) if previous_job_root else _find_previous_job_root(current_root)
    previous_insight = _load_json(previous_root / "audience_insight.json") if previous_root else {}
    previous_quality = (
        _load_json(previous_root / "reports" / "quality_report.json")
        if previous_root
        else {}
    )

    current_terms = _theme_terms(current_insight)
    previous_terms = _theme_terms(previous_insight)
    overlap = sorted(current_terms & previous_terms)
    previous_available = bool(previous_insight or previous_quality)

    completeness = _field_completeness(current_insight)
    previous_quality_ok = previous_quality.get("quality_ok")
    current_quality_ok = current_quality.get("quality_ok")

    if not previous_available:
        improvement = "no_previous_job"
    elif current_quality_ok is True and previous_quality_ok is not True:
        improvement = "improved"
    elif current_quality_ok == previous_quality_ok and completeness["ok"]:
        improvement = "stable"
    else:
        improvement = "needs_review"

    notes = []
    if not current_insight:
        notes.append("current audience insight missing")
    if not current_quality:
        notes.append("current quality report missing")
    if not previous_available:
        notes.append("previous job unavailable")

    return {
        "job_root": str(current_root),
        "previous_job_root": str(previous_root) if previous_root else None,
        "content_clarity": _content_clarity(current_insight, current_quality),
        "field_completeness": completeness,
        "theme_consistency": {
            "previous_available": previous_available,
            "overlap_terms": overlap[:12],
            "overlap_count": len(overlap),
        },
        "improvement_vs_previous": improvement,
        "notes": notes,
    }


def write_analysis_report(
    job_root: str,
    report_path: Optional[str] = None,
    previous_job_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Write `analysis_report.json` for the current job without raising."""
    try:
        report = build_analysis_report(job_root, previous_job_root=previous_job_root)
        target = Path(report_path) if report_path else Path(job_root) / "reports" / "analysis_report.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return report
    except Exception as exc:
        return {
            "job_root": job_root,
            "previous_job_root": previous_job_root,
            "content_clarity": "needs_review",
            "field_completeness": {"ok": False, "present": [], "missing": ESSENTIAL_FIELDS, "ratio": 0.0},
            "theme_consistency": {"previous_available": False, "overlap_terms": [], "overlap_count": 0},
            "improvement_vs_previous": "analysis_failed",
            "notes": [f"analysis failed: {exc}"],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Write audience insight analysis report.")
    parser.add_argument("--job-root", required=True)
    parser.add_argument("--report-path", default=None)
    parser.add_argument("--previous-job-root", default=None)
    args = parser.parse_args()

    report = write_analysis_report(
        args.job_root,
        report_path=args.report_path,
        previous_job_root=args.previous_job_root,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
