import os

def build_quality_wrapper(app, eval_once):
    max_retries = int(os.getenv("MAX_QUALITY_RETRIES", "5"))
    max_strategy_rounds = int(os.getenv("MAX_STRATEGY_REANALYSIS", "1"))

    def wrapped_eval():
        for attempt in range(1, max_retries + 2):
            if eval_once():
                return True
            if attempt > max_retries:
                break
            print(f"[Quality Loop] 품질 미통과 → 대본 재생성 {attempt}/{max_retries}")
            app.run_generator_script(diversify=True)

        for round_no in range(1, max_strategy_rounds + 1):
            print(f"[Quality Loop] 재시도 초과 → 트렌드/오디언스/전략 재분석 {round_no}/{max_strategy_rounds}")

            try:
                from constants import OBSIDIAN_VAULT_PATH
                app.search_and_save_trends(OBSIDIAN_VAULT_PATH)
            except Exception as exc:
                print(f"[Quality Loop] 트렌드 재분석 스킵: {exc}")

            try:
                app.create_audience_insight()
            except Exception as exc:
                print(f"[Quality Loop] 오디언스 재분석 스킵: {exc}")

            try:
                app.create_content_strategy()
            except Exception as exc:
                print(f"[Quality Loop] 전략 재분석 스킵: {exc}")

            app.run_generator_script(diversify=True)

            for attempt in range(1, max_retries + 2):
                if eval_once():
                    return True
                if attempt > max_retries:
                    break
                print(f"[Quality Loop] 재분석 후 품질 미통과 → 대본 재생성 {attempt}/{max_retries}")
                app.run_generator_script(diversify=True)

        print("[Quality Loop] 최종 품질 미통과 → research_failed_quality")
        try:
            app.update_pipeline(
                state="stopped",
                last_result="research_failed_quality",
            )
            app.write_human_summary()
        except Exception:
            pass
        return False

    return wrapped_eval

def main():
    os.environ.setdefault("PIPELINE_INTERVAL_SECONDS", "10800")
    os.environ.setdefault("RUN_MODE", "publish")
    os.environ.setdefault("RAG_MODE", "search")
    os.environ.setdefault("SKIP_IMAGE_GENERATION", "false")
    os.environ.setdefault("SKIP_DRIVE_UPLOAD", "false")
    os.environ.setdefault("SKIP_INSTAGRAM_PUBLISH", "false")
    os.environ.setdefault("SKIP_THREADS_IMAGE_PUBLISH", "false")
    os.environ.setdefault("MAX_QUALITY_RETRIES", "5")
    os.environ.setdefault("MAX_STRATEGY_REANALYSIS", "1")

    import content_evaluator
    import main_orchestrator

    main_orchestrator.evaluate_script_quality = build_quality_wrapper(
        main_orchestrator,
        content_evaluator.evaluate_script_quality,
    )

    print("[Cycle Wrapper] 3시간 업로드 모드 실행")
    print("[Cycle Wrapper] 품질 재시도 + 트렌드/전략 재분석 fallback 활성화")
    main_orchestrator.main()

if __name__ == "__main__":
    main()
