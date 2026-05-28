# Current Flow Map

## Scope

This map reflects the current runtime path observed in the repository without changing runtime code.

## Primary Execution Path

| Phase | Current Entry | Main Runtime Files | Main Outputs / State |
|---|---|---|---|
| Scheduling / launch | `scripts/run_codex_pipeline_3h.sh`, LaunchAgent plists, `scheduler.py` wrapper | `main_orchestrator.py`, `scheduler.py` | `logs/`, `agent_runs/agent_status.json`, `agent_runs/agent_status.md` |
| Orchestration | `main_orchestrator.py` | `main_orchestrator.py`, `agent_monitor.py`, `telegram_agent.py` | pipeline state, agent events, Telegram notices |
| Recovery / performance pre-check | inside orchestration loop | `main_orchestrator.py`, `optimal_timing.py`, `performance_to_strategy.py`, `update_insights.py` | `self_healing_strategy.json`, strategy updates, cooldown/status files |
| Audience research | `create_audience_insight()` | `audience_research.py`, `antigravity_bridge.py` | `audience_insight.json`, research briefs |
| Strategy generation | `create_content_strategy()` | `content_strategy.py` | `content_strategy.json`, `codex_strategy_brief.md` |
| Story generation | subprocess call from orchestrator | `self_healing_generator.py`, `codex_text_bridge.py`, `obsidian_rag.py`, `google_sheet_manager.py` | `script.json`, Codex/Antigravity request and response files |
| Quality gate | direct function call | `content_evaluator.py` | `content_quality_report.json`, optional feedback JSON |
| Visual generation | direct function call | `card_renderer.py`, `image_generator.py`, `antigravity_bridge.py` | `generated_backgrounds/`, `page1.png` ... `pageN.png`, image request brief |
| Temporary hosting | inside orchestration loop | `main_orchestrator.py`, Google Drive APIs | public Drive URLs, temporary Drive file IDs |
| Publishing | direct module call | `upload_carousel.py`, `google_sheet_manager.py`, `obsidian_publish_sync.py` | Instagram post, Sheets row, upload report, publish cooldown |
| Monitoring | status updates during all phases | `agent_monitor.py`, `dashboard_server.py`, `telegram_agent.py` | dashboard UI, Telegram commands, `agent_runs/*` |
| Recovery after failure | scattered exception handlers | `main_orchestrator.py`, `upload_carousel.py`, `self_healing_generator.py`, `instagram_token_manager.py` | stopped/error state, retry, cooldown, Telegram report |

## Current High-Level Runtime Sequence

1. `main_orchestrator.main()` starts continuous loop.
2. Startup duplicate guard checks last Sheet record and waits unless forced.
3. `run_orchestration_loop()` updates monitor state.
4. Google Drive/Sheets services are prepared.
5. Previous performance is checked and may create `self_healing_strategy.json`.
6. Trend search and insight sync run.
7. Obsidian RAG index is refreshed.
8. Audience insight and content strategy are generated.
9. Story generator writes `script.json`.
10. Quality evaluator either passes, retries once, or stops.
11. Renderer creates local `page*.png` images.
12. Images are uploaded to Google Drive for temporary public URLs.
13. `upload_carousel.main()` publishes Instagram carousel.
14. Upload result is logged to Sheets and Obsidian sync.
15. Temporary Drive files are cleaned.
16. Daily report check runs.
17. Monitor state returns to waiting, then loop sleeps until next run.

## Monitoring And Control Path

| Control Surface | Files |
|---|---|
| Telegram commands and notifications | `telegram_agent.py`, `telegram_commander.py`, `codex_command_bridge.py` |
| Dashboard | `dashboard_server.py`, `templates/dashboard.html`, `static/dashboard.js`, `static/dashboard.css` |
| Agent status | `agent_monitor.py`, `agent_runs/agent_status.json`, `agent_runs/agent_events.jsonl` |
| Manual / external Codex requests | `codex_command_bridge.py`, `codex_text_bridge.py`, root `codex_*` markdown/json files |

## Current Artifact Pattern

The docs describe a future `jobs/active/[JOB_ID]/...` contract, but current runtime still writes many artifacts directly at repository root:

| Current Root Artifact | Role |
|---|---|
| `audience_insight.json` | Audience research output |
| `content_strategy.json` | Strategy output and performance learning carrier |
| `script.json` | Main story/render/publish contract |
| `content_quality_report.json` | Quality gate result |
| `content_quality_feedback.json` | Optional retry input |
| `self_healing_strategy.json` | Recovery prompt injection |
| `page*.png` | Rendered upload images |
| `codex_*` files | External generation/command bridge requests and responses |

