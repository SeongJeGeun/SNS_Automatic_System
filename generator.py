import json
import os
import re
from datetime import datetime


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _as_text(value, fallback=""):
    if value is None:
        return fallback
    if isinstance(value, str):
        return value.strip() or fallback
    return json.dumps(value, ensure_ascii=False)


def _pick_first(data, keys, fallback=""):
    if not isinstance(data, dict):
        return fallback
    for key in keys:
        value = data.get(key)
        if value:
            if isinstance(value, list):
                return _as_text(value[0], fallback) if value else fallback
            return _as_text(value, fallback)
    return fallback


def _clean_sentence(text, max_len=64):
    text = re.sub(r"\s+", " ", _as_text(text)).strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rstrip()
    return cut + "…"


def _build_pages(title, hook, pain, insight, action, closing):
    return [
        {
            "page": 1,
            "role": "hook",
            "headline": _clean_sentence(title, 38),
            "body": _clean_sentence(hook, 70),
            "emphasis": "멈춰 선 나를 다시 움직이는 문장",
        },
        {
            "page": 2,
            "role": "pain",
            "headline": "문제는 의지가 아니다",
            "body": _clean_sentence(pain, 82),
            "emphasis": "흐트러진 환경이 나를 끌고 간다",
        },
        {
            "page": 3,
            "role": "reframe",
            "headline": "규율은 속박이 아니다",
            "body": _clean_sentence(insight, 82),
            "emphasis": "규율은 자유를 되찾는 구조다",
        },
        {
            "page": 4,
            "role": "action",
            "headline": "오늘은 하나만 고정하라",
            "body": _clean_sentence(action, 82),
            "emphasis": "작게 고정하면 삶이 다시 정렬된다",
        },
        {
            "page": 5,
            "role": "closing",
            "headline": "나를 다시 세우는 법",
            "body": _clean_sentence(closing, 82),
            "emphasis": "완벽함보다 반복이 먼저다",
        },
    ]


def generate_script(diversify=False):
    audience = _load_json("audience_insight.json", {})
    strategy = _load_json("content_strategy.json", {})
    healing = _load_json("self_healing_strategy.json", {}) if diversify else {}

    theme = _pick_first(strategy, ["theme", "topic", "next_direction"], "규율이라는 고귀한 속박")
    audience_pain = _pick_first(audience, ["pain", "core_pain", "insight", "summary"], "하고 싶은 일은 많은데 하루가 흐트러져 아무것도 붙잡지 못하는 상태")
    hook_strategy = _pick_first(strategy, ["hook", "hook_strategy", "headline"], "자유롭고 싶다면 먼저 하루의 틀을 만들어야 한다")
    core_insight = _pick_first(strategy, ["insight", "message", "core_message"], "규율은 나를 억압하는 감옥이 아니라 무너진 나를 붙잡아주는 최소한의 구조다")
    action = _pick_first(strategy, ["action", "routine", "cta"], "오늘 하루 딱 하나의 시간을 정하고, 그 시간만큼은 핸드폰을 멀리 둔 채 해야 할 일을 시작하라")

    if healing:
        healing_direction = _pick_first(healing, ["next_direction", "hook_strategy", "visual_concept"], "더 구체적인 행동 루틴으로 독자의 저장 가치를 높인다")
        action = f"{action}. 이번에는 {healing_direction}"

    title = _clean_sentence(theme, 34)
    closing = "자유는 아무렇게나 사는 데서 오지 않는다. 나를 지키는 작은 규칙을 반복할 때 다시 움직일 힘이 생긴다."

    script = {
        "title": title,
        "subtitle": "Mind Factory 자동 기획",
        "caption": f"{hook_strategy}\n\n오늘의 주제: {title}\n\n#마인드팩토리 #자기계발 #규율 #루틴 #동기부여",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": {
            "audience_insight": os.path.exists("audience_insight.json"),
            "content_strategy": os.path.exists("content_strategy.json"),
            "self_healing_strategy": bool(healing),
        },
        "pages": _build_pages(title, hook_strategy, audience_pain, core_insight, action, closing),
    }

    with open("script.json", "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    print("✅ generator.py: script.json 생성 완료")
    return script


if __name__ == "__main__":
    generate_script(diversify=False)
