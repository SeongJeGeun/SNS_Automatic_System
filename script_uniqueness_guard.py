import json
import os
from datetime import datetime

HISTORY_FILE = os.path.join("agent_runs", "script_publish_history.json")
SCRIPT_FILE = "script.json"


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        return default


def _write_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _signature(script):
    title = str(script.get("title", "")).strip()
    pages = script.get("pages", [])
    first = ""
    if pages and isinstance(pages[0], dict):
        first = str(pages[0].get("heading", "")).strip()
    return f"{title}|{first}"


def is_duplicate_script(script_path=SCRIPT_FILE, history_path=HISTORY_FILE, recent_limit=8):
    script = _load_json(script_path, {})
    if not script:
        return False
    current = _signature(script)
    history = _load_json(history_path, [])
    recent = history[-recent_limit:] if isinstance(history, list) else []
    for item in recent:
        if isinstance(item, dict) and item.get("signature") == current:
            return True
    return False


def record_script_history(script_path=SCRIPT_FILE, history_path=HISTORY_FILE):
    script = _load_json(script_path, {})
    if not script:
        return False
    history = _load_json(history_path, [])
    if not isinstance(history, list):
        history = []
    entry = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "title": script.get("title"),
        "signature": _signature(script),
        "template_id": (script.get("quality_intent") or {}).get("template_id"),
        "template_title": (script.get("quality_intent") or {}).get("template_title"),
    }
    history.append(entry)
    _write_json(history_path, history[-50:])
    print(f"[Script Guard] recorded script history: {entry.get('title')}")
    return True


def run_generator_until_unique(app, max_attempts=5):
    for attempt in range(1, max_attempts + 1):
        app.run_generator_script(diversify=(attempt > 1))
        if not is_duplicate_script():
            record_script_history()
            return True
        print(f"[Script Guard] duplicate script detected; regenerating {attempt}/{max_attempts}")
    print("[Script Guard] failed to produce unique script within retry limit")
    record_script_history()
    return False
