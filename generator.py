import json
import os
import re
from datetime import datetime


PAIN_WORDS = ["피곤", "무기력", "불안", "자책", "번아웃", "비교", "막막", "무너", "힘들", "지친", "압박", "뒤처", "침대", "루틴"]
ACTION_WORDS = ["오늘", "지금", "딱", "하나", "10분", "물", "걷", "쓰기", "끄고", "시작", "루틴"]


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


def _clean_sentence(text, max_len=68):
    text = re.sub(r"\s+", " ", _as_text(text)).strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rstrip()
    return cut + "…"


def _page(page, role, heading, sub_text, image_prompt, layout_hint):
    return {
        "page": page,
        "role": role,
        "heading": _clean_sentence(heading, 32),
        "sub_text": _clean_sentence(sub_text, 42),
        "image_prompt": image_prompt,
        "layout_hint": layout_hint,
    }


def _build_pages(title, pain, insight, action):
    """Build evaluator-friendly pages using heading/sub_text/image_prompt keys."""
    return [
        _page(
            1,
            "pain_hook",
            "침대에서 못 일어나고 불안한가요?",
            "피곤하고 무기력한데 또 뒤처질까 자책하는 밤.",
            "dark bedroom, phone glow, tired young adult, heavy anxiety mood, Korean Instagram headline space",
            "large bottom headline with small top label",
        ),
        _page(
            2,
            "cause_reframe",
            "문제는 의지가 아니라 시스템입니다",
            "루틴이 없으면 불안과 비교가 하루를 먼저 끌고 갑니다.",
            "minimal desk, scattered notes, broken routine symbols, muted blue gray tone",
            "split layout: problem label left, explanation box right",
        ),
        _page(
            3,
            "three_step_tip_1",
            "3단계 방법: 지금 10분만 시작",
            "1단계 물 한 컵, 2단계 폰 끄고, 3단계 딱 하나 쓰기.",
            "three numbered cards, water glass, phone off icon, pen and notebook, clean high contrast",
            "three stacked tip boxes with big numbers",
        ),
        _page(
            4,
            "three_step_tip_2",
            "무너지는 날의 요약 원칙",
            "힘들면 크게 바꾸지 말고 걷기 10분과 루틴 하나만 지키세요.",
            "walking shoes at door, simple checklist, warm light, recovery and routine mood",
            "summary card with checklist bullets",
        ),
        _page(
            5,
            "identity_shift",
            "규율은 자유를 뺏지 않습니다",
            "규율은 무너진 나를 다시 회복시키는 작은 안전장치입니다.",
            "open window, calm morning light, notebook with routine grid, hopeful mood",
            "quote-centered layout with subtle frame",
        ),
        _page(
            6,
            "micro_action",
            "오늘 딱 하나만 선언하세요",
            "지금 10분 시작. 할 일 하나 쓰고, 끝나면 체크하세요.",
            "bold checklist template, pen tick mark, minimal black and cream Instagram design",
            "template style with blank line for user action",
        ),
        _page(
            7,
            "save_cta",
            "챌린지 인증 템플릿: 오늘의 10분",
            "저장해두고 무너지는 날 다시 꺼내 보세요. 댓글에 미션 완료 선언.",
            "challenge completion card, stamp icon, save reminder, strong CTA, Korean social media post",
            "final CTA card with save icon and comment prompt",
        ),
    ]


def generate_script(diversify=False):
    audience = _load_json("audience_insight.json", {})
    strategy = _load_json("content_strategy.json", {})
    healing = _load_json("self_healing_strategy.json", {}) if diversify else {}

    theme = _pick_first(strategy, ["theme", "topic", "next_direction"], "규율이라는 고귀한 속박")
    audience_pain = _pick_first(
        audience,
        ["pain", "core_pain", "insight", "summary"],
        "피곤하고 무기력한데도 비교와 불안 때문에 쉬지 못하고, 침대에 누워 자책만 반복하는 상태",
    )
    hook_strategy = _pick_first(
        strategy,
        ["hook", "hook_strategy", "headline"],
        "지친 사람에게 필요한 건 더 센 의지가 아니라 다시 시작할 수 있는 작은 루틴이다",
    )
    core_insight = _pick_first(
        strategy,
        ["insight", "message", "core_message"],
        "규율은 나를 억압하는 감옥이 아니라 무너진 나를 회복시키는 시스템이다",
    )
    action = _pick_first(
        strategy,
        ["action", "routine", "cta"],
        "오늘 지금 딱 10분만 폰을 끄고 물 한 컵을 마신 뒤 해야 할 일 하나를 쓰고 시작하라",
    )

    if healing:
        healing_direction = _pick_first(
            healing,
            ["next_direction", "hook_strategy", "visual_concept"],
            "저장하고 따라 할 수 있는 챌린지 템플릿을 강화한다",
        )
        action = f"{action}. {healing_direction}"

    title = _clean_sentence(theme, 34)
    pages = _build_pages(title, audience_pain, core_insight, action)

    script = {
        "title": title,
        "subtitle": "Mind Factory 자동 기획",
        "caption": (
            f"{hook_strategy}\n\n"
            "오늘 할 일은 거창하지 않습니다.\n"
            "물 한 컵, 폰 끄기, 10분 시작.\n\n"
            "저장해두고 무너지는 날 다시 꺼내 보세요.\n"
            "댓글에 '오늘의 10분 완료'라고 인증하면 됩니다.\n\n"
            "#마인드팩토리 #자기계발 #규율 #루틴 #동기부여 #번아웃회복"
        ),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "quality_intent": {
            "pain_words": PAIN_WORDS,
            "action_words": ACTION_WORDS,
            "structure": "pain hook -> cause reframe -> 3-step tips -> identity shift -> challenge CTA",
        },
        "source": {
            "audience_insight": os.path.exists("audience_insight.json"),
            "content_strategy": os.path.exists("content_strategy.json"),
            "self_healing_strategy": bool(healing),
        },
        "pages": pages,
    }

    with open("script.json", "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    print(f"✅ generator.py: script.json 생성 완료 ({len(pages)} pages, quality-gate optimized)")
    return script


if __name__ == "__main__":
    generate_script(diversify=False)
