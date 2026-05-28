# Future Architecture

## Goal

Keep the current behavior, but make runtime responsibilities easier to trace before any file movement or refactor.

## Minimal Target Shape

| Layer | Responsibility | Current Files To Keep Using Initially |
|---|---|---|
| Entry / scheduling | Start the process, enforce interval, allow manual run | `main_orchestrator.py`, `scheduler.py`, `scripts/`, LaunchAgents |
| Orchestration | Own stage order, stop/retry policy, state transitions | `main_orchestrator.py` |
| Generation | Audience, strategy, story, quality contracts | `audience_research.py`, `content_strategy.py`, `self_healing_generator.py`, `content_evaluator.py` |
| Rendering | Background generation and card composition | `image_generator.py`, `card_renderer.py` |
| Publishing | Platform upload, caption, publish report, cooldown | `upload_carousel.py`, metrics/token modules |
| State / artifacts | Job-scoped JSON, images, reports, status | `agent_runs/`, future `jobs/active/[JOB_ID]/` |
| Knowledge / feedback | Obsidian, Sheets, metrics, performance learning | `obsidian_*`, `google_sheet_manager.py`, `update_insights.py`, `performance_to_strategy.py` |
| Control UI | Telegram and dashboard commands/status | `telegram_*`, `dashboard_server.py`, `codex_command_bridge.py` |

## Target Runtime Contract

Use one job folder as the authoritative artifact boundary:

```text
jobs/active/[JOB_ID]/
  manifest.json
  audience_insight.json
  strategy.json
  script.json
  quality_report_1.json
  quality_report_2.json
  visual_plan.json
  cards/page1.png
  caption.json
  publish_plan.json
  final_status.json
```

Root-level files can remain as compatibility mirrors until callers are migrated.

## Target Control Flow

1. Entry point creates or resumes a job.
2. Orchestrator passes the job path to each stage.
3. Each stage reads only declared inputs and writes only declared outputs.
4. Quality failure writes feedback into the job folder and triggers one bounded retry.
5. Rendering writes cards under the job folder.
6. Publishing reads the job folder, writes publish status, then logs to Sheets/Obsidian.
7. Monitoring reads job status and pipeline status without owning generation logic.

## Minimal Boundaries To Establish First

| Boundary | Rule |
|---|---|
| Orchestrator vs stage modules | Orchestrator decides order; stage modules should not decide pipeline flow. |
| Generation vs rendering | Story JSON should be stable before image work starts. |
| Rendering vs publishing | Publishing should consume explicit image paths/URLs, not infer from global `page*.png` when job paths exist. |
| Monitoring vs runtime | Dashboard and Telegram should command or observe, not duplicate pipeline rules. |
| Recovery vs normal generation | Recovery should produce explicit strategy/feedback artifacts, not hidden prompt changes. |

## Non-Goals For The Next Batch

- No `src/` migration.
- No import path rewrite.
- No renaming of root runtime modules.
- No behavior change to publishing.
- No change to credentials or LaunchAgent behavior.

