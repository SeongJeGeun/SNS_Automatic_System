import json
import os
from collections import Counter

PERFORMANCE_LOG = os.path.join("shared", "performance_log.json")
CONTENT_STRATEGY_FILE = "content_strategy.json"
SCRIPT_FILE = "script.json"
PAIN_WORDS = (
    "불안",
    "무기력",
    "번아웃",
    "자책",
    "비교",
    "막막",
    "고통",
    "피곤",
    "무너",
    "힘든",
)

# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────

def main():
    result = update_strategy_from_performance()
    if result["updated"]:
        print(
            "[Performance Strategy] 성과 로그 기반 전략 반영 완료: "
            f"TOP {result['top_count']}건 / MID {result['mid_count']}건 / LOW {result['low_count']}건"
        )
    else:
        print(f"[Performance Strategy] 전략 반영 생략: {result['reason']}")
    return result


# ──────────────────────────────────────────────
# 핵심 공개 함수
# ──────────────────────────────────────────────

def update_strategy_from_performance(
    performance_log_path=PERFORMANCE_LOG,
    strategy_path=CONTENT_STRATEGY_FILE,
    script_path=SCRIPT_FILE,
):
    logs = load_json(performance_log_path, default=[])
    if not isinstance(logs, list) or not logs:
        return {"updated": False, "reason": "performance_log.json 데이터 없음"}

    # 1. content_score 계산 및 3등급 분류
    scored = [_with_score(post) for post in logs]
    graded = assign_grades(scored)

    # 2. performance_log.json에 content_score / grade 기입 후 저장
    save_scored_logs(performance_log_path, graded)

    # 3. 등급별 분리
    top_posts  = [p for p in graded if p["grade"] == "TOP"]
    low_posts  = [p for p in graded if p["grade"] == "LOW"]

    fallback_script = load_json(script_path, default={})
    top_patterns = [extract_post_pattern(p, fallback_script) for p in top_posts]
    low_patterns = [extract_post_pattern(p, fallback_script) for p in low_posts]

    # 4. content_strategy.json 업데이트
    strategy = load_json(strategy_path, default={})
    if not isinstance(strategy, dict):
        strategy = {}

    # TOP → 전략 업데이트 (최대 5개)
    strategy["best_hook_patterns"] = unique_non_empty(
        p["first_heading"] for p in top_patterns
    )[:5]

    strategy["best_card_count"] = most_common_value(
        p["card_count_bucket"] or p["card_count"] for p in top_patterns
    )

    strategy["proven_cta_phrases"] = unique_non_empty(
        p["cta_phrase"] for p in top_patterns
    )[:5]

    # LOW → avoid 리스트 (low_hook_patterns 포함)
    avoid_items = list(strategy.get("avoid", []))
    new_avoids = build_avoid_items(low_patterns)
    for item in new_avoids:
        if item not in avoid_items:
            avoid_items.append(item)
    strategy["avoid"] = avoid_items

    # LOW 훅 패턴 별도 저장
    strategy["low_hook_patterns"] = unique_non_empty(
        p["first_heading"] for p in low_patterns
    )[:5]

    # 성과 학습 메타 정보
    if top_posts:
        top_threshold = to_float(min(p["content_score"] for p in top_posts))
    else:
        top_threshold = 0.0
    if low_posts:
        low_threshold = to_float(max(p["content_score"] for p in low_posts))
    else:
        low_threshold = 0.0

    strategy["performance_learning"] = {
        "scoring_formula": "save_rate×0.5 + share_rate×0.3 + engagement_rate×0.2",
        "grade_rule": "TOP: 상위 20% / MID: 중간 60% / LOW: 하위 20%",
        "top_score_threshold": round(top_threshold, 6),
        "low_score_threshold": round(low_threshold, 6),
        "top_count": len(top_posts),
        "mid_count": len(graded) - len(top_posts) - len(low_posts),
        "low_count": len(low_posts),
        "top_patterns": top_patterns,
        "low_patterns": low_patterns,
    }

    save_json(strategy_path, strategy)
    return {
        "updated": True,
        "top_count": len(top_posts),
        "mid_count": len(graded) - len(top_posts) - len(low_posts),
        "low_count": len(low_posts),
    }


# ──────────────────────────────────────────────
# content_score 계산 및 등급 분류
# ──────────────────────────────────────────────

def compute_content_score(post):
    """content_score = save_rate×0.5 + share_rate×0.3 + engagement_rate×0.2"""
    save_rate       = to_float(post.get("save_rate", 0))
    share_rate      = to_float(post.get("share_rate", 0))
    engagement_rate = to_float(post.get("engagement_rate", 0))
    return round(save_rate * 0.5 + share_rate * 0.3 + engagement_rate * 0.2, 6)


def _with_score(post):
    """post dict에 content_score를 추가해 반환 (원본 변경 없음)."""
    entry = dict(post)
    entry["content_score"] = compute_content_score(post)
    return entry


def assign_grades(scored_posts):
    """
    content_score 기준으로 3등급 분류.
    - TOP : 상위 20%
    - LOW : 하위 20%
    - MID : 나머지 60%
    """
    if not scored_posts:
        return []

    ranked = sorted(scored_posts, key=lambda p: p["content_score"], reverse=True)
    n = len(ranked)
    top_cutoff = max(1, round(n * 0.2))
    low_cutoff = max(1, round(n * 0.2))

    result = []
    for i, post in enumerate(ranked):
        entry = dict(post)
        if i < top_cutoff:
            entry["grade"] = "TOP"
        elif i >= n - low_cutoff:
            entry["grade"] = "LOW"
        else:
            entry["grade"] = "MID"
        result.append(entry)
    return result


def save_scored_logs(performance_log_path, graded_posts):
    """
    graded_posts의 content_score / grade를 원본 performance_log.json에 upsert.
    post_id 기준으로 매칭해 덮어쓴다.
    """
    score_map = {
        str(p.get("post_id", "")): {
            "content_score": p["content_score"],
            "grade": p["grade"],
        }
        for p in graded_posts
        if p.get("post_id")
    }

    existing = load_json(performance_log_path, default=[])
    if not isinstance(existing, list):
        existing = []

    updated = []
    for post in existing:
        pid = str(post.get("post_id", ""))
        entry = dict(post)
        if pid in score_map:
            entry.update(score_map[pid])
        updated.append(entry)

    save_json(performance_log_path, updated)


# ──────────────────────────────────────────────
# 패턴 추출
# ──────────────────────────────────────────────

def extract_post_pattern(post, fallback_script):
    script = extract_script_payload(post) or fallback_script or {}
    pages = post.get("pages") or (script.get("pages", []) if isinstance(script, dict) else [])
    first_page = pages[0] if pages else {}
    last_page  = pages[-1] if pages else {}

    first_heading = str(
        post.get("first_heading")
        or post.get("heading")
        or first_page.get("heading")
        or ""
    ).strip()

    cta_phrase = str(
        post.get("cta_phrase")
        or post.get("cta")
        or last_page.get("sub_text")
        or last_page.get("heading")
        or ""
    ).strip()

    card_count = to_int(post.get("card_count") or len(pages))

    return {
        "post_id":                    str(post.get("post_id", "")),
        "platform":                   str(post.get("platform", "")),
        "content_score":              to_float(post.get("content_score", 0)),
        "grade":                      str(post.get("grade", "")),
        "save_rate":                  to_float(post.get("save_rate", 0)),
        "share_rate":                 to_float(post.get("share_rate", 0)),
        "engagement_rate":            to_float(post.get("engagement_rate", 0)),
        "first_heading":              first_heading,
        "first_heading_has_pain_word": has_pain_word(first_heading),
        "first_heading_length":       len(first_heading),
        "card_count":                 card_count,
        "card_count_bucket":          card_count_bucket(card_count),
        "theme_color":                str(post.get("theme_color") or first_page.get("theme_color") or "").strip(),
        "cta_phrase":                 cta_phrase,
    }


def extract_script_payload(post):
    for key in ("script", "script_data", "content_script"):
        payload = post.get(key)
        if isinstance(payload, dict):
            return payload

    script_path = post.get("script_path")
    if script_path:
        payload = load_json(str(script_path), default={})
        if isinstance(payload, dict):
            return payload
    return {}


def build_avoid_items(low_patterns):
    """LOW 포스트에서 피해야 할 패턴을 avoid 문구로 변환."""
    avoid_items = []
    for pattern in low_patterns:
        heading = pattern.get("first_heading")
        if heading:
            avoid_items.append(f"성과 낮은 훅 패턴 반복 금지 (low_hook_pattern): {heading}")

        cta_phrase = pattern.get("cta_phrase")
        if cta_phrase:
            avoid_items.append(f"성과 낮은 CTA 반복 금지: {cta_phrase}")

        theme_color = pattern.get("theme_color")
        if theme_color:
            avoid_items.append(f"성과 낮은 theme_color 조합 주의: {theme_color}")
    return avoid_items


# ──────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────

def has_pain_word(text):
    return any(word in text for word in PAIN_WORDS)


def card_count_bucket(card_count):
    if 5 <= card_count <= 7:
        return "5~7장"
    if 8 <= card_count <= 10:
        return "8~10장"
    if card_count > 0:
        return f"{card_count}장"
    return ""


def most_common_value(values):
    filtered = [value for value in values if value]
    if not filtered:
        return ""
    return Counter(filtered).most_common(1)[0][0]


def unique_non_empty(values):
    result = []
    seen = set()
    for value in values:
        value = str(value or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def load_json(path, default=None):
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Warning] JSON 로드 실패 ({path}): {e}")
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def to_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def to_float(value):
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    main()
