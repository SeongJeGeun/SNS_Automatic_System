import json
import os
import random
import re
from datetime import datetime


PAIN_WORDS = ["피곤", "무기력", "불안", "자책", "번아웃", "비교", "막막", "무너", "힘들", "지친", "압박", "뒤처", "침대", "루틴"]
ACTION_WORDS = ["오늘", "지금", "딱", "하나", "10분", "물", "걷", "쓰기", "끄고", "시작", "루틴"]

TOPIC_TEMPLATES = [
    {
        "title": "작은 루틴이 무너진 하루를 구한다",
        "pain_heading": "계속 미루고 자책하고 있나요?",
        "pain_sub": "불안한데 시작은 안 되고, 비교만 하다 하루가 끝나는 밤.",
        "reframe_heading": "문제는 게으름이 아니라 시작 장벽입니다",
        "reframe_sub": "의지를 키우기보다 시작을 너무 작게 만드는 시스템이 먼저입니다.",
        "tip_heading": "3단계 방법: 시작을 줄이세요",
        "tip_sub": "1단계 물 한 컵, 2단계 10분 타이머, 3단계 해야 할 일 하나.",
        "summary_heading": "오늘의 원칙은 작게 끝내기",
        "summary_sub": "힘들면 완벽한 하루보다 무너지지 않는 루틴 하나만 지키세요.",
        "identity_heading": "꾸준함은 감정이 아니라 설계입니다",
        "identity_sub": "기분이 나빠도 돌아올 수 있는 길을 미리 만들어 두는 것.",
        "action_heading": "오늘 딱 하나만 체크하세요",
        "action_sub": "지금 10분 시작하고 끝나면 체크 표시 하나만 남기세요.",
        "cta_heading": "챌린지 인증 템플릿: 오늘의 10분",
        "cta_sub": "저장해두고 흔들리는 날 다시 꺼내 보세요. 댓글에 완료 선언.",
        "tags": "#루틴 #자기계발 #번아웃회복 #시작습관 #마인드팩토리",
    },
    {
        "title": "비교가 심한 날 나를 다시 잡는 법",
        "pain_heading": "남들은 앞서가는데 나만 멈춘 것 같나요?",
        "pain_sub": "피곤한데도 쉬면 뒤처질까 불안해서 계속 자책하는 하루.",
        "reframe_heading": "비교는 정보가 아니라 소음입니다",
        "reframe_sub": "내 루틴이 없을 때 타인의 속도가 내 기준처럼 느껴집니다.",
        "tip_heading": "3단계 방법: 비교를 끊는 루틴",
        "tip_sub": "1단계 앱 닫기, 2단계 숨 고르기, 3단계 오늘 할 일 하나 쓰기.",
        "summary_heading": "오늘의 원칙은 내 속도 회복",
        "summary_sub": "막막하면 크게 이기려 하지 말고 10분만 내 페이스로 돌아오세요.",
        "identity_heading": "나를 지키는 규율은 조용합니다",
        "identity_sub": "보여주기보다 오늘의 작은 약속을 지키는 사람이 단단해집니다.",
        "action_heading": "지금 비교 앱 하나만 닫으세요",
        "action_sub": "닫고, 물 한 컵 마시고, 할 일 하나를 10분만 시작하세요.",
        "cta_heading": "인증 템플릿: 비교 대신 10분 완료",
        "cta_sub": "저장하고 다음 번 불안한 날 다시 사용하세요. 댓글에 완료 남기기.",
        "tags": "#비교습관 #불안관리 #루틴회복 #멘탈관리 #마인드팩토리",
    },
    {
        "title": "번아웃 직전의 하루를 회복하는 10분",
        "pain_heading": "쉬어도 피곤하고 시작도 두렵나요?",
        "pain_sub": "침대에 누워도 마음은 불안하고, 해야 할 일은 계속 쌓입니다.",
        "reframe_heading": "회복은 멈춤이 아니라 재정렬입니다",
        "reframe_sub": "무기력한 날에는 더 세게 밀기보다 에너지를 새로 배치해야 합니다.",
        "tip_heading": "3단계 방법: 10분 회복 루틴",
        "tip_sub": "1단계 물 마시기, 2단계 방 한 곳 정리, 3단계 가장 작은 일 시작.",
        "summary_heading": "오늘의 원칙은 에너지 절약",
        "summary_sub": "힘든 날의 목표는 완벽이 아니라 다시 움직일 만큼만 회복하는 것.",
        "identity_heading": "무너진 날도 루틴은 남습니다",
        "identity_sub": "작은 규칙 하나가 다음 하루의 바닥을 받쳐 줍니다.",
        "action_heading": "지금 주변 한 곳만 정리하세요",
        "action_sub": "책상 한 칸, 침대 한쪽, 메모 하나. 10분이면 충분합니다.",
        "cta_heading": "저장용 체크리스트: 회복 10분",
        "cta_sub": "저장하고 번아웃이 오는 날 그대로 따라 하세요. 완료 인증 환영.",
        "tags": "#번아웃 #회복루틴 #무기력탈출 #자기관리 #마인드팩토리",
    },
]


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


def _select_template(strategy, audience, diversify):
    seed_basis = "|".join([
        datetime.now().strftime("%Y%m%d%H"),
        _as_text(strategy.get("theme") if isinstance(strategy, dict) else ""),
        _as_text(strategy.get("topic") if isinstance(strategy, dict) else ""),
        _as_text(audience.get("story_angle") if isinstance(audience, dict) else ""),
        str(os.getenv("JOB_ID", "")),
        "diversify" if diversify else "normal",
    ])
    rng = random.Random(seed_basis)
    return rng.choice(TOPIC_TEMPLATES)


def _build_pages(template):
    return [
        _page(1, "pain_hook", template["pain_heading"], template["pain_sub"], "dark phone glow, tired young adult, anxiety mood, Korean Instagram headline space", "large bottom headline with small top label"),
        _page(2, "cause_reframe", template["reframe_heading"], template["reframe_sub"], "minimal desk, scattered notes, broken routine symbols, muted blue gray tone", "split layout: problem label left, explanation box right"),
        _page(3, "three_step_tip_1", template["tip_heading"], template["tip_sub"], "three numbered cards, water glass, phone off icon, pen and notebook, clean contrast", "three stacked tip boxes with big numbers"),
        _page(4, "three_step_tip_2", template["summary_heading"], template["summary_sub"], "walking shoes at door, simple checklist, warm light, recovery and routine mood", "summary card with checklist bullets"),
        _page(5, "identity_shift", template["identity_heading"], template["identity_sub"], "open window, calm morning light, notebook with routine grid, hopeful mood", "quote-centered layout with subtle frame"),
        _page(6, "micro_action", template["action_heading"], template["action_sub"], "bold checklist template, pen tick mark, minimal black and cream Instagram design", "template style with blank line for user action"),
        _page(7, "save_cta", template["cta_heading"], template["cta_sub"], "challenge completion card, stamp icon, save reminder, strong CTA, Korean social media post", "final CTA card with save icon and comment prompt"),
    ]


def generate_script(diversify=False):
    audience = _load_json("audience_insight.json", {})
    strategy = _load_json("content_strategy.json", {})
    healing = _load_json("self_healing_strategy.json", {}) if diversify else {}
    template = _select_template(strategy, audience, diversify)

    theme = _pick_first(strategy, ["theme", "topic", "next_direction"], template["title"])
    hook_strategy = _pick_first(strategy, ["hook", "hook_strategy", "headline"], template["reframe_sub"])

    if theme == "규율이라는 고귀한 속박":
        title = template["title"]
    else:
        title = _clean_sentence(theme, 34)

    if healing:
        title = template["title"]

    pages = _build_pages(template)

    script = {
        "title": title,
        "subtitle": "Mind Factory 자동 기획",
        "caption": (
            f"{hook_strategy}\n\n"
            f"오늘의 주제: {title}\n"
            "거창한 변화보다 지금 가능한 10분을 먼저 만드세요.\n"
            "저장해두고 흔들리는 날 다시 꺼내 보세요.\n"
            "댓글에 '오늘의 10분 완료'라고 인증하면 됩니다.\n\n"
            f"{template['tags']}"
        ),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "quality_intent": {
            "pain_words": PAIN_WORDS,
            "action_words": ACTION_WORDS,
            "structure": "pain hook -> cause reframe -> 3-step tips -> identity shift -> challenge CTA",
            "template_title": template["title"],
        },
        "source": {
            "audience_insight": os.path.exists("audience_insight.json"),
            "content_strategy": os.path.exists("content_strategy.json"),
            "self_healing_strategy": bool(healing),
            "template_rotation": True,
        },
        "pages": pages,
    }

    with open("script.json", "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    print(f"✅ generator.py: script.json 생성 완료 ({len(pages)} pages, diversified template: {template['title']})")
    return script


if __name__ == "__main__":
    generate_script(diversify=False)
