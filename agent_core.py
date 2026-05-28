"""Minimal vertical CEO/worker agent primitives.

This is a dry-run scaffold. It does not change publishing behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol


@dataclass
class AgentTask:
    goal: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    agent_name: str
    ok: bool
    summary: str
    data: Dict[str, Any] = field(default_factory=dict)


class WorkerAgent(Protocol):
    name: str

    def run(self, task: AgentTask) -> AgentResult:
        ...


class CEOAgent:
    """Centralized CEO dispatcher for low-compute vertical orchestration."""

    def __init__(self, workers: List[WorkerAgent]):
        self.workers = {worker.name: worker for worker in workers}

    def dispatch(self, worker_name: str, task: AgentTask) -> AgentResult:
        worker = self.workers.get(worker_name)
        if not worker:
            return AgentResult(
                agent_name="ceo",
                ok=False,
                summary=f"worker not found: {worker_name}",
            )
        print(f"[CEO] dispatch -> {worker_name}: {task.goal}")
        return worker.run(task)

    def run_plan(self, goal: str, worker_order: List[str], context: Dict[str, Any]) -> Dict[str, AgentResult]:
        results: Dict[str, AgentResult] = {}
        shared_context = dict(context)
        shared_context["goal"] = goal

        for worker_name in worker_order:
            result = self.dispatch(
                worker_name,
                AgentTask(goal=goal, context={**shared_context, "previous_results": results}),
            )
            results[worker_name] = result
            shared_context[f"{worker_name}_result"] = result.data

        return results
