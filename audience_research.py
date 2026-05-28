"""Audience research module: generates audience insight and attaches advisory signals.

Downstream consumer note (Batch 30)
-------------------------------------
After ``create_audience_insight()`` returns, the returned dict contains
``strategy_signals`` — an advisory-only dict built by
``strategy_signal_builder.build_strategy_signals()``.  Downstream strategy
or script modules may **optionally** read these signals and adapt their
behavior without changing publish or blocking behavior.

Example (read-only, non-blocking)::

    from example_strategy_consumer import adapt_strategy_from_signals

    insight = create_audience_insight()
    adapted_config = adapt_strategy_from_signals(insight.get("strategy_signals"))
    # adapted_config is advisory only — never passed to upload_carousel,
    # scheduler, or Telegram modules.

If ``strategy_signals`` is absent or ``available=False``, the consumer
returns conservative defaults automatically.

TODO (Batch 31+): Wire ``adapt_strategy_from_signals`` into the real
    strategy/script generation stage once prompt-rule ownership is approved.
"""
import json
import os
import re
import time
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()


PAIN_SIGNAL_QUERIES = [
    "요즘 20대 30대 직장인 번아웃 무기력 불안 고민",
    "요즘 사람들이 힘들어하는 이유 자기계발 동기부여 피로감",
    "인스타그램 자기계발 카드뉴스 저장 많이 되는 고민 주제",
    "MZ 세대 돈 커리어 관계 자존감 불안 루틴 고민",
]
PAIN_KEYWORD_CANDIDATES = [
    "번아웃",
    "무기력",
    "불안",
    "자책",
    "비교",
    "자존감",
    "커리어",
    "관계",
    "돈",
    "루틴",
    "피로감",
    "압박",
    "회피",
    "고립",
    "막막함",
]
TOPIC_KEYWORD_CANDIDATES = [
    "번아웃",
    "무기력",
    "자기계발 피로감",
    "커리어 불안",
    "자존감",
    "관계 피로",
    "돈 걱정",
    "루틴 붕괴",
    "저장형 카드뉴스",
    "실천 루틴",
]

DEFAULT_AUDIENCE_INSIGHT = {
    "audience_state": "성과 압박은 큰데 체력과 집중력은 바닥난 상태. 해야 할 일은 알지만 시작하지 못해 자책이 누적된다.",
    "core_pains": [
        "열심히 살아야 한다는 압박과 실제 행동 사이의 간극",
        "휴식해도 회복되지 않는 번아웃과 무기력",
        "남들과 비교하며 뒤처진다는 불안",
        "루틴을 만들고 싶지만 금방 무너지는 자기불신",
    ],
    "emotional_keywords": ["불안", "무기력", "자책", "비교", "번아웃", "막막함"],
    "needed_message": "괜찮다는 말만 반복하지 말고, 지금 무너진 이유를 정확히 짚어준 뒤 작게 다시 움직일 수 있는 행동을 제시해야 한다.",
    "story_angle": "공감으로 시작해 자책을 멈추게 하고, 문제를 의지 부족이 아니라 시스템 부재로 재정의한 뒤, 오늘 당장 가능한 작은 규율로 연결한다.",
    "content_principles": [
        "첫 장은 독자가 자기 이야기라고 느껴야 한다.",
        "중간 장은 고통의 원인을 차갑게 정리하되 사람을 비난하지 않는다.",
        "마지막 장은 저장하고 다시 볼 수 있는 구체적 행동으로 끝낸다.",
        "위로와 동기부여의 비율은 4:6으로 둔다.",
    ],
}

DEFAULT_LOCAL_AUDIENCE_MODEL = "gemma4:26b"
DEFAULT_LOCAL_AUDIENCE_TIMEOUT_SECONDS = "30"
LOCAL_AUDIENCE_SUCCESS_STATUS = "local_obsidian_ollama_json_parsed"


def read_recent_local_trends(vault_path="obsidian_vault", limit=4):
    if not os.path.exists(vault_path):
        return []

    files = [
        os.path.join(vault_path, name)
        for name in os.listdir(vault_path)
        if name.startswith("trend_search_") and name.endswith(".md")
    ]
    files.sort(key=lambda path: os.path.getmtime(path), reverse=True)

    snippets = []
    for path in files[:limit]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            snippets.append({
                "source": os.path.basename(path),
                "excerpt": content[:1600],
            })
        except Exception:
            continue
    return snippets


def build_codex_research_brief(insight, output_file="codex_research_brief.md"):
    lines = [
        "# Codex Research Brief",
        "",
        "아래 검색/추론은 외부 API를 직접 붙이지 않고, Codex 내장 검색과 추론으로 수행하기 위한 작업 지시서입니다.",
        "",
        "## 목표",
        "요즘 사람들이 어떤 삶을 살고 무엇 때문에 지치는지 파악한 뒤, 공감과 동기부여가 동시에 가능한 카드뉴스 주제를 도출한다.",
        "",
        "## 검색 질문",
    ]
    for query in PAIN_SIGNAL_QUERIES:
        lines.append(f"- {query}")

    lines.extend([
        "",
        "## 분석 기준",
        "- 사람들이 반복적으로 표현하는 감정",
        "- 삶의 압박이 생기는 원인",
        "- 단순 위로보다 필요한 관점 전환",
        "- 저장/공유를 부르는 실천 메시지",
        "",
        "## 현재 로컬 기본 인사이트",
        json.dumps(insight, ensure_ascii=False, indent=2),
    ])

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def run_antigravity_pain_signal_search(output_dir="agent_runs/audience_research"):
    os.makedirs(output_dir, exist_ok=True)
    results = []

    for idx, query in enumerate(PAIN_SIGNAL_QUERIES, start=1):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"pain_signal_{idx}_{timestamp}.md"
        output_path = os.path.join(output_dir, safe_name)
        prompt = build_search_prompt(query)

        try:
            from antigravity_bridge import run_search_task
            markdown = run_search_task(prompt, output_path)
            if not markdown and os.path.exists(output_path):
                markdown = read_text(output_path)
            if markdown:
                results.append({
                    "query": query,
                    "source": output_path,
                    "markdown": markdown,
                })
                print(f"[Audience Agent] Antigravity 검색 결과 수집 완료: {query}")
            else:
                print(f"[Audience Agent] Antigravity 검색 결과 없음: {query}")
        except Exception as e:
            print(f"[Warning] Antigravity 검색 실패 ({query}): {e}")

    return results


def build_search_prompt(query):
    return f"""
검색 질문: {query}

아래 기준으로 한국어 Markdown 보고서를 작성해 주세요.
- 오늘/최근 사람들이 반복적으로 말하는 고통 키워드
- 20~30대가 겪는 감정, 상황, 욕망
- Instagram/Threads 카드뉴스로 만들 때 저장/공유를 유도할 수 있는 주제
- 핵심 키워드는 명사형으로 분리
""".strip()


def parse_search_results(search_results):
    combined = "\n\n".join(result.get("markdown", "") for result in search_results)
    if not combined.strip():
        return {
            "trending_topics": TOPIC_KEYWORD_CANDIDATES[:3],
            "hot_pain_keywords": PAIN_KEYWORD_CANDIDATES[:5],
        }

    pain_scores = score_keywords(combined, PAIN_KEYWORD_CANDIDATES)
    topic_scores = score_keywords(combined, TOPIC_KEYWORD_CANDIDATES)
    extracted_terms = extract_repeated_terms(combined)

    hot_pain_keywords = merge_ranked_terms(
        [term for term, _count in pain_scores],
        [term for term in extracted_terms if is_pain_like(term)],
        limit=5,
        fallback=PAIN_KEYWORD_CANDIDATES,
    )
    trending_topics = merge_ranked_terms(
        [term for term, _count in topic_scores],
        extracted_terms,
        limit=3,
        fallback=TOPIC_KEYWORD_CANDIDATES,
    )

    return {
        "trending_topics": trending_topics,
        "hot_pain_keywords": hot_pain_keywords,
    }


def score_keywords(text, candidates):
    scored = []
    for keyword in candidates:
        count = text.count(keyword)
        if count:
            scored.append((keyword, count))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def extract_repeated_terms(text):
    tokens = re.findall(r"[가-힣A-Za-z0-9]{2,}(?:\s+[가-힣A-Za-z0-9]{2,})?", text)
    stopwords = {
        "검색",
        "질문",
        "보고서",
        "핵심",
        "요약",
        "패턴",
        "콘텐츠",
        "카드뉴스",
        "Instagram",
        "Threads",
        "사람들이",
        "최근",
        "오늘",
    }
    counts = {}
    for token in tokens:
        token = token.strip()
        if token in stopwords or len(token) > 14:
            continue
        counts[token] = counts.get(token, 0) + 1

    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [term for term, count in ranked if count >= 2][:12]


def is_pain_like(term):
    return any(keyword in term for keyword in PAIN_KEYWORD_CANDIDATES)


def merge_ranked_terms(*term_lists, limit, fallback):
    merged = []
    seen = set()
    for terms in term_lists:
        for term in terms:
            term = str(term or "").strip()
            if not term or term in seen:
                continue
            seen.add(term)
            merged.append(term)
            if len(merged) >= limit:
                return merged

    for term in fallback:
        if term not in seen:
            merged.append(term)
            if len(merged) >= limit:
                break
    return merged


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_audience_artifact_paths():
    """Resolve audience artifact paths for the current job.

    TODO: Replace env resolution with scheduler/job manager context.
    """
    from artifact_mirror import resolve_job_artifact_root

    job_root = resolve_job_artifact_root()
    return {
        "job_id": job_root.job_id,
        "job_root": job_root.root,
        "warning": job_root.warning,
        "audience_insight": f"{job_root.root}/audience_insight.json",
        "audit_report": f"{job_root.root}/reports/audit.json",
        "quality_report": f"{job_root.root}/reports/quality_report.json",
        "analysis_report": f"{job_root.root}/reports/analysis_report.json",
        "audit_log": f"{job_root.root}/reports/audit_log.txt",
    }


def _log_job_path_warning(paths):
    warning = paths.get("warning")
    if not warning:
        return
    try:
        from hooks.audit_logger import log_hook_event
        log_hook_event(
            "JOB_ID",
            paths.get("job_root", "unknown"),
            {"ok": False, "warnings": [warning]},
            log_path=paths["audit_log"],
        )
    except Exception:
        pass


def _run_audience_post_write_hooks(output_file, paths):
    try:
        from hooks.mirror_hook import mirror_audience_insight
        mirror_audience_insight(
            output_file,
            target_path=paths["audience_insight"],
            audit_log_path=paths["audit_log"],
        )
    except Exception:
        pass

    try:
        from hooks.validation_hook import write_audience_insight_validation_report
        write_audience_insight_validation_report(
            artifact_path=paths["audience_insight"],
            report_path=paths["audit_report"],
            audit_log_path=paths["audit_log"],
        )
    except Exception:
        pass


def _run_audience_quality_gate(insight, output_file, paths):
    """Log minimal audience insight readiness warnings without blocking.

    TODO: Promote this to a richer quality report after strategy/script
    consumers define their readiness requirements.
    """
    try:
        from schema_validator import validate_audience_insight_quality
        result = validate_audience_insight_quality(insight)
    except Exception as exc:
        result = {
            "ok": False,
            "warnings": [f"quality gate unavailable: {exc}"],
        }

    if result.get("ok"):
        return result

    try:
        from hooks.audit_logger import log_hook_event
        log_hook_event(
            "AUDIENCE_QUALITY",
            output_file,
            result,
            details="non-blocking quality gate warning",
            log_path=paths["audit_log"],
        )
    except Exception:
        pass

    return result


def _write_audience_quality_report(
    insight,
    quality_result,
    generation_time_seconds,
    report_path,
):
    """Write a small readiness report for downstream stages.

    TODO: Surface this report in monitoring/dashboard views after ownership is
    defined.
    """
    try:
        compatibility = insight.get("compatibility") or {}
        report = {
            "quality_ok": bool(quality_result.get("ok")),
            "warnings": quality_result.get("warnings") or [],
            "generation_time_seconds": round(float(generation_time_seconds), 2),
            "model": insight.get("model"),
            "status": insight.get("status"),
            "json_parse_ok": compatibility.get("json_parse_ok"),
            "schema_ok": insight.get("schema_check", {}).get("ok"),
            "model_backed_fields": compatibility.get("model_backed_fields") or [],
        }
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _run_audience_analysis(paths):
    """Write non-blocking analysis metadata for long-running operation."""
    try:
        from analyze_audience_insight import write_analysis_report
        report = write_analysis_report(
            paths["job_root"],
            report_path=paths["analysis_report"],
        )
    except Exception as exc:
        report = {"ok": False, "warnings": [f"analysis unavailable: {exc}"]}

    try:
        from hooks.audit_logger import log_hook_event
        log_hook_event(
            "ANALYSIS",
            paths["job_root"],
            {"ok": bool(report), "warnings": report.get("notes", [])},
            log_path=paths["audit_log"],
        )
    except Exception:
        pass


def _attach_analysis_summary(insight, paths):
    """Attach advisory analysis metrics for downstream in-process consumers."""
    try:
        from analysis_report_reader import read_analysis_summary
        insight["analysis_summary"] = read_analysis_summary(paths["job_id"])
    except Exception:
        insight["analysis_summary"] = {
            "available": False,
            "job_id": paths.get("job_id"),
            "content_clarity": "unknown",
            "improvement_vs_previous": "unknown",
            "theme_consistency": {
                "overlap_count": 0,
                "previous_available": False,
            },
            "warnings": ["analysis summary unavailable"],
        }


def _attach_strategy_signals(insight):
    """Attach non-blocking strategy adaptation signals for downstream use.

    The attached ``strategy_signals`` dict is advisory only.  Downstream
    strategy/script modules may read it via
    ``example_strategy_consumer.adapt_strategy_from_signals()`` to optionally
    adapt prompt parameters.  This must never block execution or change
    publish behavior.

    TODO (Batch 32+): Replace ``example_strategy_consumer`` import with the
    production strategy consumer once downstream ownership is confirmed.
    """
    try:
        from strategy_signal_builder import build_strategy_signals
        insight["strategy_signals"] = build_strategy_signals(
            insight.get("analysis_summary")
        )
    except Exception:
        insight["strategy_signals"] = {
            "available": False,
            "strategy_mode": "conservative",
            "clarity_flag": "needs_review",
            "consistency_flag": "unknown",
            "improvement_flag": "unknown",
            "source": "fallback",
        }


def _write_job_status_from_insight(insight, artifact_paths, quality_result, generation_time_seconds):
    """Write a lightweight job-scoped status artifact after insight generation.

    Non-blocking wrapper around ``agent_status_writer.write_job_status()``.
    All exceptions are swallowed so the caller's flow is never interrupted.

    TODO (Batch 34+): Stream status to a dashboard WebSocket endpoint once
        the dashboard owns the status subscription contract.
    """
    try:
        from agent_status_writer import write_job_status
        signals = insight.get("strategy_signals") or {}
        analysis_summary = insight.get("analysis_summary") or {}
        write_job_status(
            job_id=artifact_paths.get("job_id", "unknown"),
            job_root=artifact_paths.get("job_root", "jobs/unknown"),
            model=insight.get("model"),
            generation_status=insight.get("status"),
            quality_ok=bool(quality_result.get("ok")),
            quality_warnings=quality_result.get("warnings") or [],
            analysis_available=bool(analysis_summary.get("available")),
            strategy_mode=signals.get("strategy_mode"),
            obsidian_context_enabled=None,  # set later by self_healing_generator
            generation_time_seconds=generation_time_seconds,
            extra={
                "clarity_flag": signals.get("clarity_flag"),
                "consistency_flag": signals.get("consistency_flag"),
                "improvement_flag": signals.get("improvement_flag"),
                "signal_source": signals.get("source"),
            },
        )
    except Exception as exc:
        print(f"[Warning] job status 기록 실패 (non-blocking): {exc}")


def _persist_strategy_signals(insight, output_file):
    """Re-write *output_file* so ``strategy_signals`` is available to file readers.

    ``content_strategy.py`` reads ``audience_insight.json`` from disk, so
    signals must be persisted after ``_attach_strategy_signals()`` writes them
    into the in-memory dict.  This write is best-effort and non-blocking.

    TODO (Batch 32+): Replace with a structured patch-write once job-scoped
    artifact paths are stable.
    """
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(insight, f, ensure_ascii=False, indent=2)
        print(
            f"[Audience Agent] strategy_signals audience_insight.json에 반영 완료: "
            f"mode={insight.get('strategy_signals', {}).get('strategy_mode')}"
        )
    except Exception as exc:
        print(f"[Warning] strategy_signals 파일 반영 실패 (non-blocking): {exc}")


def _create_local_audience_insight(output_file):
    """Default local draft path with non-local fallback handled by caller.

    TODO: Add deeper quality scoring before accepting model-backed JSON.
    """
    from generate_audience_insight_local import generate_local_draft, write_draft

    draft = generate_local_draft(
        model_name=os.getenv("LOCAL_AUDIENCE_INSIGHT_MODEL", DEFAULT_LOCAL_AUDIENCE_MODEL),
        endpoint=os.getenv("LOCAL_AUDIENCE_INSIGHT_ENDPOINT", "http://localhost:11434"),
        vault_path=os.getenv("LOCAL_AUDIENCE_INSIGHT_VAULT_PATH") or None,
        ollama_timeout_seconds=(
            os.getenv("OLLAMA_TIMEOUT_SECONDS")
            or DEFAULT_LOCAL_AUDIENCE_TIMEOUT_SECONDS
        ),
    )
    schema_ok = draft.get("schema_check", {}).get("ok")
    if draft.get("status") != LOCAL_AUDIENCE_SUCCESS_STATUS or not schema_ok:
        raise RuntimeError(
            f"local audience insight unavailable: status={draft.get('status')}, "
            f"schema_ok={schema_ok}"
        )
    write_draft(output_file, draft)
    return draft


def create_audience_insight(output_file="audience_insight.json", use_local_draft=True):
    artifact_paths = _resolve_audience_artifact_paths()
    _log_job_path_warning(artifact_paths)
    local_draft_enabled = use_local_draft or _truthy(
        os.getenv("LOCAL_AUDIENCE_INSIGHT_DRAFT_ENABLED")
    )
    if local_draft_enabled:
        try:
            generation_started = time.perf_counter()
            insight = _create_local_audience_insight(output_file)
            generation_time_seconds = time.perf_counter() - generation_started
            _run_audience_post_write_hooks(output_file, artifact_paths)
            quality_result = _run_audience_quality_gate(
                insight,
                output_file,
                artifact_paths,
            )
            _write_audience_quality_report(
                insight,
                quality_result,
                generation_time_seconds,
                artifact_paths["quality_report"],
            )
            _run_audience_analysis(artifact_paths)
            _attach_analysis_summary(insight, artifact_paths)
            _attach_strategy_signals(insight)
            _persist_strategy_signals(insight, output_file)
            _write_job_status_from_insight(
                insight, artifact_paths, quality_result, generation_time_seconds
            )
            build_codex_research_brief(insight)
            print(f"[Audience Agent] local audience insight draft 생성 완료: {output_file}")
            print("[Audience Agent] Codex 조사 지시서 생성 완료: codex_research_brief.md")
            return insight
        except Exception as exc:
            print(f"[Warning] 로컬 audience insight draft 실패, 기존 경로로 폴백합니다: {exc}")

    generation_started = time.perf_counter()
    local_trends = read_recent_local_trends()
    search_results = run_antigravity_pain_signal_search()
    parsed_search = parse_search_results(search_results)
    insight = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "research_mode": "antigravity_search_plus_local_seed",
        "codex_search_queries": PAIN_SIGNAL_QUERIES,
        "antigravity_search_sources": [
            {
                "query": result["query"],
                "source": result["source"],
                "excerpt": result["markdown"][:1600],
            }
            for result in search_results
        ],
        "local_trend_sources": local_trends,
        **parsed_search,
        **DEFAULT_AUDIENCE_INSIGHT,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(insight, f, ensure_ascii=False, indent=2)
    generation_time_seconds = time.perf_counter() - generation_started

    _run_audience_post_write_hooks(output_file, artifact_paths)
    quality_result = _run_audience_quality_gate(insight, output_file, artifact_paths)
    _write_audience_quality_report(
        insight,
        quality_result,
        generation_time_seconds,
        artifact_paths["quality_report"],
    )
    _run_audience_analysis(artifact_paths)
    _attach_analysis_summary(insight, artifact_paths)
    _attach_strategy_signals(insight)
    _persist_strategy_signals(insight, output_file)
    _write_job_status_from_insight(
        insight, artifact_paths, quality_result, generation_time_seconds
    )

    build_codex_research_brief(insight)
    print(f"[Audience Agent] audience insight 생성 완료: {output_file}")
    print("[Audience Agent] Codex 조사 지시서 생성 완료: codex_research_brief.md")
    return insight


if __name__ == "__main__":
    create_audience_insight()
