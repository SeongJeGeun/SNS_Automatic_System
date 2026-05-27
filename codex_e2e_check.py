import json
import os
from datetime import datetime

from audience_research import create_audience_insight
from card_renderer import generate_card_news_images
from content_evaluator import evaluate_script_quality
from content_strategy import create_content_strategy
from self_healing_generator import main as generate_script
from upload_carousel import build_caption, get_script_data


REPORT_PATH = os.path.join("agent_runs", "codex_e2e_check_report.json")


def _file_exists(path):
    return os.path.exists(path) and os.path.getsize(path) > 0


def run_check():
    os.makedirs("agent_runs", exist_ok=True)
    report = {
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "safe_end_to_end_without_instagram_publish",
        "steps": [],
        "ok": False,
    }

    def step(name, fn, required_files=None):
        started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            result = fn()
            missing = [path for path in (required_files or []) if not _file_exists(path)]
            ok = not missing and result is not False
            detail = "ok" if ok else f"missing_or_failed: {missing}"
        except Exception as exc:
            ok = False
            detail = str(exc)
        report["steps"].append({
            "name": name,
            "started_at": started,
            "ok": ok,
            "detail": detail,
        })
        if not ok:
            raise RuntimeError(f"{name}: {detail}")
        return result

    try:
        step("Audience research", create_audience_insight, ["audience_insight.json", "codex_research_brief.md"])
        step("Content strategy", create_content_strategy, ["content_strategy.json", "codex_strategy_brief.md"])
        step("Story generation", generate_script, ["script.json", "codex_story_requests.md"])

        quality_ok = evaluate_script_quality()
        if not quality_ok:
            report["steps"].append({
                "name": "Quality check",
                "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ok": False,
                "detail": "quality_failed",
            })
            raise RuntimeError("quality_failed")
        report["steps"].append({
            "name": "Quality check",
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ok": True,
            "detail": "ok",
        })

        step("Card image render", generate_card_news_images, ["codex_image_requests.md"])
        script = get_script_data()
        page_count = len(script.get("pages", []))
        page_files = [f"page{i}.png" for i in range(1, page_count + 1)]
        missing_pages = [path for path in page_files if not _file_exists(path)]
        if missing_pages:
            raise RuntimeError(f"missing rendered pages: {missing_pages}")

        caption = build_caption(script)
        if not caption.strip():
            raise RuntimeError("caption_empty")

        report["steps"].append({
            "name": "Publish readiness",
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ok": True,
            "detail": "caption_built_and_images_ready; instagram_publish_skipped_for_safety",
        })
        report["page_files"] = page_files
        report["caption_preview"] = caption[:500]
        report["ok"] = True
    except Exception as exc:
        report["ok"] = False
        report["error"] = str(exc)
    finally:
        report["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(json.dumps(report, ensure_ascii=False, indent=2))

    return report["ok"]


if __name__ == "__main__":
    raise SystemExit(0 if run_check() else 1)
