"""Local scaffold-only dry-run for future pipeline integration.

This script intentionally stays outside the production runtime flow. It does
not start scheduler loops, publish content, read environment variables, or run
subprocesses. Ollama is checked only when explicitly requested.
"""

import argparse
from typing import List, Optional, Tuple

from gemma_bridge import LocalModelBridge, LocalModelRequest
from obsidian_context_reader import build_obsidian_context_reader
from ollama_adapter import OllamaRequest, build_default_ollama_adapter
from schema_validator import SchemaValidationRequest, SchemaValidator
from tone_validator import ToneValidationRequest, ToneValidator
from trend_collector import TrendCollector


def _read_obsidian_context(vault_path: Optional[str]) -> Tuple[bool, List[str]]:
    if not vault_path:
        return True, []

    reader = build_obsidian_context_reader(vault_path)
    snippets = reader.get_context_snippets(limit=2, max_chars_per_note=300)
    return True, [snippet.text for snippet in snippets]


def run_dryrun(
    *,
    vault_path: Optional[str] = None,
    enable_ollama: bool = False,
    model_name: str = "tinyllama",
) -> int:
    """Exercise the scaffold modules together with deterministic inputs.

    TODO: Replace placeholder payloads with job-scoped artifacts after the
    runtime migration contract is approved.
    TODO: Keep this dry-run separate from production publish/scheduler paths.
    TODO: Add explicit local-service diagnostics before any real generation use.
    """
    trend_result = TrendCollector().collect(platforms=["instagram", "threads"])
    obsidian_ok, context_snippets = _read_obsidian_context(vault_path)
    context_text = "\n\n".join(context_snippets)

    model_request = LocalModelRequest(
        prompt=(
            "Create a placeholder Instagram carousel concept.\n\n"
            f"Context:\n{context_text or '[no obsidian context supplied]'}"
        ),
        mode="story_json",
        schema_hint='{"title": "...", "pages": []}',
        metadata={"context_snippet_count": len(context_snippets)},
    )

    model_response = LocalModelBridge(model_name=model_name).generate(model_request)
    local_model_request_ok = bool(model_request.prompt.strip()) and bool(model_name.strip())

    if enable_ollama:
        ollama_response = build_default_ollama_adapter(model_name=model_name).generate(
            OllamaRequest(prompt=model_request.prompt, model_name=model_name, mode=model_request.mode)
        )
        optional_ollama_ok = True if ollama_response.ok else bool(ollama_response.error)
    else:
        optional_ollama_ok = True

    placeholder_output = {
        "title": "Dry-run scaffold concept",
        "pages": [
            {
                "page": 1,
                "heading": "Start small today",
                "sub_text": "Save this reminder before the day gets noisy.",
            }
        ],
    }

    schema_result = SchemaValidator().validate(
        SchemaValidationRequest(
            artifact_name="script.json",
            payload=placeholder_output,
            required_fields=["title", "pages"],
        )
    )

    tone_result = ToneValidator().validate(
        ToneValidationRequest(
            text="Save this reminder before the day gets noisy.",
            platform="instagram",
        )
    )

    checks = [
        ("obsidian_context_read", obsidian_ok),
        ("local_model_request_build", local_model_request_ok and not model_response.ok and bool(model_response.error)),
        ("optional_ollama_check", optional_ollama_ok),
        ("schema_validation", schema_result.ok),
        ("tone_validation", tone_result.ok),
    ]

    overall_ok = all(ok for _name, ok in checks)

    print("dryrun_pipeline_check")
    for name, ok in checks:
        print(f"- {name}: {'PASS' if ok else 'FAIL'}")
    print(f"overall: {'PASS' if overall_ok else 'FAIL'}")

    return 0 if overall_ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run scaffold-only local pipeline checks.")
    parser.add_argument("--vault-path", default=None)
    parser.add_argument("--enable-ollama", action="store_true")
    parser.add_argument("--model-name", default="tinyllama")
    args = parser.parse_args()
    return run_dryrun(
        vault_path=args.vault_path,
        enable_ollama=args.enable_ollama,
        model_name=args.model_name,
    )


if __name__ == "__main__":
    raise SystemExit(main())
