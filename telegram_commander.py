"""
telegram_commander.py
─────────────────────
텔레그램으로 받은 자연어 메시지를 로컬 규칙으로 해석하여
SNS 자동화 시스템의 각 기능을 실행하는 모듈.

포워드가 텔레그램에서 보낸 메시지 → 로컬 의도 분석 → 대응 액션 실행
"""

import json
import os
import re
from datetime import datetime

from dotenv import load_dotenv

from codex_command_bridge import enqueue_codex_command

load_dotenv()

STATE_DIR = "agent_runs"
CUSTOM_TOPIC_FILE = os.path.join(STATE_DIR, "custom_topic.json")
PAUSE_FILE = os.path.join(STATE_DIR, "pipeline_paused.flag")

# =====================================================================
# 1. 자연어 의도 파싱
# =====================================================================
def parse_intent(user_message: str) -> dict:
    """Parse Telegram commands locally. External AI APIs are intentionally unused."""
    return parse_intent_locally(user_message)


def parse_intent_locally(user_message: str) -> dict:
    text = user_message.strip()
    normalized = text.lower()
    topic_markers = ["주제", "테마", "내용", "카드뉴스", "포스팅"]

    if any(word in normalized for word in ["도움말", "help", "명령어"]):
        return {"action": "help", "params": {}, "reply": "사용 가능한 명령을 안내합니다."}

    if any(word in normalized for word in ["지금", "바로", "즉시", "run now", "실행"]) and not any(marker in text for marker in topic_markers):
        return {"action": "run_now", "params": {}, "reply": "즉시 실행 요청을 받았습니다."}

    if any(word in normalized for word in ["상태", "status", "어떻게", "돌아가"]):
        return {"action": "status", "params": {}, "reply": "현재 상태를 확인합니다."}

    if any(word in normalized for word in ["멈춰", "중지", "일시중지", "pause"]):
        return {"action": "pause", "params": {}, "reply": "자동 파이프라인을 일시 중지합니다."}

    if any(word in normalized for word in ["재개", "다시 시작", "resume"]):
        return {"action": "resume", "params": {}, "reply": "자동 파이프라인을 재개합니다."}

    if any(word in normalized for word in ["건너뛰", "스킵", "skip"]):
        return {"action": "skip", "params": {}, "reply": "이번 회차를 건너뜁니다."}

    if any(word in normalized for word in ["보고서", "성과", "리포트", "report"]):
        return {"action": "report", "params": {}, "reply": "성과 보고서를 생성합니다."}

    interval_match = re.search(r"(\d+)\s*시간", text)
    if interval_match and any(word in normalized for word in ["마다", "주기", "간격"]):
        return {
            "action": "set_interval",
            "params": {"hours": int(interval_match.group(1))},
            "reply": "포스팅 주기를 변경합니다.",
        }

    tone_keywords = ["강렬", "부드럽", "따뜻", "냉정", "팩폭", "위로", "유머", "진지"]
    if any(keyword in text for keyword in tone_keywords) and any(word in normalized for word in ["톤", "어조", "느낌", "분위기"]):
        return {"action": "set_tone", "params": {"tone": text}, "reply": "다음 콘텐츠 어조를 반영합니다."}

    if any(marker in text for marker in topic_markers) or "올려줘" in normalized:
        topic = text
        for suffix in ["만들어줘", "올려줘", "작성해줘", "해줘"]:
            topic = topic.replace(suffix, "")
        topic = topic.strip()
        return {"action": "set_topic", "params": {"topic": topic or text}, "reply": "다음 콘텐츠 주제를 반영합니다."}

    return {"action": "unknown", "params": {}, "reply": "Codex 작업 큐에 전달합니다."}


# =====================================================================
# 2. 액션 실행기
# =====================================================================
def execute_action(intent: dict) -> str:
    """파싱된 의도에 따라 시스템 액션 실행. 반환값은 텔레그램에 보낼 최종 메시지."""
    action = intent.get("action", "unknown")
    params = intent.get("params", {})
    base_reply = intent.get("reply", "")

    os.makedirs(STATE_DIR, exist_ok=True)

    # ── 즉시 실행 ──────────────────────────────────────────────────
    if action == "run_now":
        from telegram_agent import mark_run_now
        mark_run_now(source="natural_language")
        return f"⚡ {base_reply}\n\n곧 새 카드뉴스 제작을 시작합니다!"

    # ── 주제 고정 ──────────────────────────────────────────────────
    elif action == "set_topic":
        topic = params.get("topic", "").strip()
        if not topic:
            return "❌ 주제를 인식하지 못했습니다. 예: '규율에 관한 포스팅 올려줘'"
        payload = {
            "topic": topic,
            "set_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "used": False
        }
        with open(CUSTOM_TOPIC_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return f"📌 {base_reply}\n\n다음 포스팅 주제: **{topic}**"

    # ── 어조 변경 ──────────────────────────────────────────────────
    elif action == "set_tone":
        tone = params.get("tone", "").strip()
        if not tone:
            return "❌ 어조를 인식하지 못했습니다. 예: '좀 더 강렬하게 올려줘'"
        tone_file = os.path.join(STATE_DIR, "custom_tone.json")
        with open(tone_file, "w", encoding="utf-8") as f:
            json.dump({"tone": tone, "set_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, f, ensure_ascii=False, indent=2)
        return f"🎭 {base_reply}\n\n다음 포스팅 어조: **{tone}**"

    # ── 상태 확인 ──────────────────────────────────────────────────
    elif action == "status":
        from telegram_agent import read_status_text
        status = read_status_text()
        return f"📊 현재 시스템 상태\n\n{status}"

    # ── 일시 중지 ──────────────────────────────────────────────────
    elif action == "pause":
        with open(PAUSE_FILE, "w") as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return f"⏸ {base_reply}\n\n파이프라인이 일시 중지됩니다. 재개하려면 '다시 시작해줘' 라고 보내세요."

    # ── 재개 ────────────────────────────────────────────────────────
    elif action == "resume":
        if os.path.exists(PAUSE_FILE):
            os.remove(PAUSE_FILE)
        return f"▶️ {base_reply}\n\n파이프라인이 재개됩니다!"

    # ── 이번 회차 건너뛰기 ─────────────────────────────────────────
    elif action == "skip":
        skip_file = os.path.join(STATE_DIR, "skip_once.flag")
        with open(skip_file, "w") as f:
            f.write("skip")
        return f"⏭ {base_reply}\n\n이번 회차 포스팅을 건너뜁니다."

    # ── 주기 변경 ──────────────────────────────────────────────────
    elif action == "set_interval":
        hours = params.get("hours")
        try:
            hours = int(hours)
            if hours < 1 or hours > 24:
                raise ValueError
        except Exception:
            return "❌ 올바른 시간을 지정해주세요. (1~24시간 사이)\n예: '6시간마다 올려줘'"
        interval_file = os.path.join(STATE_DIR, "custom_interval.json")
        with open(interval_file, "w", encoding="utf-8") as f:
            json.dump({"hours": hours, "set_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, f, ensure_ascii=False, indent=2)
        return f"⏰ {base_reply}\n\n포스팅 주기가 {hours}시간으로 변경됩니다."

    # ── 보고서 즉시 발송 ────────────────────────────────────────────
    elif action == "report":
        try:
            from agent_monitor import write_human_summary
            write_human_summary()
            from telegram_agent import read_status_text
            status = read_status_text()
            return f"📋 성과 보고서\n\n{status}"
        except Exception as e:
            return f"⚠️ 보고서 생성 중 오류: {e}"

    # ── 도움말 ──────────────────────────────────────────────────────
    elif action == "help":
        return (
            "🤖 마인드팩토리 AI 자동화 명령어 가이드\n\n"
            "자연어로 자유롭게 말씀하시면 됩니다!\n\n"
            "📌 예시 명령어:\n"
            "• '지금 바로 올려줘' → 즉시 포스팅\n"
            "• '규율에 관한 내용으로 올려줘' → 주제 고정\n"
            "• '좀 더 강렬한 어조로 바꿔줘' → 어조 변경\n"
            "• '현재 상태 알려줘' → 상태 확인\n"
            "• '잠깐 멈춰줘' → 일시 중지\n"
            "• '다시 시작해줘' → 재개\n"
            "• '이번 건 건너뛰어줘' → 회차 스킵\n"
            "• '6시간마다 올려줘' → 주기 변경\n"
            "• '성과 보고서 보내줘' → 보고서 발송\n\n"
            "⚡ 슬래시 명령어도 사용 가능:\n"
            "/run_now /status /help"
        )

    # ── 알 수 없음 ──────────────────────────────────────────────────
    else:
        return (
            "명령을 Codex 작업 큐에 전달했습니다.\n"
            "자동 실행 가능한 내부 명령으로 분류되지는 않았지만, Codex가 확인할 수 있게 기록했습니다."
        )


# =====================================================================
# 3. 메인 처리 함수 (telegram_agent.py에서 호출)
# =====================================================================
def handle_natural_language(user_message: str) -> dict:
    """
    자연어 메시지를 받아 의도를 파악하고 액션을 실행.
    반환: {"reply": "텔레그램에 보낼 메시지", "action": "실행된 액션명"}
    """
    print(f"[Commander] 자연어 명령 수신: '{user_message[:80]}'")
    intent = parse_intent(user_message)
    intent.setdefault("params", {})
    intent["params"]["original_message"] = user_message
    action = intent.get("action", "unknown")
    print(f"[Commander] 파싱된 액션: {action} / 파라미터: {intent.get('params', {})}")
    command = enqueue_codex_command(
        user_message,
        source="telegram",
        metadata={"parsed_action": action, "params": intent.get("params", {})},
    )
    reply = execute_action(intent)
    return {"reply": reply, "action": action, "command_id": command["id"]}


# =====================================================================
# 4. 일시중지 여부 확인 (main_orchestrator.py에서 호출)
# =====================================================================
def is_pipeline_paused() -> bool:
    return os.path.exists(PAUSE_FILE)


def get_custom_topic() -> str | None:
    """custom_topic.json에서 미사용 주제를 읽어 반환. 사용 후 used=True로 마킹."""
    if not os.path.exists(CUSTOM_TOPIC_FILE):
        return None
    try:
        with open(CUSTOM_TOPIC_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("used"):
            return None
        # 사용됨으로 마킹
        data["used"] = True
        with open(CUSTOM_TOPIC_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data.get("topic")
    except Exception:
        return None


def get_custom_tone() -> str | None:
    """custom_tone.json에서 어조 설정 읽기"""
    tone_file = os.path.join(STATE_DIR, "custom_tone.json")
    if not os.path.exists(tone_file):
        return None
    try:
        with open(tone_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("tone")
    except Exception:
        return None
