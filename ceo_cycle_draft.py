"""CEO Agent dry-run report.

Reads current runtime artifacts, asks the local LLM for a short operating
recommendation, and writes report files only. It does not publish anything and
does not modify the existing pipeline.

CEO topic candidates are loaded from templates/ceo_topic_pool.json so the topic
pool can evolve without code changes. The CEO now prefers the configured
weekday_slot when selection_policy.prefer_weekday_slot=true.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List

from agent_core import AgentResult, AgentTask, CEOAgent
from local_llm_router import LocalLLMRouter

REPORT_JSON = os.path.join("agent_runs", "ceo_cycle_report.json")
REPORT_MD = os.path.join("agent_runs", "ceo_cycle_report.md")
TOPIC_GUIDANCE_JSON = os.path.join("agent_runs", "ceo_topic_guidance.json")
CEO_TOPIC_POOL_FILE = os.getenv("CEO_TOPIC_POOL_FILE", os.path.join("templates", "ceo_topic_pool.json"))

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


def _write_markdown(path: str, report: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    topic = report.get("topic_guidance", {})
    lines = [
        "# CEO Cycle Dry-run Report",
        "",
        f"- created_at: {report.get('created_at')}",
        f"- mode: {report.get('mode')}",
        f"- local_model: {report.get('llm', {}).get('model')}",
        f"- instagram_state: {report.get('state', {}).get('instagram_state')}",
        f"- threads_state: {report.get('state', {}).get('threads_state')}",
        f"- recent_topic: {report.get('state', {}).get('recent_topic')}",
        f"- next_topic: {topic.get('topic_title')}",
        f"- emotion_axis: {topic.get('emotion_axis')}",
        f"- weekday_slot: {topic.get('weekday_slot')}",
        f"- selected_by: {topic.get('selected_by')}",
        "",
        "## CEO Recommendation",
        "",
        report.get("ceo_recommendation") or "No recommendation generated.",
        "",
    ]
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


def _select_topic(topics: List[Dict[str, Any]], recent_template_ids: set, pool: Dict[str, Any]) -> tuple[Dict[str, Any], str, str]:
    today_slot = _today_weekday_slot()
    weekday_topics = [topic for topic in topics if topic.get("weekday_slot") == today_slot]

    if _prefer_weekday_slot(pool) and weekday_topics:
        for topic in weekday_topics:
            if _is_allowed_by_history(topic, recent_template_ids):
                return topic, "weekday_slot", today_slot
        return weekday_topics[0], "weekday_slot_history_override", today_slot

    for topic in topics:
        if _is_allowed_by_history(topic, recent_template_ids):
            return topic, "avoid_recent_template_ids", today_slot
    return topics[0], "fallback_first_topic", today_slot


def build_topic_guidance(state: Dict[str, Any]) -> Dict[str, Any]:
    pool = _load_topic_pool()
    history = state.get("script_history", [])
    recent_template_ids = set(_recent_template_ids(history, limit=_history_limit(pool)))
    topics = _topic_candidates(pool)
    chosen, selected_by, today_slot = _select_topic(topics, recent_template_ids, pool)

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
        "series_name": chosen.get("series_name"),
        "episode_role": chosen.get("episode_role"),
        "next_episode_hint": chosen.get("next_episode_hint"),
        "why_now": chosen.get("why_now"),
        "avoid_recent_template_ids": list(recent_template_ids),
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
            "요일별 시리즈 편성표가 있으면 그 편성을 우선합니다."
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
            f"선정 기준: {topic_guidance.get('selected_by')} / 요일 슬롯: {topic_guidance.get('today_weekday_slot')}\n"
            "Instagram은 쿨다운 여부를 우선 확인하고, 제한 중이면 Threads만 발행하세요.\n"
            "성과 데이터가 부족하므로 조회수보다 중복 방지와 발행 안정성을 우선하세요."
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
