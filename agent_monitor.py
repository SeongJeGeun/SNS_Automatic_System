import json
import os
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timedelta


MONITOR_DIR = "agent_runs"
STATUS_FILE = "agent_status.json"
EVENT_LOG = "agent_events.jsonl"


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_monitor_dir():
    os.makedirs(MONITOR_DIR, exist_ok=True)


def load_status():
    ensure_monitor_dir()
    path = os.path.join(MONITOR_DIR, STATUS_FILE)
    if not os.path.exists(path):
        return {"agents": {}, "pipeline": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"agents": {}, "pipeline": {}}


def save_status(status):
    ensure_monitor_dir()
    path = os.path.join(MONITOR_DIR, STATUS_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def append_event(event):
    ensure_monitor_dir()
    event = {"time": now_str(), **event}
    path = os.path.join(MONITOR_DIR, EVENT_LOG)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def update_pipeline(**fields):
    status = load_status()
    status.setdefault("pipeline", {}).update(fields)
    status["pipeline"]["updated_at"] = now_str()
    save_status(status)


def heartbeat(note=None):
    status = load_status()
    status.setdefault("pipeline", {})["heartbeat_at"] = now_str()
    if note:
        status["pipeline"]["heartbeat_note"] = note
    save_status(status)
    append_event({"agent": "Orchestrator", "event": "heartbeat", "note": note})


@contextmanager
def agent_step(agent_name, detail=None):
    ensure_monitor_dir()
    started = time.time()
    status = load_status()
    agent = status.setdefault("agents", {}).setdefault(agent_name, {})
    agent.update({
        "state": "running",
        "started_at": now_str(),
        "detail": detail,
        "error": None,
    })
    save_status(status)
    append_event({"agent": agent_name, "event": "started", "detail": detail})

    try:
        yield
    except Exception as exc:
        elapsed = round(time.time() - started, 2)
        status = load_status()
        agent = status.setdefault("agents", {}).setdefault(agent_name, {})
        agent.update({
            "state": "failed",
            "finished_at": now_str(),
            "elapsed_seconds": elapsed,
            "error": str(exc),
        })
        save_status(status)
        append_event({
            "agent": agent_name,
            "event": "failed",
            "elapsed_seconds": elapsed,
            "error": str(exc),
            "traceback": traceback.format_exc()[-4000:],
        })
        raise
    else:
        elapsed = round(time.time() - started, 2)
        status = load_status()
        agent = status.setdefault("agents", {}).setdefault(agent_name, {})
        agent.update({
            "state": "success",
            "finished_at": now_str(),
            "elapsed_seconds": elapsed,
            "error": None,
        })
        save_status(status)
        append_event({
            "agent": agent_name,
            "event": "success",
            "elapsed_seconds": elapsed,
        })


def write_human_summary():
    status = load_status()
    lines = ["# Agent Status", ""]
    pipeline = status.get("pipeline", {})
    for key in [
        "state",
        "last_run_started_at",
        "last_run_finished_at",
        "next_run_at",
        "heartbeat_at",
        "last_result",
    ]:
        if pipeline.get(key):
            lines.append(f"- {key}: {pipeline[key]}")

    lines.extend(["", "## Agents"])
    for agent_name, agent in sorted(status.get("agents", {}).items()):
        lines.append(
            f"- {agent_name}: {agent.get('state')} "
            f"(started: {agent.get('started_at')}, finished: {agent.get('finished_at')}, "
            f"elapsed: {agent.get('elapsed_seconds')})"
        )
        if agent.get("error"):
            lines.append(f"  error: {agent['error']}")

    path = os.path.join(MONITOR_DIR, "agent_status.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def next_run_time(interval_seconds):
    return (datetime.now() + timedelta(seconds=interval_seconds)).strftime("%Y-%m-%d %H:%M:%S")
