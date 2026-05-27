import json
import os
from datetime import datetime

import requests
from dotenv import load_dotenv

from codex_command_bridge import (
    enqueue_codex_command,
    mark_result_reported,
    read_unreported_results,
)

load_dotenv(override=True)

STATE_DIR = "agent_runs"
OFFSET_FILE = os.path.join(STATE_DIR, "telegram_offset.txt")
RUN_NOW_FILE = os.path.join(STATE_DIR, "run_now.request")


def is_configured():
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def bot_name():
    return os.getenv("TELEGRAM_BOT_NAME", "MindFactoryBot")


def _api_url(method):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    return f"https://api.telegram.org/bot{token}/{method}"


def send_telegram_message(text):
    if not is_configured():
        print("[Telegram] TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 없어 알림을 생략합니다.")
        return False

    # 알림 켜짐 여부 체크
    if os.getenv("TELEGRAM_NOTIFICATIONS_ENABLED", "true").lower() != "true":
        print("[Telegram] TELEGRAM_NOTIFICATIONS_ENABLED가 false로 설정되어 메시지 발송을 생략합니다.")
        return False

    # 자동 보고서/시작 알림 Mute 여부 체크
    if os.getenv("TELEGRAM_REPORT_MUTED", "false").lower() == "true":
        muted_keywords = ["자동화 보고", "파이프라인 시작", "품질 기준 미달"]
        if any(kw in text for kw in muted_keywords):
            print(f"[Telegram] TELEGRAM_REPORT_MUTED가 true이며, 뮤트 대상 키워드가 포함되어 메시지 발송을 생략합니다. (메시지: {text[:30]}...)")
            return False

    try:
        response = requests.post(
            _api_url("sendMessage"),
            json={
                "chat_id": os.getenv("TELEGRAM_CHAT_ID"),
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        if response.status_code == 200:
            return True
        print(f"[Telegram] 전송 실패 ({response.status_code}): {response.text}")
    except Exception as exc:
        print(f"[Telegram] 전송 중 예외: {exc}")
    return False


def _read_offset():
    try:
        with open(OFFSET_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None


def _write_offset(offset):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(OFFSET_FILE, "w", encoding="utf-8") as f:
        f.write(str(offset))


def get_updates(timeout=0):
    if not is_configured():
        return []

    params = {"timeout": timeout}
    offset = _read_offset()
    if offset is not None:
        params["offset"] = offset

    try:
        response = requests.get(_api_url("getUpdates"), params=params, timeout=timeout + 10)
        data = response.json()
        if not data.get("ok"):
            print(f"[Telegram] 업데이트 조회 실패: {data}")
            return []

        updates = data.get("result", [])
        if updates:
            _write_offset(max(update["update_id"] for update in updates) + 1)
        return updates
    except Exception as exc:
        print(f"[Telegram] 업데이트 조회 중 예외: {exc}")
        return []


def _message_text(update):
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    if str(chat.get("id")) != str(os.getenv("TELEGRAM_CHAT_ID", "")):
        return None
    return (message.get("text") or "").strip()


def read_status_text():
    path = os.path.join(STATE_DIR, "agent_status.md")
    if not os.path.exists(path):
        return "아직 agent_status.md가 없습니다."
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()[:3500]


def mark_run_now(source="telegram"):
    os.makedirs(STATE_DIR, exist_ok=True)
    payload = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
    }
    with open(RUN_NOW_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def consume_run_now():
    if not os.path.exists(RUN_NOW_FILE):
        return False
    try:
        os.remove(RUN_NOW_FILE)
    except OSError:
        pass
    return True


def help_text():
    return (
        f"{bot_name()} 명령어\n"
        "/status - 현재 에이전트 상태 확인\n"
        "/run_now - 대기 시간을 건너뛰고 다음 파이프라인 실행\n"
        "자연어 지시 - Codex 작업 큐로 전달\n"
        "/help - 명령어 보기"
    )


def process_telegram_commands():
    if os.getenv("TELEGRAM_COMMANDS_ENABLED", "true").lower() != "true":
        return {"run_now": False}

    command_result = {"run_now": False}
    send_pending_codex_results()
    for update in get_updates(timeout=0):
        text = _message_text(update)
        if not text:
            continue

        command = text.split()[0].lower()
        if command == "/status":
            send_telegram_message(read_status_text())
        elif command == "/run_now":
            mark_run_now()
            command_result["run_now"] = True
            send_telegram_message("확인했습니다. 대기 시간을 건너뛰고 다음 파이프라인을 실행합니다.")
        elif command == "/help":
            send_telegram_message(help_text())
        elif command in {"/approve", "/reject"}:
            send_telegram_message("승인 단계는 현재 자동 승인으로 처리됩니다. 별도 승인/거절 명령은 사용하지 않습니다.")
        else:
            try:
                from telegram_commander import handle_natural_language
                result = handle_natural_language(text)
                if result.get("action") == "run_now":
                    command_result["run_now"] = True
                reply = result.get("reply") or "명령을 처리했습니다."
                if result.get("command_id"):
                    reply += f"\n\nCodex 작업 ID: {result['command_id']}"
                send_telegram_message(reply)
            except Exception as exc:
                command = enqueue_codex_command(
                    text,
                    source="telegram",
                    metadata={"fallback_reason": str(exc)},
                )
                send_telegram_message(
                    "명령을 Codex 작업 큐에 전달했습니다.\n"
                    f"작업 ID: {command['id']}\n"
                    "처리 결과는 완료 후 텔레그램으로 보고하도록 기록했습니다."
                )

    if consume_run_now():
        command_result["run_now"] = True
    return command_result


def send_pending_codex_results():
    for result in read_unreported_results():
        command_id = result.get("id", "unknown")
        message = (
            "Codex 작업 결과\n\n"
            f"작업 ID: {command_id}\n"
            f"상태: {result.get('status', 'done')}\n\n"
            f"{result.get('result', '')}"
        )
        if send_telegram_message(message):
            mark_result_reported(command_id)


def request_telegram_approval(title, detail, timeout_seconds=None):
    """Approval policy requested by the user: always approve without waiting."""
    if not is_configured():
        print("[Telegram] 텔레그램 미설정 상태라 승인 요청을 자동 승인으로 처리합니다.")
        return True

    send_telegram_message(
        f"자동 승인 처리: {title}\n\n"
        f"{detail}\n\n"
        "현재 설정은 텔레그램 승인 대기 없이 계속 진행합니다."
    )
    return True
