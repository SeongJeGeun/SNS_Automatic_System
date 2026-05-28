# Change Plan

## Current Runtime Files

Likely core runtime files:

| Area | Files |
|---|---|
| Orchestration / schedule | `main_orchestrator.py`, `scheduler.py` |
| Monitoring | `agent_monitor.py`, `dashboard_server.py` |
| Generation | `audience_research.py`, `content_strategy.py`, `self_healing_generator.py`, `content_evaluator.py` |
| Rendering | `card_renderer.py`, `image_generator.py` |
| Publishing | `upload_carousel.py`, `instagram_token_manager.py`, `instagram_metrics.py`, `threads_metrics.py` |
| Feedback / strategy | `update_insights.py`, `performance_to_strategy.py`, `optimal_timing.py` |
| Storage / integrations | `google_sheet_manager.py`, `obsidian_rag.py`, `obsidian_publish_sync.py`, `obsidian_linker.py` |
| Command bridges | `telegram_agent.py`, `telegram_commander.py`, `codex_text_bridge.py`, `codex_command_bridge.py`, `antigravity_bridge.py` |
| Config constants | `constants.py`, selected `config/*.json` |

## Support / Docs / Peripheral Files

| Category | Files / Folders |
|---|---|
| Docs | `README.md`, `docs/*.md` |
| Prompts | `prompts/*.md` |
| Samples | `samples/*.json` |
| Dashboard UI assets | `templates/`, `static/` |
| Ops examples | `ops/launch_agents/`, `scripts/` |
| Runtime state | `agent_runs/`, `logs/`, `generated_backgrounds/`, `faiss_index/` |
| Local knowledge / credentials | `obsidian_vault/`, `.env`, `token.json`, `client_secrets.json` |
| Current root artifacts | `audience_insight.json`, `content_strategy.json`, `script.json`, `content_quality_report.json`, `page*.png`, `codex_*` |

## Overlaps And Confusion Points

| Issue | Why It Is Confusing | Suggested Direction |
|---|---|---|
| Root artifacts vs documented job folders | Docs describe `jobs/active`, but runtime mostly writes root files. | Introduce job path compatibility gradually. |
| `scheduler.py` vs `main_orchestrator.py` | `scheduler.py` is only a wrapper but can look like a second scheduler. | Document it as legacy compatibility. |
| Codex vs Antigravity naming | Files use both names for the same bridge pattern. | Pick one public term in docs, keep filenames for now. |
| Recovery logic is scattered | Quality retry, performance healing, token/cooldown handling live in different modules. | Define recovery artifacts and state transitions first. |
| Dashboard/Telegram can enqueue commands | Control surfaces risk duplicating runtime policy. | Keep them as command/status adapters. |
| Publishing also logs and cleans images | `upload_carousel.py` uploads, writes reports, appends Sheets, removes local files. | Split only after artifact paths are stable. |
| Threads is documented more than implemented | Docs describe Threads publishing and monitoring, but current primary publish path is Instagram carousel. | Mark Threads as planned/partial until code path is confirmed. |

## Batch Plan

| Batch | Scope | Files Allowed | Verification |
|---|---|---|---|
| 1 | Create architecture docs only. | `docs/CURRENT_FLOW_MAP.md`, `docs/FUTURE_ARCHITECTURE.md`, `docs/CHANGE_PLAN.md` | File diff only. |
| 2 | Add an artifact contract doc or schema index. | Docs/samples only | Compare docs to current filenames. |
| 3 | Add job-path planning shim without changing behavior. | Approved runtime files only | Dry-run / existing QA. |
| 4 | Migrate one stage output to job folder with root mirror. | One generation stage only | Diff, script output, generated JSON. |
| 5 | Migrate renderer to explicit input/output paths. | Renderer files only | Render test produces expected PNGs. |
| 6 | Migrate publisher to consume explicit job image URLs/paths. | Publisher/orchestrator only | Safe test without publishing where possible. |

## Recommended Next Batch

Batch 2: create a concise artifact contract index that reconciles current root files with the documented future `jobs/active/[JOB_ID]` structure.

Do not start implementation refactors until that contract is approved.

