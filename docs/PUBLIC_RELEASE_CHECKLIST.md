# Public Release Checklist

Use this before pushing the repository to GitHub.

## Keep Private

- `.env`, `.env.*`
- `token.json`, `client_secrets.json`, `google_creds.json`, `credentials*.json`
- `obsidian_vault/`
- `agent_runs/`, `logs/`, `jobs/active/`, `jobs/archive/`
- generated images such as `page*.png` and `generated_backgrounds/`
- generated request/response files such as `codex_*_requests.md` and `codex_*_response.json`

## Public Structure

- `prompts/`: agent prompts and output contracts
- `samples/`: safe example JSON payloads
- `config/`: non-secret strategy and policy reference data
- `scripts/`: portable local launch scripts
- `ops/launch_agents/`: sanitized macOS LaunchAgent examples
- `docs/`: operating rules and release notes
- `static/`, `templates/`: dashboard UI assets

## Before Push

1. Run the QA script: `./scripts/qa_checks.sh`
2. Check tracked files: `git status --short`
3. Confirm secret files are ignored: `git check-ignore .env token.json client_secrets.json obsidian_vault/test.md`
