# MindFactory SNS Automation — Repository Structure

## Top-Level Layout

```
SNS_Automatic_System/
├── prompts/            # Stage prompt files for all AI agents
├── samples/            # Reference JSON schemas (one per contract file)
├── config/             # Public non-secret strategy and policy JSON
├── jobs/
│   ├── active/         # Local runtime artifacts, ignored by Git
│   └── archive/        # Local completed job artifacts, ignored by Git
├── logs/               # Local orchestrator and system logs, ignored by Git
├── scripts/            # Shell scripts for launching pipeline and dashboard
├── ops/launch_agents/  # Sanitized macOS LaunchAgent examples
├── docs/               # Governance and reference documentation (this folder)
├── agent_runs/         # Runtime state: PIDs, Instagram status, Telegram offset
├── generated_backgrounds/ # Image asset store (one subfolder per generation run)
├── static/             # Dashboard UI (CSS, JS)
├── templates/          # Dashboard HTML
├── launch_agents/      # Local LaunchAgent files, ignored by Git
├── obsidian_vault/     # External knowledge base, ignored by Git
├── faiss_index/        # Vector index for RAG (auto-generated)
├── .env                # Secrets — never commit, never move
├── .env.example        # Safe reference template
├── client_secrets.json # Google OAuth credentials — never move
├── token.json          # Google OAuth token — never move
├── .gitignore
└── README.md
```

## Folder Purpose Summary

| Folder | Owner | Contents |
|---|---|---|
| `prompts/` | Humans + AI | Stage prompt `.md` files. Stable. Version-controlled. |
| `samples/` | Humans + AI | `*.sample.json` files. One per contract file. Read-only reference. |
| `config/` | Humans + AI | Non-secret strategy, policy, and reference JSON. |
| `jobs/active/` | Orchestrator | Local folders for active job artifacts. Ignored by Git. |
| `jobs/archive/` | Orchestrator | Local completed job artifacts. Ignored by Git. |
| `logs/` | System | Local logs. Ignored by Git. |
| `scripts/` | Humans | Shell scripts to start pipeline and dashboard. |
| `ops/launch_agents/` | Humans | Safe plist examples without personal absolute paths. |
| `docs/` | Humans | Governance docs. Short and specific. |
| `agent_runs/` | Runtime | Ephemeral state. PIDs, Instagram cooldown, Telegram offset. |

## What Stays at Root

Only files that tools, OS, or conventions require at root:
- `.env`, `.env.example` — environment config
- `client_secrets.json`, `token.json` — Google auth
- `.gitignore`, `README.md` — project metadata
- All Python `.py` source files — pending `src/` migration (Phase 4)
