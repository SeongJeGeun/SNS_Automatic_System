import json
import os
from datetime import datetime


STATE_DIR = "agent_runs"
QUEUE_FILE = os.path.join(STATE_DIR, "codex_command_queue.jsonl")
RESULT_FILE = os.path.join(STATE_DIR, "codex_command_results.jsonl")
REPORTED_RESULTS_FILE = os.path.join(STATE_DIR, "codex_reported_results.json")
REQUESTS_MD = "codex_command_requests.md"


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _command_id():
    return datetime.now().strftime("cx-%Y%m%d%H%M%S%f")


def enqueue_codex_command(command_text, source="telegram", metadata=None):
    os.makedirs(STATE_DIR, exist_ok=True)
    command = {
        "id": _command_id(),
        "created_at": _now(),
        "source": source,
        "status": "queued",
        "command": command_text.strip(),
        "metadata": metadata or {},
    }

    with open(QUEUE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(command, ensure_ascii=False) + "\n")

    _rewrite_requests_markdown()
    return command


def record_codex_result(command_id, result_text, status="done"):
    os.makedirs(STATE_DIR, exist_ok=True)
    result = {
        "id": command_id,
        "finished_at": _now(),
        "status": status,
        "result": result_text,
    }
    with open(RESULT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")
    _rewrite_requests_markdown()
    return result


def read_queued_commands(limit=20):
    if not os.path.exists(QUEUE_FILE):
        return []
    commands = []
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                commands.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return commands[-limit:]


def _read_results():
    if not os.path.exists(RESULT_FILE):
        return {}
    results = {}
    with open(RESULT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            results[item.get("id")] = item
    return results


def read_unreported_results():
    results = _read_results()
    if not results:
        return []

    try:
        with open(REPORTED_RESULTS_FILE, "r", encoding="utf-8") as f:
            reported_ids = set(json.load(f))
    except Exception:
        reported_ids = set()

    pending = [item for command_id, item in results.items() if command_id not in reported_ids]
    pending.sort(key=lambda item: item.get("finished_at", ""))
    return pending


def mark_result_reported(command_id):
    os.makedirs(STATE_DIR, exist_ok=True)
    try:
        with open(REPORTED_RESULTS_FILE, "r", encoding="utf-8") as f:
            reported_ids = set(json.load(f))
    except Exception:
        reported_ids = set()
    reported_ids.add(command_id)
    with open(REPORTED_RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(reported_ids), f, ensure_ascii=False, indent=2)


def _rewrite_requests_markdown():
    commands = read_queued_commands(limit=50)
    results = _read_results()
    lines = [
        "# Codex Command Requests",
        "",
        "텔레그램/웹 대시보드로 들어온 사용자 지시를 Codex가 확인하고 수행하기 위한 작업 큐입니다.",
        "완료 후 결과는 텔레그램/웹 대시보드로 보고하고, 필요하면 `record_codex_result()`로 기록합니다.",
        "",
    ]

    if not commands:
        lines.append("현재 대기 중인 명령이 없습니다.")
    else:
        for command in commands:
            result = results.get(command["id"])
            status = result.get("status") if result else command.get("status", "queued")
            lines.extend(
                [
                    f"## {command['id']} [{status}]",
                    f"- 시간: {command.get('created_at')}",
                    f"- 출처: {command.get('source')}",
                    f"- 명령: {command.get('command')}",
                ]
            )
            if result:
                lines.append(f"- 결과: {result.get('result')}")
            lines.append("")

    with open(REQUESTS_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
