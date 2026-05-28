"""Build advisory strategy signals from audience analysis summaries.

Importing this module performs no file I/O. Signals are deterministic and
non-blocking.
"""

from typing import Any, Dict, Optional


def build_strategy_signals(analysis_summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return lightweight downstream strategy signals.

    TODO: Feed these signals into adaptive strategy prompting once downstream
    ownership and prompt rules are approved.
    """
    summary = analysis_summary or {}
    available = bool(summary.get("available"))
    clarity = str(summary.get("content_clarity") or "unknown")
    improvement = str(summary.get("improvement_vs_previous") or "unknown")
    theme_consistency = summary.get("theme_consistency") or {}
    overlap_count = int(theme_consistency.get("overlap_count") or 0)
    previous_available = bool(theme_consistency.get("previous_available"))

    if clarity == "clear":
        clarity_flag = "clear"
    elif clarity == "usable_with_review":
        clarity_flag = "usable_with_review"
    else:
        clarity_flag = "needs_review"

    if not previous_available:
        consistency_flag = "no_previous"
    elif overlap_count >= 8:
        consistency_flag = "consistent"
    elif overlap_count >= 3:
        consistency_flag = "partial"
    else:
        consistency_flag = "low"

    if improvement in {"improved", "stable", "needs_review"}:
        improvement_flag = improvement
    else:
        improvement_flag = "unknown"

    if not available or clarity_flag == "needs_review":
        strategy_mode = "conservative"
    elif consistency_flag == "consistent" and improvement_flag == "stable":
        strategy_mode = "reinforce_theme"
    else:
        strategy_mode = "normal"

    return {
        "available": available,
        "strategy_mode": strategy_mode,
        "clarity_flag": clarity_flag,
        "consistency_flag": consistency_flag,
        "improvement_flag": improvement_flag,
        "source": "analysis_summary",
    }
