import os
from datetime import datetime, timedelta


def build_quality_wrapper(app, eval_once):
    max_retries = int(os.getenv("MAX_QUALITY_RETRIES", "5"))
    max_strategy_rounds = int(os.getenv("MAX_STRATEGY_REANALYSIS", "1"))

    def wrapped_eval():
        for attempt in range(1, max_retries + 2):
            if eval_once():
                return True
            if attempt > max_retries:
                break
            print(f"[Quality Loop] retry script generation {attempt}/{max_retries}")
            app.run_generator_script(diversify=True)

        for round_no in range(1, max_strategy_rounds + 1):
            print(f"[Quality Loop] refresh strategy context {round_no}/{max_strategy_rounds}")
            try:
                from constants import OBSIDIAN_VAULT_PATH
                app.search_and_save_trends(OBSIDIAN_VAULT_PATH)
            except Exception as exc:
                print(f"[Quality Loop] trend refresh skipped: {exc}")
            try:
                app.create_audience_insight()
            except Exception as exc:
                print(f"[Quality Loop] audience refresh skipped: {exc}")
            try:
                app.create_content_strategy()
            except Exception as exc:
                print(f"[Quality Loop] strategy refresh skipped: {exc}")
            app.run_generator_script(diversify=True)
            for attempt in range(1, max_retries + 2):
                if eval_once():
                    return True
                if attempt > max_retries:
                    break
                print(f"[Quality Loop] retry after refresh {attempt}/{max_retries}")
                app.run_generator_script(diversify=True)

        print("[Quality Loop] final status: research_failed_quality")
        try:
            app.update_pipeline(state="stopped", last_result="research_failed_quality")
            app.write_human_summary()
        except Exception:
            pass
        return False

    return wrapped_eval


def install_unique_generator_wrapper(app):
    import script_uniqueness_guard

    original_run_generator = app.run_generator_script
    max_attempts = int(os.getenv("MAX_SCRIPT_UNIQUENESS_RETRIES", "5"))

    def unique_run_generator(diversify=False):
        for attempt in range(1, max_attempts + 1):
            original_run_generator(diversify=(diversify or attempt > 1))
            if not script_uniqueness_guard.is_duplicate_script():
                script_uniqueness_guard.record_script_history()
                return True
            print(f"[Script Guard] duplicate script detected; regenerating {attempt}/{max_attempts}")
        print("[Script Guard] duplicate remained after retry limit; recording for audit")
        script_uniqueness_guard.record_script_history()
        return False

    app.run_generator_script = unique_run_generator


def run_ceo_guidance_preflight():
    """Generate CEO topic guidance before the publish cycle.

    Best-effort only: if local LLM or CEO dry-run fails, the existing publish
    flow continues with generator fallback behavior.
    """
    if os.getenv("ENABLE_CEO_PREFLIGHT", "true").lower() != "true":
        print("[CEO Preflight] disabled")
        return False

    try:
        import ceo_cycle_draft
        ceo_cycle_draft.main()
        print("[CEO Preflight] topic guidance ready")
        return True
    except Exception as exc:
        print(f"[CEO Preflight] skipped: {exc}")
        return False


def _interval_seconds():
    return int(os.getenv("PIPELINE_INTERVAL_SECONDS", "10800"))


def _next_run_at(seconds):
    return (datetime.now() + timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:%M:%S")


def _patch_pipeline_interval(app, state):
    seconds = _interval_seconds()
    try:
        app.update_pipeline(
            state=state,
            interval_seconds=seconds,
            next_run_at=_next_run_at(seconds),
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        app.write_human_summary()
    except Exception as exc:
        print(f"[Cycle Wrapper] interval status update skipped: {exc}")


def main():
    os.environ["PIPELINE_INTERVAL_SECONDS"] = os.getenv("PIPELINE_INTERVAL_SECONDS", "10800")
    os.environ["RUN_MODE"] = "publish"
    os.environ["RAG_MODE"] = os.getenv("RAG_MODE", "search")
    os.environ["SKIP_IMAGE_GENERATION"] = "false"
    os.environ["SKIP_DRIVE_UPLOAD"] = "false"
    os.environ["SKIP_INSTAGRAM_PUBLISH"] = "false"
    os.environ["SKIP_THREADS_IMAGE_PUBLISH"] = "false"
    os.environ["MAX_QUALITY_RETRIES"] = os.getenv("MAX_QUALITY_RETRIES", "5")
    os.environ["MAX_STRATEGY_REANALYSIS"] = os.getenv("MAX_STRATEGY_REANALYSIS", "1")
    os.environ["RUN_ONCE"] = "true"

    run_ceo_guidance_preflight()

    import content_evaluator
    import main_orchestrator

    install_unique_generator_wrapper(main_orchestrator)
    main_orchestrator.evaluate_script_quality = build_quality_wrapper(
        main_orchestrator,
        content_evaluator.evaluate_script_quality,
    )

    _patch_pipeline_interval(main_orchestrator, "starting")
    print("[Cycle Wrapper] 3 hour publish mode enabled")
    print("[Cycle Wrapper] RUN_ONCE=true; launchd owns the 3 hour schedule")
    print("[Cycle Wrapper] script uniqueness guard enabled")
    print("[Cycle Wrapper] CEO topic guidance preflight enabled")
    main_orchestrator.run_orchestration_loop()
    _patch_pipeline_interval(main_orchestrator, "waiting")


if __name__ == "__main__":
    main()
