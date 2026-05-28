"""Standalone local readiness diagnostics.

This command is not connected to the production runtime flow. Importing it has
no side effects; checks run only from `main()`.
"""

import argparse
import json
from typing import Any, Dict, Optional

from obsidian_context_reader import build_obsidian_context_reader
from ollama_adapter import OllamaRequest, build_default_ollama_adapter


def run_diagnostics(
    *,
    model_name: str = "tinyllama",
    endpoint: str = "http://localhost:11434",
    vault_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Run graceful local diagnostics for optional local dependencies.

    TODO: Add explicit model-list checks via `/api/tags`.
    TODO: Add vault ignore patterns and note ranking diagnostics.
    TODO: Add machine-readable severity levels once monitoring ownership exists.
    """
    adapter = build_default_ollama_adapter(model_name=model_name, endpoint=endpoint)
    ollama_response = adapter.generate(
        OllamaRequest(
            prompt="diagnostic ping",
            model_name=model_name,
            mode="diagnostic",
        )
    )

    notes_found = 0
    vault_readable = True
    if vault_path:
        reader = build_obsidian_context_reader(vault_path)
        notes = reader.list_markdown_files(limit=20)
        notes_found = len(notes)
        vault_readable = bool(notes) or reader.vault_path.exists()
    else:
        vault_readable = True

    model_configured = bool(model_name.strip())
    summary = {
        "ollama_endpoint": {
            "endpoint": endpoint,
            "reachable": bool(ollama_response.ok),
            "error": ollama_response.error,
        },
        "model_ready": bool(ollama_response.ok and model_configured),
        "model_name": model_name,
        "model_configured": model_configured,
        "vault_readable": vault_readable,
        "vault_path": vault_path,
        "notes_found": notes_found,
        "overall": True,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local model and vault readiness.")
    parser.add_argument("--model", default="tinyllama")
    parser.add_argument("--endpoint", default="http://localhost:11434")
    parser.add_argument("--vault-path", default=None)
    args = parser.parse_args()

    summary = run_diagnostics(
        model_name=args.model,
        endpoint=args.endpoint,
        vault_path=args.vault_path,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

