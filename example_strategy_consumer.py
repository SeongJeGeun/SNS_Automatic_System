"""Example strategy consumer: reads strategy_signals and adapts strategy config.

This module demonstrates how downstream strategy or script modules can
optionally consume ``strategy_signals`` from the audience insight artifact
and return an adapted strategy configuration without blocking or modifying
the publish flow.

Usage (non-blocking, read-only):
    from example_strategy_consumer import adapt_strategy_from_signals

    adapted = adapt_strategy_from_signals(insight.get("strategy_signals"))
    # Use `adapted` as a hint when building prompts or templates.
    # Never pass `adapted` to upload_carousel, scheduler, or Telegram modules.

TODO (Batch 31+): Wire this into the real strategy/script generation stage
    once prompt-rule ownership is approved and downstream producers accept
    the strategy config interface.
"""

from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Default conservative strategy returned whenever signals are unavailable.
# ---------------------------------------------------------------------------
_DEFAULT_CONSERVATIVE_STRATEGY: Dict[str, Any] = {
    "strategy_mode": "conservative",
    "output_length": "short",
    "template": "safe_template",
    "prompt_specificity": "high",
    "theme_repetition": False,
    "obsidian_context": False,
    "source": "default_fallback",
    "rationale": (
        "signals unavailable → conservative defaults applied; "
        "no publishing or blocking behavior changed"
    ),
}


def adapt_strategy_from_signals(
    strategy_signals: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return an adapted strategy config based on advisory ``strategy_signals``.

    Rules
    -----
    - ``strategy_mode == "conservative"``  → shorter output, safer template.
    - ``strategy_mode == "reinforce_theme"`` → repeat previous theme, add
      Obsidian context.
    - ``clarity_flag == "needs_review"`` → increase prompt specificity.
    - All other combinations → balanced defaults.
    - Signals unavailable or malformed → conservative defaults (same as above).

    This function is **non-blocking**. It never writes files, never modifies
    publish behavior, and never raises an unhandled exception.

    Parameters
    ----------
    strategy_signals:
        The ``strategy_signals`` dict attached to the audience insight, or
        ``None`` / empty dict when unavailable.

    Returns
    -------
    dict
        Adapted strategy configuration for optional downstream use.
    """
    # ------------------------------------------------------------------
    # Guard: missing or empty signals → conservative defaults
    # ------------------------------------------------------------------
    if not strategy_signals or not strategy_signals.get("available"):
        return dict(_DEFAULT_CONSERVATIVE_STRATEGY)

    try:
        return _build_adapted_config(strategy_signals)
    except Exception as exc:
        # Non-blocking: swallow any unexpected error and fall back safely.
        return {
            **_DEFAULT_CONSERVATIVE_STRATEGY,
            "source": "error_fallback",
            "rationale": (
                f"unexpected error during signal adaptation ({exc}); "
                "conservative defaults applied"
            ),
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_adapted_config(signals: Dict[str, Any]) -> Dict[str, Any]:
    """Build an adapted config dict from validated signals.

    Separated from the public function so that exceptions are caught cleanly
    by the caller.
    """
    strategy_mode: str = str(signals.get("strategy_mode") or "conservative")
    clarity_flag: str = str(signals.get("clarity_flag") or "needs_review")
    consistency_flag: str = str(signals.get("consistency_flag") or "unknown")
    improvement_flag: str = str(signals.get("improvement_flag") or "unknown")

    # ------------------------------------------------------------------ #
    # Adaptation rule 1: conservative mode                                #
    # ------------------------------------------------------------------ #
    if strategy_mode == "conservative":
        config = {
            "strategy_mode": "conservative",
            "output_length": "short",
            "template": "safe_template",
            "prompt_specificity": "high" if clarity_flag == "needs_review" else "normal",
            "theme_repetition": False,
            "obsidian_context": False,
            "source": "strategy_signals",
            "rationale": (
                "strategy_mode=conservative → short output, safe template applied"
            ),
        }
        # Append clarity note when review is needed.
        if clarity_flag == "needs_review":
            config["rationale"] += (
                "; clarity_flag=needs_review → prompt specificity set to high"
            )
        return config

    # ------------------------------------------------------------------ #
    # Adaptation rule 2: reinforce_theme mode                             #
    # ------------------------------------------------------------------ #
    if strategy_mode == "reinforce_theme":
        config = {
            "strategy_mode": "reinforce_theme",
            "output_length": "normal",
            "template": "theme_reinforcement_template",
            "prompt_specificity": "high" if clarity_flag == "needs_review" else "normal",
            "theme_repetition": True,
            "obsidian_context": True,
            "source": "strategy_signals",
            "rationale": (
                "strategy_mode=reinforce_theme → previous theme repeated, "
                "Obsidian context included"
            ),
        }
        if clarity_flag == "needs_review":
            config["rationale"] += (
                "; clarity_flag=needs_review → prompt specificity set to high"
            )
        return config

    # ------------------------------------------------------------------ #
    # Adaptation rule 3: clarity needs review (any other mode)            #
    # ------------------------------------------------------------------ #
    if clarity_flag == "needs_review":
        return {
            "strategy_mode": strategy_mode,
            "output_length": "normal",
            "template": "default_template",
            "prompt_specificity": "high",
            "theme_repetition": False,
            "obsidian_context": False,
            "source": "strategy_signals",
            "rationale": (
                f"clarity_flag=needs_review with strategy_mode={strategy_mode} "
                "→ prompt specificity elevated to high"
            ),
        }

    # ------------------------------------------------------------------ #
    # Balanced defaults for all other signal combinations                 #
    # ------------------------------------------------------------------ #
    return {
        "strategy_mode": strategy_mode,
        "output_length": "normal",
        "template": "default_template",
        "prompt_specificity": "normal",
        "theme_repetition": False,
        "obsidian_context": False,
        "source": "strategy_signals",
        "rationale": (
            f"strategy_mode={strategy_mode}, clarity_flag={clarity_flag}, "
            f"consistency_flag={consistency_flag}, "
            f"improvement_flag={improvement_flag} → balanced defaults"
        ),
    }


# ---------------------------------------------------------------------------
# Standalone validation helper (used by test / batch validation scripts only)
# ---------------------------------------------------------------------------

def _demo_run() -> None:
    """Print example adapted configs for both signal-available and fallback cases.

    TODO (Batch 31+): Remove this demo block once integration tests cover the
    same scenarios in the real test suite.
    """
    import json

    # --- Case A: signals available, strategy_mode = conservative ----------
    signals_conservative = {
        "available": True,
        "strategy_mode": "conservative",
        "clarity_flag": "needs_review",
        "consistency_flag": "no_previous",
        "improvement_flag": "unknown",
        "source": "analysis_summary",
    }
    result_a = adapt_strategy_from_signals(signals_conservative)
    print("=== Case A: signals available (conservative) ===")
    print(json.dumps(result_a, ensure_ascii=False, indent=2))

    # --- Case B: signals available, strategy_mode = reinforce_theme ------
    signals_reinforce = {
        "available": True,
        "strategy_mode": "reinforce_theme",
        "clarity_flag": "clear",
        "consistency_flag": "consistent",
        "improvement_flag": "stable",
        "source": "analysis_summary",
    }
    result_b = adapt_strategy_from_signals(signals_reinforce)
    print("\n=== Case B: signals available (reinforce_theme) ===")
    print(json.dumps(result_b, ensure_ascii=False, indent=2))

    # --- Case C: signals unavailable (fallback) --------------------------
    result_c = adapt_strategy_from_signals(None)
    print("\n=== Case C: signals unavailable (default_fallback) ===")
    print(json.dumps(result_c, ensure_ascii=False, indent=2))

    # --- Case D: signals available=False (explicit fallback) -------------
    result_d = adapt_strategy_from_signals({"available": False, "strategy_mode": "conservative"})
    print("\n=== Case D: signals available=False (default_fallback) ===")
    print(json.dumps(result_d, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _demo_run()
