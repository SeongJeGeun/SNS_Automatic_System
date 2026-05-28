"""Content strategy module: builds content_strategy.json from audience insight.

Batch 31 — Signal Adaptation Integration
-----------------------------------------
``create_content_strategy()`` now reads ``strategy_signals`` from the audience
insight artifact and optionally adapts:

- ``quality_bar.minimum_score``  (conservative → lower threshold)
- ``story_structure``            (conservative → shortened; reinforce_theme → theme lock)
- ``hook_rules``                 (clarity=needs_review → specificity directive added)
- ``obsidian_context_enabled``   (reinforce_theme → True, others → False)

All adaptation is **non-blocking**: if signals are absent or the consumer
raises any exception, the strategy falls back to conservative defaults without
affecting publish behavior.

TODO (Batch 32+): Surface ``adapted_strategy_config`` in monitoring/dashboard
    views after QA ownership is defined.
"""

import json
from datetime import datetime

from example_strategy_consumer import adapt_strategy_from_signals


DEFAULT_STRATEGY = {
    "target_reader": "열심히 살고 싶은데 번아웃과 무기력 때문에 스스로를 믿지 못하는 20~30대 (특히 규율과 통제를 선호하는 남성 타겟의 정체성 표출 저격)",
    "audience_pain": "쉬어도 회복되지 않고, 해야 할 일을 알면서도 시작하지 못하는 상태",
    "core_promise": "독자가 게으른 사람이 아니라 회복 시스템이 무너진 사람이라는 관점 전환을 준다.",
    "hook_type": "공감형 반전 훅",
    "hook_rules": [
        "첫 장은 철학 선언이 아니라 독자의 현재 상태를 대신 말해야 한다. (자기표현 및 사회연결 자극)",
        "추상어보다 상황어를 쓴다. 예: '쉬어도 피곤한 이유', '침대에서 못 나오는 날'",
        "비난하지 말고, 자책을 멈추게 하는 반전을 넣는다.",
    ],
    "story_structure": [
        "1장: 독자가 자기 이야기라고 느끼는 고통 훅 (자기표현 정체성 저격)",
        "2장: 현재 삶의 상태를 공감",
        "3장: 문제가 의지 부족이 아니라 시스템 부재임을 설명 (헤비 유저를 위한 구체적인 이타주의적 3단계 실천 팁 제시)",
        "4장: 기존 동기부여 방식의 한계 지적",
        "5장: 작게 다시 움직이는 관점 전환",
        "6장: 오늘 바로 할 수 있는 작은 행동",
        "마지막 장: 라이트 유저의 지위 추구와 성취 증명을 위한 인증/챌린지 템플릿(글귀) 및 저장하고 다시 볼 만한 결론과 CTA",
    ],
    "cta_type": "저장 유도",
    "cta_rule": "마지막 장은 '저장해두고 무너지는 날 다시 보라'처럼 자연스럽게 저장 이유를 줘야 한다.",
    "avoid": [
        "멋있지만 누구에게 하는 말인지 모르는 추상 문장",
        "독자를 게으르다고 단정하는 과한 훈계",
        "성공, 규율, 몰입 같은 단어만 반복하는 구성",
        "카드마다 같은 의미를 다른 말로 반복하는 구성",
        "오락성을 유발하는 가벼운 네온 배색이나 단순 유머 요소",
    ],
}


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Signal adaptation helpers (non-blocking)
# ---------------------------------------------------------------------------

def _apply_signal_adaptation(strategy: dict, adapted_config: dict) -> None:
    """Mutate *strategy* in-place based on *adapted_config* from the consumer.

    Rules applied here mirror the adaptation rules documented in
    ``example_strategy_consumer``:

    - conservative  → lower quality bar score, shorten story_structure,
                       add specificity directive to hook_rules
    - reinforce_theme → lock story theme, enable obsidian_context flag,
                         add theme-repetition note to hook_rules
    - clarity=needs_review → add prompt-specificity directive to hook_rules
                              (applies to any strategy_mode)

    All changes are advisory; they append or adjust fields already present
    in *strategy* without removing existing rules.
    """
    mode = adapted_config.get("strategy_mode", "conservative")
    specificity = adapted_config.get("prompt_specificity", "normal")
    theme_repetition = adapted_config.get("theme_repetition", False)
    obsidian = adapted_config.get("obsidian_context", False)
    rationale = adapted_config.get("rationale", "")

    # Store the full adapted config for downstream inspection / audit.
    strategy["adapted_strategy_config"] = adapted_config

    # -- conservative: tighten quality bar, shorten story arc ---------------
    if mode == "conservative":
        # Lower the minimum score so a conservative-mode output is not unfairly
        # penalised for shorter length.
        qb = strategy.setdefault("quality_bar", {})
        qb["minimum_score"] = min(qb.get("minimum_score", 72), 65)
        qb["signal_note"] = (
            "conservative mode: minimum_score relaxed to 65 to allow "
            "shorter, safer output"
        )

        # Compress story structure to 5 cards (already the minimum).
        strategy["story_structure"] = merge_unique(
            strategy.get("story_structure", []),
            ["[conservative] 총 장수를 5장 이내로 압축하고 핵심 공감-행동 흐름만 유지한다."],
        )

    # -- reinforce_theme: lock theme, enable obsidian ------------------------
    if mode == "reinforce_theme":
        strategy["obsidian_context_enabled"] = True
        strategy["story_structure"] = merge_unique(
            strategy.get("story_structure", []),
            [
                "[reinforce_theme] 이전 카드뉴스의 핵심 주제를 반복 강화한다. "
                "동일 주제를 새로운 각도에서 재해석해 일관성을 유지한다.",
            ],
        )
        strategy["hook_rules"] = merge_unique(
            strategy.get("hook_rules", []),
            [
                "[reinforce_theme] 이전 시리즈와 연속성이 느껴지는 훅 표현을 "
                "우선 사용한다.",
            ],
        )

    # -- clarity=needs_review: elevate prompt specificity -------------------
    if specificity == "high":
        strategy["hook_rules"] = merge_unique(
            strategy.get("hook_rules", []),
            [
                "[clarity:needs_review] 독자의 구체적인 상황(시간·장소·행동)을 "
                "훅 첫 문장에 명시하여 모호함을 제거한다.",
            ],
        )
        strategy.setdefault("quality_bar", {})["prompt_specificity"] = "high"

    # -- obsidian flag (shared by reinforce_theme and any future modes) ------
    if obsidian:
        strategy["obsidian_context_enabled"] = True

    # Always store the rationale for auditability.
    strategy["signal_adaptation_rationale"] = rationale


def _attach_signal_adaptation(strategy: dict, audience: dict) -> None:
    """Non-blocking wrapper: read signals from audience and adapt strategy.

    TODO (Batch 32+): Replace direct dict access with a typed interface once
        ``audience_insight`` schema is stabilised.
    """
    try:
        signals = audience.get("strategy_signals")
        adapted_config = adapt_strategy_from_signals(signals)
        _apply_signal_adaptation(strategy, adapted_config)
        print(
            f"[Strategy Agent] 시그널 어댑테이션 적용 완료: "
            f"mode={adapted_config.get('strategy_mode')}, "
            f"specificity={adapted_config.get('prompt_specificity')}, "
            f"obsidian={adapted_config.get('obsidian_context')}"
        )
    except Exception as exc:
        # Non-blocking: log and continue without modifying strategy further.
        print(f"[Warning] 시그널 어댑테이션 실패 (non-blocking): {exc}")
        strategy["adapted_strategy_config"] = {
            "strategy_mode": "conservative",
            "source": "error_fallback",
            "rationale": f"adaptation error: {exc}",
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_content_strategy(
    audience_file="audience_insight.json",
    output_file="content_strategy.json",
):
    audience = load_json(audience_file) or {}
    previous_strategy = load_json(output_file) or {}
    strategy = dict(DEFAULT_STRATEGY)

    if audience.get("audience_state"):
        strategy["audience_state"] = audience["audience_state"]
    if audience.get("core_pains"):
        strategy["audience_pain"] = audience["core_pains"][0]
        strategy["secondary_pains"] = audience["core_pains"][1:]
    if audience.get("needed_message"):
        strategy["core_promise"] = audience["needed_message"]
    if audience.get("story_angle"):
        strategy["story_angle"] = audience["story_angle"]
    if audience.get("emotional_keywords"):
        strategy["emotional_keywords"] = audience["emotional_keywords"]
    if audience.get("trending_topics"):
        strategy["trending_topics"] = audience["trending_topics"]
    if audience.get("hot_pain_keywords"):
        strategy["hot_pain_keywords"] = audience["hot_pain_keywords"]
        strategy["hook_rules"] = merge_unique(
            strategy["hook_rules"],
            [
                "첫 장 heading에는 오늘 검색에서 강하게 반복된 고통 키워드를 1개 이상 반영한다: "
                + ", ".join(audience["hot_pain_keywords"][:5])
            ],
        )

    merge_performance_learning(strategy, previous_strategy)

    # ------------------------------------------------------------------
    # Batch 31: apply strategy_signals adaptation (non-blocking)
    # ------------------------------------------------------------------
    _attach_signal_adaptation(strategy, audience)

    strategy["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    strategy["quality_bar"] = strategy.get("quality_bar") or {}
    strategy["quality_bar"].setdefault("minimum_score", 72)
    strategy["quality_bar"].setdefault("must_have", [
        "첫 장에 구체적인 고통이 있어야 한다.",
        "3장 안에 문제 원인 해석이 나와야 한다.",
        "마지막 장에 저장할 이유가 있어야 한다.",
        "각 장은 하나의 생각만 담아야 한다.",
        "image_prompt는 각 장 의미와 달라야 한다.",
        "중간 장(3~4장)에 이타주의 자극을 위한 즉시 적용 가능한 3단계 실천 팁 요약이 포함되어야 한다.",
        "마지막 장에 라이트 유저의 성취/지위 증명을 돕는 인증 또는 챌린지 템플릿(문구)이 명확히 포함되어야 한다."
    ])

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(strategy, f, ensure_ascii=False, indent=2)

    write_strategy_brief(strategy)
    print(f"[Strategy Agent] 콘텐츠 전략 생성 완료: {output_file}")
    return strategy


def merge_performance_learning(strategy, previous_strategy):
    passthrough_fields = [
        "best_hook_patterns",
        "best_card_count",
        "proven_cta_phrases",
        "performance_learning",
    ]
    for field in passthrough_fields:
        if previous_strategy.get(field):
            strategy[field] = previous_strategy[field]

    if previous_strategy.get("best_hook_patterns"):
        strategy["hook_rules"] = merge_unique(
            strategy["hook_rules"],
            [
                "성과가 검증된 첫 장 heading 패턴을 우선 참고한다: "
                + " / ".join(previous_strategy["best_hook_patterns"][:5])
            ],
        )

    if previous_strategy.get("proven_cta_phrases"):
        strategy["cta_rule"] = (
            strategy["cta_rule"]
            + " 검증된 CTA 표현을 우선 변형해 사용한다: "
            + " / ".join(previous_strategy["proven_cta_phrases"][:5])
        )

    if previous_strategy.get("best_card_count"):
        strategy["best_card_count"] = previous_strategy["best_card_count"]
        strategy["story_structure"] = merge_unique(
            strategy["story_structure"],
            [f"성과 로그 기준 최빈 카드 장 수는 {previous_strategy['best_card_count']}이다."],
        )

    if previous_strategy.get("avoid"):
        strategy["avoid"] = merge_unique(strategy["avoid"], previous_strategy["avoid"])


def merge_unique(existing, additions):
    result = []
    seen = set()
    for item in list(existing or []) + list(additions or []):
        item = str(item or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def write_strategy_brief(strategy, output_file="codex_strategy_brief.md"):
    lines = [
        "# Codex Content Strategy Brief",
        "",
        "카드뉴스 생성 전에 반드시 따라야 하는 콘텐츠 전략입니다.",
        "",
        "```json",
        json.dumps(strategy, ensure_ascii=False, indent=2),
        "```",
    ]
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    create_content_strategy()
