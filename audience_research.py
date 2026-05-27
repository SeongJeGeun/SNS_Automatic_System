import json
import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()


PAIN_SIGNAL_QUERIES = [
    "요즘 20대 30대 직장인 번아웃 무기력 불안 고민",
    "요즘 사람들이 힘들어하는 이유 자기계발 동기부여 피로감",
    "인스타그램 자기계발 카드뉴스 저장 많이 되는 고민 주제",
    "MZ 세대 돈 커리어 관계 자존감 불안 루틴 고민",
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


def create_audience_insight(output_file="audience_insight.json"):
    local_trends = read_recent_local_trends()
    insight = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "research_mode": "local_seed_plus_codex_brief",
        "codex_search_queries": PAIN_SIGNAL_QUERIES,
        "local_trend_sources": local_trends,
        **DEFAULT_AUDIENCE_INSIGHT,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(insight, f, ensure_ascii=False, indent=2)

    build_codex_research_brief(insight)
    print(f"[Audience Agent] audience insight 생성 완료: {output_file}")
    print("[Audience Agent] Codex 조사 지시서 생성 완료: codex_research_brief.md")
    return insight


if __name__ == "__main__":
    create_audience_insight()
