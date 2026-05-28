"""CEO Agent dry-run report.

Reads current runtime artifacts, asks the local LLM for a short operating
recommendation, and writes report files only. It does not publish anything and
does not modify the existing pipeline.

Batch step 2 adds a lightweight topic guidance artifact that generator.py may
optionally read in a later stage.
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

TOPIC_POOL = [
    {
        "topic_key": "comparison_anxiety",
        "topic_title": "비교 불안에서 벗어나는 작은 루틴",
        "emotion_axis": "비교/불안",
        "avoid_after": ["comparison_detox"],
    },
    {
        "topic_key": "burnout_recovery",
        "topic_title": "번아웃 직전의 하루를 회복하는 10분",
        "emotion_axis": "번아웃/회복",
        "avoid_after": ["burnout_reset"],
    },
    {
        "topic_key": "execution_barrier",
        "topic_title": "시작 장벽을 낮추는 10분 실행법",
        "emotion_axis": "미루기/실행",
        "avoid_after": ["small_routine_recovery"],
    },
    {
        "topic_key": "lonely_night_reset",
        "topic_title": "혼자 무너지는 밤을 넘기는 방법",
        "emotion_axis": "외로움/자기회복",
        "avoid_after": [],
    },
]


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
        "",
        "## CEO Recommendation",
        "",
        report.get("ceo_recommendation") or "No recommendation generated.",
        "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


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


def build_topic_guidance(state: Dict[str, Any]) -> Dict[str, Any]:
    history = state.get("script_history", [])
    recent_template_ids = set(_recent_template_ids(history, limit=5))

    for item in TOPIC_POOL:
        if not any(blocked in recent_template_ids for blocked in item.get("avoid_after", [])):
            chosen = item
            break
    else:
        chosen = TOPIC_POOL[0]

    return {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "ceo_cycle_draft",
        "mode": "advisory",
        "topic_key": chosen["topic_key"],
        "topic_title": chosen["topic_title"],
        "emotion_axis": chosen["emotion_axis"],
        "avoid_recent_template_ids": list(recent_template_ids),
        "notes": "Advisory only. Generator may read this file in a later stage.",
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
            "중복 콘텐츠를 피하고 Instagram 쿨다운 중에는 Threads 중심으로 운영합니다."
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
