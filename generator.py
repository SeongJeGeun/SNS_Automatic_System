import json
import os
import random
import re
from datetime import datetime


PAIN_WORDS = ["피곤", "무기력", "불안", "자책", "번아웃", "비교", "막막", "무너", "힘들", "지친", "압박", "뒤처", "침대", "루틴"]
ACTION_WORDS = ["오늘", "지금", "딱", "하나", "10분", "물", "걷", "쓰기", "끄고", "시작", "루틴"]
CEO_TOPIC_GUIDANCE_FILE = os.path.join("agent_runs", "ceo_topic_guidance.json")
CONTENT_TEMPLATE_PACK_FILE = os.getenv("CONTENT_TEMPLATE_PACK_FILE", os.path.join("templates", "content_topics.json"))

FALLBACK_TEMPLATE_PACK = {
    "version": 0,
    "name": "fallback_content_topics",
    "series_system": {
        "series_name": "마인드팩토리 10분 회복 시리즈",
        "next_episode_label": "다음 편 예고",
        "fixed_cta": "저장해두고 다음에 흔들리는 날 다시 꺼내 보세요.",
    },
    "defaults": {
        "subtitle": "Mind Factory 자동 기획",
        "structure": "pain hook -> cause reframe -> 3-step tips -> identity shift -> challenge CTA",
        "caption_body": [
            "거창한 변화보다 지금 가능한 10분을 먼저 만드세요.",
            "저장해두고 흔들리는 날 다시 꺼내 보세요.",
            "댓글에 '오늘의 10분 완료'라고 인증하면 됩니다.",
        ],
    },
    "templates": [
        {
            "template_id": "small_routine_recovery",
            "topic_keys": ["execution_barrier", "routine_recovery"],
            "series_name": "마인드팩토리 10분 회복 시리즈",
            "weekday_slot": "wed",
            "episode_role": "시작 장벽을 낮추는 실행 편",
            "next_episode_hint": "다음 편에서는 비교 불안이 올라올 때 내 속도로 돌아오는 방법을 다룹니다.",
            "fixed_cta": "댓글에 '10분 시작'이라고 남기고 바로 하나만 실행하세요.",
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
        }
    ],
}


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
    return text[:max_len].rstrip() + "…"


def _load_template_pack():
    pack = _load_json(CONTENT_TEMPLATE_PACK_FILE, None)
    if isinstance(pack, dict) and isinstance(pack.get("templates"), list) and pack["templates"]:
        return pack
    print(f"[Generator] template pack missing or invalid, fallback used: {CONTENT_TEMPLATE_PACK_FILE}")
    return FALLBACK_TEMPLATE_PACK


def _template_defaults(pack):
    defaults = pack.get("defaults") if isinstance(pack, dict) else {}
    return defaults if isinstance(defaults, dict) else {}


def _series_system(pack):
    series = pack.get("series_system") if isinstance(pack, dict) else {}
    fallback = FALLBACK_TEMPLATE_PACK.get("series_system", {})
    return series if isinstance(series, dict) else fallback


def _topic_templates(pack):
    templates = pack.get("templates") if isinstance(pack, dict) else []
    return templates if isinstance(templates, list) and templates else FALLBACK_TEMPLATE_PACK["templates"]


def _page(page, role, heading, sub_text, image_prompt, layout_hint, **extra):
    payload = {
        "page": page,
        "role": role,
        "heading": _clean_sentence(heading, 32),
        "sub_text": _clean_sentence(sub_text, 42),
        "image_prompt": image_prompt,
        "layout_hint": layout_hint,
    }
    payload.update({k: v for k, v in extra.items() if v not in (None, "")})
    return payload


def _load_ceo_topic_guidance():
    guidance = _load_json(CEO_TOPIC_GUIDANCE_FILE, {})
    if isinstance(guidance, dict) and guidance.get("topic_key"):
        return guidance
    return {}


def _template_for_guidance(templates, guidance):
    topic_key = guidance.get("topic_key")
    if not topic_key:
        return None
    for template in templates:
        if topic_key in template.get("topic_keys", []):
            return template
    return None


def _select_template(pack, strategy, audience, diversify):
    guidance = _load_ceo_topic_guidance()
    templates = _topic_templates(pack)
    guided_template = _template_for_guidance(templates, guidance)
    if guided_template:
        print(f"[Generator] CEO topic guidance applied: {guidance.get('topic_title')}")
        return guided_template, guidance

    seed_basis = "|".join([
        datetime.now().strftime("%Y%m%d%H"),
        _as_text(strategy.get("theme") if isinstance(strategy, dict) else ""),
        _as_text(strategy.get("topic") if isinstance(strategy, dict) else ""),
        _as_text(audience.get("story_angle") if isinstance(audience, dict) else ""),
        str(os.getenv("JOB_ID", "")),
        "diversify" if diversify else "normal",
    ])
    rng = random.Random(seed_basis)
    return rng.choice(templates), guidance


def _series_metadata(pack, template):
    series = _series_system(pack)
    return {
        "series_name": _as_text(template.get("series_name"), _as_text(series.get("series_name"), "마인드팩토리 10분 회복 시리즈")),
        "weekday_slot": _as_text(template.get("weekday_slot"), ""),
        "episode_role": _as_text(template.get("episode_role"), ""),
        "next_episode_hint": _as_text(template.get("next_episode_hint"), ""),
        "fixed_cta": _as_text(template.get("fixed_cta"), _as_text(series.get("fixed_cta"), "")),
        "next_episode_label": _as_text(series.get("next_episode_label"), "다음 편 예고"),
    }


def _build_pages(template, series_meta=None):
    series_meta = series_meta or {}
    series_badge = series_meta.get("series_name")
    episode_role = series_meta.get("episode_role")
    next_episode_hint = series_meta.get("next_episode_hint")
    fixed_cta = series_meta.get("fixed_cta")
    next_label = series_meta.get("next_episode_label", "다음 편 예고")

    page1_sub = template["pain_sub"]
    if episode_role:
        page1_sub = f"{episode_role} · {template['pain_sub']}"

    page7_sub = template["cta_sub"]
    if fixed_cta:
        page7_sub = fixed_cta
    if next_episode_hint:
        page7_sub = f"{page7_sub} / {next_label}: {next_episode_hint}"

    return [
        _page(1, "pain_hook", template["pain_heading"], page1_sub, "dark phone glow, tired young adult, anxiety mood, Korean Instagram headline space, small series badge at top", "series badge top, large bottom headline with small top label", series_badge=series_badge, episode_role=episode_role),
        _page(2, "cause_reframe", template["reframe_heading"], template["reframe_sub"], "minimal desk, scattered notes, broken routine symbols, muted blue gray tone", "split layout: problem label left, explanation box right"),
        _page(3, "three_step_tip_1", template["tip_heading"], template["tip_sub"], "three numbered cards, water glass, phone off icon, pen and notebook, clean contrast", "three stacked tip boxes with big numbers"),
        _page(4, "three_step_tip_2", template["summary_heading"], template["summary_sub"], "walking shoes at door, simple checklist, warm light, recovery and routine mood", "summary card with checklist bullets"),
        _page(5, "identity_shift", template["identity_heading"], template["identity_sub"], "open window, calm morning light, notebook with routine grid, hopeful mood", "quote-centered layout with subtle frame"),
        _page(6, "micro_action", template["action_heading"], template["action_sub"], "bold checklist template, pen tick mark, minimal black and cream Instagram design", "template style with blank line for user action"),
        _page(7, "save_cta", template["cta_heading"], page7_sub, "challenge completion card, stamp icon, save reminder, strong CTA, Korean social media post, next episode teaser", "final CTA card with save icon, comment prompt, and next episode teaser", series_badge=series_badge, next_episode_hint=next_episode_hint, fixed_cta=fixed_cta),
    ]


def _caption_body(defaults):
    body = defaults.get("caption_body") if isinstance(defaults, dict) else []
    if isinstance(body, list) and body:
        return "\n".join(_as_text(line) for line in body)
    return "거창한 변화보다 지금 가능한 10분을 먼저 만드세요.\n저장해두고 흔들리는 날 다시 꺼내 보세요."


def _series_caption_block(meta):
    lines = []
    if meta.get("series_name"):
        lines.append(f"시리즈: {meta['series_name']}")
    if meta.get("episode_role"):
        lines.append(f"이번 편: {meta['episode_role']}")
    if meta.get("fixed_cta"):
        lines.append(meta["fixed_cta"])
    if meta.get("next_episode_hint"):
        lines.append(f"{meta.get('next_episode_label', '다음 편 예고')}: {meta['next_episode_hint']}")
    return "\n".join(lines)


def generate_script(diversify=False):
    pack = _load_template_pack()
    defaults = _template_defaults(pack)
    audience = _load_json("audience_insight.json", {})
    strategy = _load_json("content_strategy.json", {})
    healing = _load_json("self_healing_strategy.json", {}) if diversify else {}
    template, ceo_guidance = _select_template(pack, strategy, audience, diversify)

    theme = _pick_first(strategy, ["theme", "topic", "next_direction"], template["title"])
    hook_strategy = _pick_first(strategy, ["hook", "hook_strategy", "headline"], template["reframe_sub"])

    if ceo_guidance.get("topic_title"):
        title = _clean_sentence(ceo_guidance["topic_title"], 34)
    elif theme == "규율이라는 고귀한 속박":
        title = template["title"]
    else:
        title = _clean_sentence(theme, 34)

    if healing:
        title = template["title"]

    series_meta = _series_metadata(pack, template)
    pages = _build_pages(template, series_meta)
    structure = defaults.get("structure", FALLBACK_TEMPLATE_PACK["defaults"]["structure"])
    subtitle = defaults.get("subtitle", "Mind Factory 자동 기획")
    series_caption = _series_caption_block(series_meta)

    script = {
        "title": title,
        "subtitle": subtitle,
        "series": series_meta,
        "caption": (
            f"{hook_strategy}\n\n"
            f"오늘의 주제: {title}\n"
            f"{_caption_body(defaults)}\n\n"
            f"{series_caption}\n\n"
            f"{template['tags']}"
        ),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "quality_intent": {
            "pain_words": PAIN_WORDS,
            "action_words": ACTION_WORDS,
            "structure": structure,
            "template_id": template.get("template_id"),
            "template_title": template["title"],
            "series_name": series_meta.get("series_name"),
            "episode_role": series_meta.get("episode_role"),
            "ceo_topic_key": ceo_guidance.get("topic_key"),
            "ceo_emotion_axis": ceo_guidance.get("emotion_axis"),
        },
        "source": {
            "audience_insight": os.path.exists("audience_insight.json"),
            "content_strategy": os.path.exists("content_strategy.json"),
            "self_healing_strategy": bool(healing),
            "template_rotation": True,
            "template_pack_file": CONTENT_TEMPLATE_PACK_FILE,
            "template_pack_name": pack.get("name"),
            "template_pack_version": pack.get("version"),
            "ceo_topic_guidance": bool(ceo_guidance),
        },
        "pages": pages,
    }

    with open("script.json", "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    print(f"✅ generator.py: script.json 생성 완료 ({len(pages)} pages, template pack: {pack.get('name')}, template: {template['title']})")
    return script


if __name__ == "__main__":
    generate_script(diversify=False)
