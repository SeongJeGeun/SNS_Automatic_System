import json
from datetime import datetime


DEFAULT_STRATEGY = {
    "target_reader": "열심히 살고 싶은데 번아웃과 무기력 때문에 스스로를 믿지 못하는 20~30대",
    "audience_pain": "쉬어도 회복되지 않고, 해야 할 일을 알면서도 시작하지 못하는 상태",
    "core_promise": "독자가 게으른 사람이 아니라 회복 시스템이 무너진 사람이라는 관점 전환을 준다.",
    "hook_type": "공감형 반전 훅",
    "hook_rules": [
        "첫 장은 철학 선언이 아니라 독자의 현재 상태를 대신 말해야 한다.",
        "추상어보다 상황어를 쓴다. 예: '쉬어도 피곤한 이유', '침대에서 못 나오는 날'",
        "비난하지 말고, 자책을 멈추게 하는 반전을 넣는다.",
    ],
    "story_structure": [
        "1장: 독자가 자기 이야기라고 느끼는 고통 훅",
        "2장: 현재 삶의 상태를 공감",
        "3장: 문제가 의지 부족이 아니라 시스템 부재임을 설명",
        "4장: 기존 동기부여 방식의 한계 지적",
        "5장: 작게 다시 움직이는 관점 전환",
        "6장: 오늘 바로 할 수 있는 작은 행동",
        "마지막 장: 저장하고 다시 볼 만한 결론과 CTA",
    ],
    "cta_type": "저장 유도",
    "cta_rule": "마지막 장은 '저장해두고 무너지는 날 다시 보라'처럼 자연스럽게 저장 이유를 줘야 한다.",
    "avoid": [
        "멋있지만 누구에게 하는 말인지 모르는 추상 문장",
        "독자를 게으르다고 단정하는 과한 훈계",
        "성공, 규율, 몰입 같은 단어만 반복하는 구성",
        "카드마다 같은 의미를 다른 말로 반복하는 구성",
    ],
}


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def create_content_strategy(
    audience_file="audience_insight.json",
    output_file="content_strategy.json",
):
    audience = load_json(audience_file) or {}
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

    strategy["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    strategy["quality_bar"] = {
        "minimum_score": 72,
        "must_have": [
            "첫 장에 구체적인 고통이 있어야 한다.",
            "3장 안에 문제 원인 해석이 나와야 한다.",
            "마지막 장에 저장할 이유가 있어야 한다.",
            "각 장은 하나의 생각만 담아야 한다.",
            "image_prompt는 각 장 의미와 달라야 한다.",
        ],
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(strategy, f, ensure_ascii=False, indent=2)

    write_strategy_brief(strategy)
    print(f"[Strategy Agent] 콘텐츠 전략 생성 완료: {output_file}")
    return strategy


def write_strategy_brief(strategy, output_file="antigravity_strategy_brief.md"):
    lines = [
        "# Antigravity Content Strategy Brief",
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
