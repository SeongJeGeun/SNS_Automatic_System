# Batch Plan

## Scope

Only the first three implementation batches are defined here. No behavior change is included in this planning step.

## Batches

| Batch name | Goal | Allowed files to change | Forbidden files to change | Expected outputs | Validation method | Rollback note |
|---|---|---|---|---|---|---|
| Batch 1: Artifact Readiness Docs | Approve artifact names, ownership, and job/root compatibility rules. | `docs/ARTIFACT_CONTRACT.md`, `docs/AGENT_BOUNDARY.md`, `docs/BATCH_PLAN.md`, optional `samples/*.sample.json` only if explicitly approved | Runtime `.py`, scripts, LaunchAgents, credentials, generated runtime state | Approved docs and optional sample contract updates | File diff review | Delete or revert doc-only changes. |
| Batch 2: Job Context Planning Shim | Add a minimal non-invasive job context helper or plan for one, without changing stage behavior. | Only files explicitly approved after Batch 1; likely docs first, then a small helper module if approved | Existing generation, rendering, publishing logic unless listed in approved scope | A declared job id/path convention and compatibility strategy | Dry-run/import check if code is approved; otherwise doc diff | Remove helper/doc addition; no artifact migration should have occurred. |
| Batch 3: First Artifact Mirror | Migrate one low-risk generation artifact to also write job-scoped copy while preserving root output. | One approved producer and any required tests/docs; recommended candidate: audience insight only | Publisher, renderer, scheduler, dashboard, token/credential files | Root artifact unchanged plus matching job-scoped artifact | Run the single producer or safe pipeline subset; compare JSON contents | Revert producer change; root behavior remains authoritative. |

## Gate Before Runtime Changes

- Artifact contract approved.
- Boundary ownership accepted.
- Exact files for Batch 2 listed by user in `IMPLEMENT_BATCH` mode.
- Rollback path confirmed for each touched file.

## Batch 21: Production Switch

| Item | Decision |
|---|---|
| Goal | Make local audience insight generation the default producer path. |
| Primary model | `gemma4:26b` |
| Default timeout | `30` seconds via `OLLAMA_TIMEOUT_SECONDS` or generator default |
| Fallback | Existing non-local `audience_research.py` path if Ollama is unavailable, JSON parsing fails, or schema validation fails. |
| Hooks | Mirror, validation, and audit hooks remain unchanged. |
| Runtime boundary | Scheduler, renderer, publisher, Telegram, and scripts remain unchanged. |

### Batch 21 Validation Notes

- Default-path operational test should produce `audience_insight.json` with `status=local_obsidian_ollama_json_parsed`.
- Fallback test should force an unavailable Ollama endpoint and confirm the existing non-local path still writes an audience insight artifact.
- Next batch should measure repeated-run JSON consistency and model latency variance before expanding this pattern to other artifacts.

## Batch 23: Lightweight Quality Gate

| Item | Decision |
|---|---|
| Goal | Add a minimal audience insight readiness check before downstream strategy/script use. |
| Checks | `audience_state`, `story_angle`, and at least one item in `core_pains`, `emotional_keywords`, and `content_principles`. |
| Behavior | Non-blocking; failures log an `AUDIENCE_QUALITY` audit warning only. |
| Fallback | No fallback is triggered by quality warnings. Fallback remains limited to local model/schema failure. |
| Runtime boundary | Scheduler, renderer, publisher, Telegram, and scripts remain unchanged. |

### Batch 23 Validation Notes

- Compile changed Python files.
- Run one successful default local generation.
- Run one mocked quality failure and confirm warning logging while the caller continues.

## Batch 24: Quality Report Artifact

| Item | Decision |
|---|---|
| Goal | Write audience insight readiness metadata for optional downstream inspection. |
| Report path | `jobs/active/latest/reports/quality_report.json` |
| Fields | `quality_ok`, `warnings`, `generation_time_seconds`, `model`, `status`, `json_parse_ok`, `schema_ok`, `model_backed_fields` |
| Behavior | Non-blocking; report write failures do not stop generation. |
| Runtime boundary | Scheduler, renderer, publisher, Telegram, and scripts remain unchanged. |

### Batch 24 Validation Notes

- Compile changed Python files.
- Run one default `gemma4:26b` generation and verify the quality report exists.
- Confirm downstream stages are not invoked by this validation.

## Batch 26: JOB_ID Path Transition

| Item | Decision |
|---|---|
| Goal | Move audience insight mirror, audit, quality report, and audit log paths from `jobs/active/latest` to `jobs/[JOB_ID]`. |
| Job id source | `JOB_ID` environment variable. |
| Missing job id | Auto-generate a timestamp id and log a non-blocking warning. |
| Compatibility | `USE_ACTIVE_LATEST=true` forces old `jobs/active/latest` paths and logs a warning. |
| Paths | `jobs/[JOB_ID]/audience_insight.json`, `jobs/[JOB_ID]/reports/audit.json`, `jobs/[JOB_ID]/reports/quality_report.json`, `jobs/[JOB_ID]/reports/audit_log.txt` |
| Runtime boundary | Scheduler, renderer, publisher, Telegram, and scripts remain unchanged. |

### Batch 26 Validation Notes

- Compile changed Python files.
- Run one `JOB_ID=test-001` path check.
- Run one no-`JOB_ID` path check and confirm auto-generated directory plus warning log.

## Batch 27: Evaluation / Analysis Layer

| Item | Decision |
|---|---|
| Goal | Add deterministic analysis metadata for each generated audience insight. |
| Report path | `jobs/[JOB_ID]/reports/analysis_report.json` |
| Inputs | Current `audience_insight.json`, current `quality_report.json`, previous job artifacts when available. |
| Metrics | `content_clarity`, `field_completeness`, `theme_consistency`, `improvement_vs_previous`, `notes`. |
| Behavior | Non-blocking; failures do not stop generation or downstream flow. |
| Runtime boundary | Scheduler, renderer, publisher, Telegram, and scripts remain unchanged. |

### Batch 27 Validation Notes

- Compile changed Python files.
- Run two test jobs with distinct `JOB_ID` values.
- Confirm the second job writes an analysis report with previous-job comparison metadata.

## Batch 28: Downstream Reads Analysis Report

| Item | Decision |
|---|---|
| Goal | Expose compact analysis metrics to downstream strategy/script stages. |
| Interface | `analysis_report_reader.read_analysis_summary(job_id)` |
| Metrics | `content_clarity`, `improvement_vs_previous`, `theme_consistency.overlap_count` |
| Missing report | Return graceful defaults with `available=false`; do not block downstream. |
| Runtime boundary | Scheduler, renderer, publisher, Telegram, and scripts remain unchanged. |

### Batch 28 Validation Notes

- Compile changed Python files.
- Run one test job with `JOB_ID`.
- Confirm `read_analysis_summary(job_id)` returns real metrics.
- Confirm missing job id/report returns graceful defaults.

## Batch 29: Downstream Strategy Signals

| Item | Decision |
|---|---|
| Goal | Convert `analysis_summary` into compact advisory strategy signals. |
| Interface | `strategy_signal_builder.build_strategy_signals(analysis_summary)` |
| Signals | `strategy_mode`, `clarity_flag`, `consistency_flag`, `improvement_flag` |
| Missing analysis | Return conservative defaults; do not block execution. |
| Runtime boundary | Scheduler, renderer, publisher, Telegram, and scripts remain unchanged. |

### Batch 29 Validation Notes

- Compile changed Python files.
- Run one job with analysis available and confirm `strategy_signals`.
- Run one missing-analysis signal build and confirm conservative defaults.

## Batch 30: Downstream Strategy Consumes Signals

| Item | Decision |
|---|---|
| Goal | Let downstream strategy/script modules optionally read `strategy_signals` and adapt behavior without changing publish or blocking behavior. |
| Interface | `example_strategy_consumer.adapt_strategy_from_signals(strategy_signals)` |
| Adaptation rules | `strategy_mode=conservative` → short output, safe template; `strategy_mode=reinforce_theme` → repeat theme, add Obsidian context; `clarity_flag=needs_review` → high prompt specificity. |
| Missing signals | Return `_DEFAULT_CONSERVATIVE_STRATEGY` with `source=default_fallback`; no exception raised. |
| New files | `example_strategy_consumer.py` (reference consumer, non-blocking). |
| Modified files | `audience_research.py` (module-level docstring + `_attach_strategy_signals` docstring only). |
| Runtime boundary | Scheduler, renderer, publisher, Telegram, and scripts remain unchanged. No blocking behavior added. |

### Batch 30 Validation Notes

- `python3 -m py_compile audience_research.py` and `python3 -m py_compile example_strategy_consumer.py` must pass.
- Run `python3 example_strategy_consumer.py` to produce example configs for signals-available (conservative + reinforce_theme) and signals-missing cases.
- Confirm no upload, Telegram, or scheduler code is touched.
- Confirm `adapt_strategy_from_signals(None)` returns `source=default_fallback` with conservative defaults.

## Batch 31: Integrate Strategy Adapter into Production

| Item | Decision |
|---|---|
| Goal | Integrate `adapt_strategy_from_signals()` into `content_strategy.py` so quality signals directly affect generation config. |
| Integration point | `content_strategy.py` → `create_content_strategy()` calls `_attach_signal_adaptation()` after building the base strategy. |
| Signal source | `audience_insight.json["strategy_signals"]` — persisted by new `_persist_strategy_signals()` in `audience_research.py`. |
| Adaptation applied | `quality_bar.minimum_score` (conservative → 65); `story_structure` (conservative → compress; reinforce_theme → theme lock); `hook_rules` (clarity=needs_review → specificity directive); `obsidian_context_enabled` (reinforce_theme → True). |
| Audit field | `adapted_strategy_config` written into `content_strategy.json` for downstream inspection. |
| Missing signals | `adapt_strategy_from_signals(None)` returns conservative defaults; `_attach_signal_adaptation()` swallows all exceptions. |
| New files | None. |
| Modified files | `content_strategy.py`, `audience_research.py` (`_persist_strategy_signals` added). |
| Runtime boundary | Scheduler, renderer, publisher, Telegram, and scripts remain unchanged. No blocking behavior added. |

### Batch 31 Validation Notes

- `python3 -m py_compile content_strategy.py` and `python3 -m py_compile audience_research.py` must pass.
- Run E2E test with signals-available (conservative) and confirm `adapted_strategy_config.strategy_mode == "conservative"` in `content_strategy.json`.
- Run E2E test with signals missing (`audience_insight.json` has no `strategy_signals`) and confirm conservative defaults applied.
- Confirm `adapted_strategy_config` field is written to `content_strategy.json` in both cases.
- Confirm `_persist_strategy_signals` updates `audience_insight.json` with `strategy_signals` after generation.

## Batch 32: Self-Healing Generator Consumes obsidian_context_enabled

| Item | Decision |
|---|---|
| Goal | Wire `obsidian_context_enabled` from `content_strategy.json` into `self_healing_generator.py` so reinforce-theme strategy influences prompt/context construction. |
| Flag reader | `_load_obsidian_context_flag("content_strategy.json")` — returns `True` only when field is explicitly `True`; non-blocking. |
| Effect when True | RAG query enriched via `_enrich_rag_query()` with theme-continuity terms; `[OBSIDIAN_REINFORCE]` prompt block injected before RAG section via `_build_obsidian_reinforce_block()`. |
| Effect when False/missing | Existing prompt construction unchanged; no new blocks added. |
| Error handling | Any exception in enrichment path is caught and logged; generator continues with original prompt. |
| New files | None. |
| Modified files | `self_healing_generator.py` only. |
| Runtime boundary | Scheduler, renderer, publisher, Telegram, and scripts remain unchanged. No blocking behavior added. |

### Batch 32 Validation Notes

- `python3 -m py_compile self_healing_generator.py` must pass.
- Simulate `obsidian_context_enabled=True`: confirm RAG query is enriched and `[OBSIDIAN_REINFORCE]` block appears in prompt.
- Simulate `obsidian_context_enabled=False/missing`: confirm prompt is identical to pre-Batch-32 output.
- Confirm `_load_obsidian_context_flag()` returns `False` when file is absent or field is missing.
- Confirm no upload, Telegram, or scheduler code is touched.

## Batch 33: Status Heartbeat / Dashboard Visibility

| Item | Decision |
|---|---|
| Goal | Expose key runtime state into a lightweight job-scoped status artifact for 24/7 monitoring without changing publish behavior. |
| New module | `agent_status_writer.py` — provides `write_job_status()`, `update_job_status()`, `read_job_status()`. No import-time side effects. |
| Status path | `jobs/[JOB_ID]/reports/agent_status.json` |
| Status fields | `job_id`, `model`, `generation_status`, `quality_ok`, `quality_warnings`, `analysis_available`, `strategy_mode`, `obsidian_context_enabled`, `generation_time_seconds`, `updated_at`, `clarity_flag`, `consistency_flag`, `improvement_flag`, `signal_source`, `story_agent_stage` |
| Integration: audience_research | `_write_job_status_from_insight()` called after signals persisted in both local-draft and fallback branches. |
| Integration: self_healing_generator | `update_job_status()` patches `obsidian_context_enabled` and `story_agent_stage` after flag is resolved. |
| Global status | `agent_runs/agent_status.json` (owned by `agent_monitor.py`) is never touched. |
| Error handling | All writes catch all exceptions; execution continues unchanged. Missing data fields → graceful defaults. |
| Modified files | `audience_research.py`, `self_healing_generator.py`. |
| New files | `agent_status_writer.py`. |
| Runtime boundary | Scheduler, renderer, publisher, Telegram, and scripts remain unchanged. No blocking behavior added. |

### Batch 33 Validation Notes

- `python3 -m py_compile agent_status_writer.py`, `audience_research.py`, `self_healing_generator.py` must pass.
- Run happy-path example: confirm `jobs/{JOB_ID}/reports/agent_status.json` contains all required fields.
- Run partial-data example (no strategy signals): confirm graceful defaults written without error.
- Confirm `agent_runs/agent_status.json` is unmodified.
- Confirm no upload, Telegram, or scheduler code is touched.
