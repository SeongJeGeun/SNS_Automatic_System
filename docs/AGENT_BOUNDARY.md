# Agent Boundary

## Purpose

Define subsystem ownership so future implementation batches can stay small and reversible.

## Boundary Table

| Subsystem | Responsibility | Allowed inputs | Allowed outputs | Must not own |
|---|---|---|---|---|
| Orchestrator | Stage order, retry/stop decisions, state transitions, handoff between subsystems | Env config, scheduler signal, global state, declared stage artifacts | Pipeline state, job id, stage calls, final orchestration result | Stage internals, prompt construction details, rendering layout, platform API details |
| Scheduler | Start process, enforce interval, allow manual immediate run path | LaunchAgent/script invocation, interval config, force-run signal | Orchestrator start/resume call | Content generation, publishing, artifact mutation beyond scheduling state |
| Model bridge | Send prompt/request to external model/CLI and persist raw response | Prompt text, schema hint, output path, mode | Request markdown, response JSON/markdown, bridge error | Pipeline policy, quality scoring, business strategy rules |
| Trend intake | Collect external/local trend inputs and normalize research context | Search prompts, local trend files, Obsidian context | Audience research inputs, trend reports/briefs | Final story strategy, publish decisions, recovery policy |
| Strategy | Convert audience/performance context into story strategy | Audience insight, performance learning, recovery instruction | Strategy JSON, strategy brief | Scheduling, image rendering, platform API calls |
| Quality / validators | Score artifacts and produce pass/fail plus feedback | Script JSON, strategy/quality bar | Quality report, retry feedback | Story generation, retry loop ownership, publishing |
| Rendering | Produce visual backgrounds and final card images from approved script | Script JSON, visual hints, background assets | Background images, card PNGs, optional visual plan | Caption creation, publish API, quality policy |
| Publishing | Convert approved cards/caption into platform publish requests and record result | Script/caption, explicit image URLs or paths, platform credentials | Publish report, cooldown state, Sheets/Obsidian log side effects | Story generation, rendering, retrying quality failures |
| Monitoring | Record and expose runtime status/events | Orchestrator stage updates, publisher reports, global state files | Status JSON/Markdown, event log, dashboard-readable state | Owning pipeline decisions or mutating content artifacts |
| Recovery | Convert failures/performance signals into explicit recovery artifacts | Quality feedback, publish errors, performance reports, token/cooldown state | Recovery strategy, cooldown/escalation status, retry recommendation | Hidden mutation of normal strategy, uncontrolled retries, publishing directly |
| Telegram/dashboard control surfaces | Receive user commands and display state | User command, status files, queued command files | Command queue entries, status responses, notifications | Direct generation/publish policy, artifact format ownership |

## Boundary Rules

- Orchestrator owns flow; stages own artifacts.
- Recovery outputs must be explicit artifacts.
- Monitoring can observe all stages but should not duplicate stage policy.
- Control surfaces enqueue or request actions; they should not implement pipeline stages.
- Global account state stays in `agent_runs/`; content artifacts move toward job scope.

