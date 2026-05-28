"""CEO Agent dry-run report.

Reads current runtime artifacts, asks the local LLM for a short operating
recommendation, and writes report files only. It does not publish anything and
does not modify the existing pipeline.

CEO topic candidates are loaded from templates/ceo_topic_pool.json so the topic
pool can evolve without code changes. The CEO prefers the configured
weekday_slot when selection_policy.prefer_weekday_slot=true and now also uses
recent decision_memory.jsonl events to avoid repeating weak patterns.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Set, Tuple

from agent_core import AgentResult, AgentTask, CEOAgent
from local_llm_router import LocalLLMRouter

REPORT_JSON = os.path.join("agent_runs", "ceo_cycle_report.json")
REPORT_MD = os.path.join("agent_runs", "ceo_cycle_report.md")
TOPIC_GUIDANCE_JSON = os.path.join("agent_runs", "ceo_topic_guidance.json")
CEO_TOPIC_POOL_FILE = os.getenv("CEO_TOPIC_POOL_FILE", os.path.join("templates", "ceo_topic_pool.json"))
DECISION_MEMORY_FILE = os.getenv("DECISION_MEMORY_FILE", os.path.join("agent_runs", "decision_memory.jsonl"))

FALLBACK_TOPIC_POOL = {
    "version": 0,
    "name": "fallback_ceo_topic_pool",
    "selection_policy": {
        "recent_history_limit": 5,
        "mode": "avoid_recent_template_ids_first",
        "prefer_weekday_slot": True,
    },
    "topics": [
        {
            "topic_key": "comparison_anxiety",
            "topic_title": "비교 불안에서 벗어나는 작은 루틴",
            "emotion_axis": "비교/불안",
            "weekday_slot": "mon",
            "avoid_after": ["comparison_detox"],
            "why_now": "비교와 뒤처짐 불안을 작은 루틴으로 전환",
        },
        {
            "topic_key": "execution_barrier",
            "topic_title": "시작 장벽을 낮추는 10분 실행법",
            "emotion_axis": "미루기/실행",
            "weekday_slot": "wed",
            "avoid_after": ["small_routine_recovery"],
            "why_now": "미루기와 자책을 시작 설계 문제로 재정의",
        },
    ],
}

WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _load_json(path: str, default: Any):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _md_value(value: Any, fallback: str = "없음") -> str:
    if value is None:
        return fallback
    if isinstance(value, bool):
        return "예" if value else "아니오"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value) if value else fallback
    text = str(value).strip()
    return text or fallback


def _status_icon(value: Any) -> str:
    text = str(value or "").lower()
    if text in {"active", "success", "ok", "true"}:
        return "정상"
    if text in {"cooldown", "waiting"}:
        return "대기"
    if text in {"failed", "error", "false"}:
        return "주의"
    return "확인 필요"


def _write_markdown(path: str, report: Dict[str, Any]) -> None:
    """Write a human-readable CEO report for Telegram/Obsidian review.

    This report is intentionally file-only. It does not send Telegram messages
    and does not mutate the publish pipeline.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    state = report.get("state", {}) if isinstance(report.get("state"), dict) else {}
    topic = report.get("topic_guidance", {}) if isinstance(report.get("topic_guidance"), dict) else {}
    memory = topic.get("memory_signal", {}) if isinstance(topic.get("memory_signal"), dict) else {}
    llm = report.get("llm", {}) if isinstance(report.get("llm"), dict) else {}
    worker_results = report.get("worker_results", {}) if isinstance(report.get("worker_results"), dict) else {}

    instagram_state = state.get("instagram_state")
    threads_state = state.get("threads_state")
    recommendation = report.get("ceo_recommendation") or "로컬 LLM 추천이 생성되지 않았습니다. fallback 운영 지시를 사용하세요."

    lines = [
        "# CEO 운영 보고서",
        "",
        "## 1. 운영 요약",
        "",
        f"- 생성 시각: {_md_value(report.get('created_at'))}",
        f"- 모드: {_md_value(report.get('mode'))}",
        f"- 로컬 모델: {_md_value(llm.get('model'))}",
        f"- 오늘 요일 슬롯: {_md_value(state.get('today_weekday_slot'))}",
        f"- 최근 주제: {_md_value(state.get('recent_topic'))}",
        f"- Decision Memory 기록 수: {_md_value(state.get('decision_memory_count'), '0')}",
        "",
        "## 2. 플랫폼 상태",
        "",
        "| 플랫폼 | 상태 | 판단 |",
        "|---|---:|---|",
        f"| Instagram | {_md_value(instagram_state)} | {_status_icon(instagram_state)} |",
        f"| Threads | {_md_value(threads_state)} | {_status_icon(threads_state)} |",
        "",
        "## 3. 다음 회차 선택 주제",
        "",
        f"- 주제: {_md_value(topic.get('topic_title'))}",
        f"- topic_key: `{_md_value(topic.get('topic_key'))}`",
        f"- 감정 축: {_md_value(topic.get('emotion_axis'))}",
        f"- 시리즈: {_md_value(topic.get('series_name'))}",
        f"- 이번 편 역할: {_md_value(topic.get('episode_role'))}",
        f"- 다음 편 예고: {_md_value(topic.get('next_episode_hint'))}",
        f"- 선정 기준: {_md_value(topic.get('selected_by'))}",
        f"- 메모리 위험도: {_md_value(topic.get('memory_risk'), '0')}",
        f"- 선정 이유: {_md_value(topic.get('why_now'))}",
        "",
        "## 4. Decision Memory 신호",
        "",
        f"- 최근 template_id: {_md_value(memory.get('recent_template_ids'))}",
        f"- 최근 감정 축: {_md_value(memory.get('recent_emotion_axes'))}",
        f"- 약한 template_id: {_md_value(memory.get('weak_template_ids'))}",
        f"- 약한 감정 축: {_md_value(memory.get('weak_emotion_axes'))}",
        f"- 정합성 실패 주제: {_md_value(memory.get('alignment_failed_topics'))}",
        "",
        "## 5. 다음 실행 지시",
        "",
        "1. Instagram이 cooldown이면 컨테이너 생성 없이 선제 skip합니다.",
        "2. Threads는 텍스트 중심으로 계속 발행합니다.",
        "3. 최근 template_id와 감정 축 반복을 피합니다.",
        "4. script alignment가 실패하면 generator 재시도 후 감사 로그를 남깁니다.",
        "5. 발행 후 decision_memory.jsonl에 결과를 누적합니다.",
        "",
        "## 6. CEO 추천 문장",
        "",
        recommendation,
        "",
        "## 7. Worker 상태",
        "",
        "| Worker | OK | 요약 |",
        "|---|---:|---|",
    ]

    if worker_results:
        for name, result in worker_results.items():
            if not isinstance(result, dict):
                continue
            lines.append(f"| {name} | {_md_value(result.get('ok'))} | {_md_value(result.get('summary'))} |")
    else:
        lines.append("| 없음 | - | worker 결과 없음 |")

    lines.extend([
        "",
        "---",
        "",
        "이 보고서는 CEO dry-run 결과입니다. Telegram 자동 발송은 하지 않습니다.",
        "",
    ])

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _load_topic_pool() -> Dict[str, Any]:
    pool = _load_json(CEO_TOPIC_POOL_FILE, None)
    if isinstance(pool, dict) and isinstance(pool.get("topics"), list) and pool["topics"]:
        return pool
    print(f"[CEO Draft] topic pool missing or invalid, fallback used: {CEO_TOPIC_POOL_FILE}")
    return FALLBACK_TOPIC_POOL


def _topic_candidates(pool: Dict[str, Any]) -> List[Dict[str, Any]]:
    topics = pool.get("topics") if isinstance(pool, dict) else []
    return topics if isinstance(topics, list) and topics else FALLBACK_TOPIC_POOL["topics"]


def _recent_template_ids(history: Any, limit: int = 5) -> List[str]:
    if not isinstance(history, list):
        return []
    result = []
    for item in history[-limit:]:
        if isinstance(item, dict):
            template_id = item.get("template_id")
            if template_id:
                result.append(str(template_id))
    return result


def _load_recent_decisions(limit: int = 10) -> List[Dict[str, Any]]:
    try:
        from decision_memory import load_recent_decisions
        return load_recent_decisions(limit=limit, memory_file=DECISION_MEMORY_FILE)
    except Exception:
        pass

    if not os.path.exists(DECISION_MEMORY_FILE):
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with open(DECISION_MEMORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return rows[-limit:]


def _decision_memory_signal(decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    recent_template_ids: List[str] = []
    recent_emotion_axes: List[str] = []
    weak_template_ids: Set[str] = set()
    weak_emotion_axes: Set[str] = set()
    alignment_failed_topics: List[str] = []

    for event in decisions:
        topic = event.get("topic") if isinstance(event, dict) else {}
        quality = event.get("quality") if isinstance(event, dict) else {}
        guards = event.get("guards") if isinstance(event, dict) else {}
        if not isinstance(topic, dict):
            topic = {}
        if not isinstance(quality, dict):
            quality = {}
        if not isinstance(guards, dict):
            guards = {}

        template_id = topic.get("template_id")
        emotion_axis = topic.get("ceo_emotion_axis")
        if template_id:
            recent_template_ids.append(str(template_id))
        if emotion_axis:
            recent_emotion_axes.append(str(emotion_axis))

        alignment = guards.get("script_alignment") if isinstance(guards.get("script_alignment"), dict) else {}
        quality_ok = quality.get("ok")
        if alignment.get("ok") is False or quality_ok is False:
            if template_id:
                weak_template_ids.add(str(template_id))
            if emotion_axis:
                weak_emotion_axes.add(str(emotion_axis))
            if topic.get("title"):
                alignment_failed_topics.append(str(topic.get("title")))

    return {
        "recent_template_ids": recent_template_ids[-5:],
        "recent_emotion_axes": recent_emotion_axes[-5:],
        "weak_template_ids": sorted(weak_template_ids),
        "weak_emotion_axes": sorted(weak_emotion_axes),
        "alignment_failed_topics": alignment_failed_topics[-3:],
        "decision_count": len(decisions),
    }


def _history_limit(pool: Dict[str, Any]) -> int:
    policy = pool.get("selection_policy") if isinstance(pool, dict) else {}
    if not isinstance(policy, dict):
        return 5
    try:
        return int(policy.get("recent_history_limit", 5))
    except Exception:
        return 5


def _prefer_weekday_slot(pool: Dict[str, Any]) -> bool:
    policy = pool.get("selection_policy") if isinstance(pool, dict) else {}
    if not isinstance(policy, dict):
        return False
    return str(policy.get("prefer_weekday_slot", "false")).lower() == "true"


def _today_weekday_slot() -> str:
    override = os.getenv("CEO_WEEKDAY_SLOT", "").strip().lower()
    if override in WEEKDAY_KEYS:
        return override
    return WEEKDAY_KEYS[datetime.now().weekday()]


def _is_allowed_by_history(topic: Dict[str, Any], recent_template_ids: set) -> bool:
    return not any(blocked in recent_template_ids for blocked in topic.get("avoid_after", []))


def _memory_risk(topic: Dict[str, Any], memory_signal: Dict[str, Any]) -> int:
    risk = 0
    avoid_after = set(str(x) for x in topic.get("avoid_after", []))
    recent_templates = set(memory_signal.get("recent_template_ids", []))
    weak_templates = set(memory_signal.get("weak_template_ids", []))
    recent_emotions = set(memory_signal.get("recent_emotion_axes", []))
    weak_emotions = set(memory_signal.get("weak_emotion_axes", []))
    emotion_axis = str(topic.get("emotion_axis", ""))

    if avoid_after & recent_templates:
        risk += 5
    if avoid_after & weak_templates:
        risk += 4
    if emotion_axis and emotion_axis in weak_emotions:
        risk += 3
    if emotion_axis and emotion_axis in recent_emotions:
        risk += 1
    return risk


def _lowest_risk_topic(topics: List[Dict[str, Any]], memory_signal: Dict[str, Any]) -> Dict[str, Any]:
    return sorted(topics, key=lambda item: _memory_risk(item, memory_signal))[0]


def _select_topic(
    topics: List[Dict[str, Any]],
    recent_template_ids: set,
    pool: Dict[str, Any],
    memory_signal: Dict[str, Any],
) -> Tuple[Dict[str, Any], str, str, int]:
    today_slot = _today_weekday_slot()
    weekday_topics = [topic for topic in topics if topic.get("weekday_slot") == today_slot]

    if _prefer_weekday_slot(pool) and weekday_topics:
        safe_weekday_topics = [
            topic for topic in weekday_topics
            if _is_allowed_by_history(topic, recent_template_ids) and _memory_risk(topic, memory_signal) < 5
        ]
        if safe_weekday_topics:
            chosen = _lowest_risk_topic(safe_weekday_topics, memory_signal)
            return chosen, "weekday_slot_memory_safe", today_slot, _memory_risk(chosen, memory_signal)
        chosen = _lowest_risk_topic(weekday_topics, memory_signal)
        return chosen, "weekday_slot_memory_override", today_slot, _memory_risk(chosen, memory_signal)

    safe_topics = [
        topic for topic in topics
        if _is_allowed_by_history(topic, recent_template_ids) and _memory_risk(topic, memory_signal) < 5
    ]
    if safe_topics:
        chosen = _lowest_risk_topic(safe_topics, memory_signal)
        return chosen, "decision_memory_safe_rotation", today_slot, _memory_risk(chosen, memory_signal)

    chosen = _lowest_risk_topic(topics, memory_signal)
    return chosen, "decision_memory_lowest_risk_fallback", today_slot, _memory_risk(chosen, memory_signal)


def build_topic_guidance(state: Dict[str, Any]) -> Dict[str, Any]:
    pool = _load_topic_pool()
    history = state.get("script_history", [])
    memory_signal = state.get("decision_memory_signal") or _decision_memory_signal(_load_recent_decisions(limit=10))
    recent_from_history = set(_recent_template_ids(history, limit=_history_limit(pool)))
    recent_from_memory = set(memory_signal.get("recent_template_ids", []))
    recent_template_ids = recent_from_history | recent_from_memory
    topics = _topic_candidates(pool)
    chosen, selected_by, today_slot, memory_risk = _select_topic(topics, recent_template_ids, pool, memory_signal)

    return {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "ceo_cycle_draft",
        "mode": "advisory",
        "topic_pool_file": CEO_TOPIC_POOL_FILE,
        "topic_pool_name": pool.get("name"),
        "topic_key": chosen["topic_key"],
        "topic_title": chosen["topic_title"],
        "emotion_axis": chosen["emotion_axis"],
        "weekday_slot": chosen.get("weekday_slot"),
        "today_weekday_slot": today_slot,
        "selected_by": selected_by,
        "memory_risk": memory_risk,
        "memory_signal": memory_signal,
        "series_name": chosen.get("series_name"),
        "episode_role": chosen.get("episode_role"),
        "next_episode_hint": chosen.get("next_episode_hint"),
        "why_now": chosen.get("why_now"),
        "avoid_recent_template_ids": sorted(recent_template_ids),
        "notes": "Advisory only. Generator reads this file and falls back if unavailable.",
    }


def collect_runtime_state() -> Dict[str, Any]:
    agent_status = _load_json(os.path.join("agent_runs", "agent_status.json"), {})
    cooldown = _load_json(os.path.join("agent_runs", "instagram_publish_cooldown.json"), {})
    script = _load_json("script.json", {})
    strategy = _load_json("content_strategy.json", {})
    audience = _load_json("audience_insight.json", {})
    history = _load_json(os.path.join("agent_runs", "script_publish_history.json"), [])
    performance = _load_json(os.path.join("shared", "performance_log.json"), [])
    decisions = _load_recent_decisions(limit=10)
    memory_signal = _decision_memory_signal(decisions)

    instagram_state = "cooldown" if cooldown else "unknown"
    threads_state = "active"

    recent_topic = script.get("title")
    if isinstance(history, list) and history:
        recent_topic = history[-1].get("title") or recent_topic

    return {
        "agent_status": agent_status,
        "instagram_cooldown": cooldown,
        "script_title": script.get("title"),
        "strategy_mode": strategy.get("strategy_mode") or strategy.get("mode"),
        "audience_summary": audience.get("summary") or audience.get("core_pain") or audience.get("pain"),
        "recent_topic": recent_topic,
        "recent_history_count": len(history) if isinstance(history, list) else 0,
        "script_history": history[-10:] if isinstance(history, list) else [],
        "performance_count": len(performance) if isinstance(performance, list) else 0,
        "decision_memory_count": len(decisions),
        "decision_memory_signal": memory_signal,
        "instagram_state": instagram_state,
        "threads_state": threads_state,
        "today_weekday_slot": _today_weekday_slot(),
    }


class StatusAnalystWorker:
    name = "status_analyst"

    def run(self, task: AgentTask) -> AgentResult:
        state = collect_runtime_state()
        return AgentResult(
            agent_name=self.name,
            ok=True,
            summary="runtime artifacts collected",
            data=state,
        )


class CEORecommendationWorker:
    name = "ceo_recommender"

    def run(self, task: AgentTask) -> AgentResult:
        state = task.context.get("status_analyst_result") or collect_runtime_state()
        topic_guidance = build_topic_guidance(state)
        router = LocalLLMRouter()
        system = (
            "당신은 1인 AI 기업 운영 CEO 에이전트입니다. "
            "로컬 LLM만 사용하며, SNS 자동화 시스템의 다음 회차 전략을 짧고 실행 가능하게 제안합니다. "
            "중복 콘텐츠를 피하고 Instagram 쿨다운 중에는 Threads 중심으로 운영합니다. "
            "요일별 시리즈 편성표와 decision_memory의 실패/반복 신호를 함께 반영합니다."
        )
        user = (
            "현재 런타임 상태와 다음 주제 후보를 보고 다음 회차 운영 판단을 내려주세요.\n"
            "반드시 5줄 이내 한국어로 작성하세요.\n\n"
            f"STATE_JSON:\n{json.dumps(state, ensure_ascii=False, indent=2)}\n\n"
            f"TOPIC_GUIDANCE:\n{json.dumps(topic_guidance, ensure_ascii=False, indent=2)}"
        )
        result = router.chat(system=system, user=user, task_type="ceo_dry_run") if hasattr(router, "chat") else None
        if result and result.ok:
            return AgentResult(
                agent_name=self.name,
                ok=True,
                summary="local LLM recommendation generated",
                data={"recommendation": result.content, "llm": result.__dict__, "topic_guidance": topic_guidance},
            )
        fallback = (
            f"다음 회차는 '{topic_guidance['topic_title']}' 주제로 전환하세요.\n"
            f"선정 기준: {topic_guidance.get('selected_by')} / 요일 슬롯: {topic_guidance.get('today_weekday_slot')} / 메모리 위험도: {topic_guidance.get('memory_risk')}\n"
            "Instagram은 쿨다운 여부를 우선 확인하고, 제한 중이면 Threads만 발행하세요.\n"
            "최근 decision_memory의 실패·반복 패턴을 피하면서 발행 안정성을 우선하세요."
        )
        return AgentResult(
            agent_name=self.name,
            ok=False,
            summary="local LLM failed; fallback recommendation used",
            data={"recommendation": fallback, "error": result.error if result else "router unavailable", "topic_guidance": topic_guidance},
        )


def main() -> Dict[str, Any]:
    ceo = CEOAgent([StatusAnalystWorker(), CEORecommendationWorker()])
    results = ceo.run_plan(
        goal="SNS 자동화 시스템의 다음 회차 운영 판단",
        worker_order=["status_analyst", "ceo_recommender"],
        context={},
    )
    state = results["status_analyst"].data
    reco = results["ceo_recommender"].data
    topic_guidance = reco.get("topic_guidance") or build_topic_guidance(state)
    report = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "dry_run",
        "state": state,
        "topic_guidance": topic_guidance,
        "ceo_recommendation": reco.get("recommendation"),
        "llm": reco.get("llm") or {"provider": os.getenv("LOCAL_LLM_PROVIDER", "ollama"), "model": os.getenv("LOCAL_LLM_MODEL", "qwen3:30b")},
        "worker_results": {
            name: {"ok": res.ok, "summary": res.summary}
            for name, res in results.items()
        },
    }
    _write_json(REPORT_JSON, report)
    _write_json(TOPIC_GUIDANCE_JSON, topic_guidance)
    _write_markdown(REPORT_MD, report)
    print(f"[CEO Draft] saved: {REPORT_JSON}")
    print(f"[CEO Draft] saved: {REPORT_MD}")
    print(f"[CEO Draft] saved: {TOPIC_GUIDANCE_JSON}")
    return report


if __name__ == "__main__":
    main()
