"""Standalone local audience insight draft generator.

This command is not connected to the production runtime flow. Importing it has
no side effects; generation runs only from `main()`.
"""

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from gemma_bridge import LocalModelBridge, LocalModelRequest
from obsidian_context_reader import build_obsidian_context_reader
from ollama_adapter import OllamaRequest, build_default_ollama_adapter
from schema_validator import validate_audience_insight_draft


MODEL_BACKED_INSIGHT_FIELDS = [
    "core_pains",
    "audience_state",
    "emotional_keywords",
    "needed_message",
    "story_angle",
    "content_principles",
    "trending_topics",
    "hot_pain_keywords",
]
DEFAULT_MODEL_NAME = "gemma4:26b"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 30.0


def read_context_snippets(vault_path: Optional[str]) -> List[Dict[str, str]]:
    """Read short markdown snippets from a filesystem-only Obsidian vault."""
    if not vault_path:
        return []

    reader = build_obsidian_context_reader(vault_path)
    snippets = reader.get_context_snippets(limit=5, max_chars_per_note=700)
    return [
        {
            "path": snippet.path,
            "title": snippet.title,
            "text": snippet.text,
        }
        for snippet in snippets
    ]


def build_prompt(context_notes: List[Dict[str, str]]) -> str:
    """Build a minimal prompt from available local notes.

    TODO: Add stronger prompt composition with explicit audience schema.
    TODO: Add note ranking before choosing context snippets.
    """
    context_text = "\n\n".join(
        f"# {note['title']}\n{note['text']}" for note in context_notes
    )
    return (
        "Create a concise audience insight draft for a Korean Instagram/Threads "
        "self-improvement content system. Focus on current pain points, emotional "
        "keywords, and one needed message.\n\n"
        "Return only valid JSON with these fields: audience_state, core_pains, "
        "emotional_keywords, needed_message, story_angle, content_principles, "
        "trending_topics, hot_pain_keywords. String fields must be concise. "
        "List fields must contain short strings.\n\n"
        f"Local Obsidian context:\n{context_text or '[no local context supplied]'}"
    )


def build_placeholder_insight(context_notes: List[Dict[str, str]]) -> Dict[str, Any]:
    """Build deterministic production-like insight fields.

    TODO: Replace these placeholders with parsed model output once schema
    enforcement is approved.
    """
    context_titles = [note["title"] for note in context_notes]
    audience_state = (
        "Readers are mentally tired, distracted by competing demands, and "
        "looking for one concrete next step that feels possible today."
    )
    core_pains = [
        "fatigue from vague self-improvement pressure",
        "difficulty turning motivation into a repeatable system",
        "decision fatigue when the next action is unclear",
    ]
    emotional_keywords = [
        "fatigue",
        "distraction",
        "pressure",
        "uncertainty",
        "need for action",
    ]
    needed_message = (
        "Make the next action small, concrete, and repeatable instead of asking "
        "readers to rely on more motivation."
    )
    story_angle = (
        "Start from the reader's tired state, reframe the issue as a missing "
        "system, then offer one small action that can be saved and repeated."
    )
    content_principles = [
        "Lead with a recognizable daily pain.",
        "Avoid blaming the reader for low energy.",
        "Turn the insight into one concrete behavior.",
        "End with a save-worthy reminder or checklist.",
    ]
    return {
        "insight_summary": audience_state,
        "audience_signals": [
            *emotional_keywords[:3],
            *[f"local_note:{title}" for title in context_titles[:3]],
        ],
        "content_angles": [
            "small next step",
            "reduce decision fatigue",
            "turn vague motivation into a repeatable system",
        ],
        "audience_state": audience_state,
        "core_pains": core_pains,
        "emotional_keywords": emotional_keywords,
        "needed_message": needed_message,
        "story_angle": story_angle,
        "content_principles": content_principles,
        "trending_topics": [
            "small next step",
            "decision fatigue",
            "repeatable system",
        ],
        "hot_pain_keywords": emotional_keywords[:5],
    }


def _coerce_string(value: Any, fallback: str) -> str:
    value = str(value or "").strip()
    return value if value else fallback


def _coerce_string_list(value: Any, fallback: List[str], limit: int = 6) -> List[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str):
        items = [part.strip() for part in value.split(",") if part.strip()]
    else:
        items = []
    return (items or fallback)[:limit]


def _extract_balanced_json_objects(text: str) -> Iterable[str]:
    start = None
    depth = 0
    in_string = False
    escape = False

    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                yield text[start:index + 1]
                start = None


def extract_json_candidates(generated_text: str) -> List[str]:
    """Return likely JSON objects from raw model text.

    TODO: Prefer Ollama JSON format mode once model support and adapter policy
    are approved.
    """
    candidates: List[str] = []
    text = generated_text.strip()
    if text:
        candidates.append(text)

    for match in re.finditer(r"```(?:json)?\s*(.*?)```", generated_text, re.DOTALL | re.IGNORECASE):
        block = match.group(1).strip()
        if block:
            candidates.append(block)

    candidates.extend(_extract_balanced_json_objects(generated_text))

    unique_candidates: List[str] = []
    seen = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique_candidates.append(candidate)
    return unique_candidates


def parse_model_insight(generated_text: str, fallback: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Parse model JSON into production-like insight fields.

    TODO: Add stronger prompt engineering for consistently valid JSON.
    TODO: Use Ollama JSON format mode where available.
    TODO: Add stricter schema validation and repair for malformed model output.
    TODO: Add content quality checks before model-backed output is trusted.
    """
    parsed = None
    for candidate in extract_json_candidates(generated_text):
        try:
            candidate_payload = json.loads(candidate)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(candidate_payload, dict):
            parsed = candidate_payload
            break

    if not isinstance(parsed, dict):
        return fallback, False

    structured = {
        "insight_summary": _coerce_string(
            parsed.get("insight_summary") or parsed.get("audience_state"),
            fallback["insight_summary"],
        ),
        "audience_signals": _coerce_string_list(
            parsed.get("audience_signals") or parsed.get("emotional_keywords"),
            fallback["audience_signals"],
        ),
        "content_angles": _coerce_string_list(
            parsed.get("content_angles") or parsed.get("trending_topics"),
            fallback["content_angles"],
        ),
        "audience_state": _coerce_string(
            parsed.get("audience_state"),
            fallback["audience_state"],
        ),
        "core_pains": _coerce_string_list(
            parsed.get("core_pains"),
            fallback["core_pains"],
        ),
        "emotional_keywords": _coerce_string_list(
            parsed.get("emotional_keywords"),
            fallback["emotional_keywords"],
        ),
        "needed_message": _coerce_string(
            parsed.get("needed_message"),
            fallback["needed_message"],
        ),
        "story_angle": _coerce_string(
            parsed.get("story_angle"),
            fallback["story_angle"],
        ),
        "content_principles": _coerce_string_list(
            parsed.get("content_principles"),
            fallback["content_principles"],
        ),
        "trending_topics": _coerce_string_list(
            parsed.get("trending_topics"),
            fallback["trending_topics"],
            limit=5,
        ),
        "hot_pain_keywords": _coerce_string_list(
            parsed.get("hot_pain_keywords"),
            fallback["hot_pain_keywords"],
            limit=5,
        ),
    }
    return structured, True


def generate_local_draft(
    *,
    model_name: str = DEFAULT_MODEL_NAME,
    endpoint: str = "http://localhost:11434",
    vault_path: Optional[str] = None,
    ollama_timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Generate or scaffold an audience insight draft.

    TODO: Enforce the final audience insight JSON schema after approval.
    TODO: Route model calls through the generic bridge once adapter policy is set.
    """
    context_notes = read_context_snippets(vault_path)
    prompt = build_prompt(context_notes)
    resolved_timeout = (
        ollama_timeout_seconds
        if ollama_timeout_seconds is not None
        else os.getenv("OLLAMA_TIMEOUT_SECONDS") or DEFAULT_OLLAMA_TIMEOUT_SECONDS
    )

    scaffold_response = LocalModelBridge(model_name=model_name).generate(
        LocalModelRequest(
            prompt=prompt,
            mode="audience_insight",
            metadata={"context_notes": len(context_notes)},
        )
    )

    ollama_response = build_default_ollama_adapter(
        model_name=model_name,
        endpoint=endpoint,
        timeout_seconds=resolved_timeout,
    ).generate(
        OllamaRequest(
            prompt=prompt,
            model_name=model_name,
            mode="audience_insight",
        )
    )

    placeholder_insight = build_placeholder_insight(context_notes)
    json_parse_ok = False

    if ollama_response.ok and ollama_response.text.strip():
        generated_text = ollama_response.text.strip()
        structured_insight, json_parse_ok = parse_model_insight(
            generated_text,
            placeholder_insight,
        )
        if json_parse_ok:
            model_backed_fields = MODEL_BACKED_INSIGHT_FIELDS[:]
            status = "local_obsidian_ollama_json_parsed"
            error = None
        else:
            structured_insight = placeholder_insight
            model_backed_fields = []
            status = "local_obsidian_ollama_no_json"
            error = "ollama response did not contain parseable JSON"
    else:
        generated_text = (
            "Scaffold audience insight: readers may be tired, distracted, and "
            "looking for one concrete next step. Use local notes and performance "
            "signals to refine this draft before runtime use."
        )
        structured_insight = placeholder_insight
        model_backed_fields = []
        status = "placeholder_no_ollama"
        error = ollama_response.error or scaffold_response.error

    trending_topics = _coerce_string_list(
        structured_insight.get("trending_topics"),
        ["small next step", "decision fatigue", "repeatable system"],
        limit=5,
    )
    hot_pain_keywords = _coerce_string_list(
        structured_insight.get("hot_pain_keywords"),
        structured_insight["emotional_keywords"][:5],
        limit=5,
    )
    draft = {
        "artifact_type": "audience_insight",
        "source": "local_standalone",
        "model": model_name,
        "endpoint": endpoint,
        "ollama_timeout_seconds": ollama_response.metadata.get("timeout_seconds"),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "research_mode": "local_obsidian_ollama_opt_in",
        "context_notes": context_notes,
        "local_trend_sources": [
            {
                "source": note["path"],
                "excerpt": note["text"][:1600],
            }
            for note in context_notes
        ],
        "trending_topics": trending_topics,
        "hot_pain_keywords": hot_pain_keywords,
        "generated_text": generated_text,
        "status": status,
        "error": error,
        "compatibility": {
            "production_like": True,
            "json_parse_ok": json_parse_ok,
            "model_backed_fields": model_backed_fields,
            "warnings": [
                "fields fall back individually when model output is unavailable or malformed",
                "structured fields are model-backed only when model JSON is parsed successfully",
                "model-backed content has not passed deep quality checks yet",
            ],
        },
        **structured_insight,
    }
    validation = validate_audience_insight_draft(draft)
    draft["schema_check"] = {
        "ok": validation.ok,
        "findings": validation.findings,
    }
    return draft


def write_draft(output_path: str, draft: Dict[str, Any]) -> None:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(draft, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a local audience insight draft.")
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--endpoint", default="http://localhost:11434")
    parser.add_argument("--vault-path", default=None)
    parser.add_argument("--output", default="audience_insight.local_draft.json")
    parser.add_argument(
        "--ollama-timeout-seconds",
        type=float,
        default=None,
        help="Optional Ollama request timeout; defaults to OLLAMA_TIMEOUT_SECONDS or 30 seconds.",
    )
    args = parser.parse_args()

    draft = generate_local_draft(
        model_name=args.model,
        endpoint=args.endpoint,
        vault_path=args.vault_path,
        ollama_timeout_seconds=args.ollama_timeout_seconds,
    )
    write_draft(args.output, draft)
    print(
        json.dumps(
            {
                "output": args.output,
                "status": draft["status"],
                "model": draft["model"],
                "context_notes": len(draft["context_notes"]),
                "schema_ok": draft.get("schema_check", {}).get("ok"),
                "artifact_type": draft["artifact_type"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
