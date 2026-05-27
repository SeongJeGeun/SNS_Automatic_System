import json
import os


PAIN_WORDS = [
    "피곤", "무기력", "불안", "자책", "번아웃", "비교", "막막", "무너", "힘들", "지친",
    "시작", "회복", "압박", "뒤처", "침대", "루틴",
]
ACTION_WORDS = ["오늘", "지금", "딱", "하나", "10분", "물", "걷", "쓰기", "끄고", "시작", "루틴"]
SAVE_WORDS = ["저장", "다시", "무너지는 날", "꺼내", "기억", "보라", "보세요"]
ABSTRACT_WORDS = ["성공", "규율", "몰입", "성장", "한계", "자유", "고귀", "재설계"]


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def text_of(page):
    return f"{page.get('heading', '')} {page.get('sub_text', '')}".strip()


def count_matches(text, words):
    return sum(1 for word in words if word in text)


def evaluate_script_quality(
    script_file="script.json",
    strategy_file="content_strategy.json",
    report_file="content_quality_report.json",
    feedback_file="content_quality_feedback.json",
):
    if not os.path.exists(script_file):
        return False

    script = load_json(script_file)
    strategy = load_json(strategy_file) if os.path.exists(strategy_file) else {}
    pages = script.get("pages", [])
    score = 0
    findings = []

    if 5 <= len(pages) <= 10:
        score += 10
    else:
        findings.append("장수는 5~10장이어야 합니다.")

    first_text = text_of(pages[0]) if pages else ""
    first_pain_matches = count_matches(first_text, PAIN_WORDS)
    if first_pain_matches >= 1:
        score += 18
    else:
        findings.append("1장에 독자의 구체적인 고통이 부족합니다.")

    if len(first_text) <= 55:
        score += 8
    else:
        findings.append("1장 문장이 길어 모바일에서 즉시 읽히기 어렵습니다.")

    all_texts = [text_of(page) for page in pages]
    joined = " ".join(all_texts)

    if count_matches(joined, PAIN_WORDS) >= 4:
        score += 14
    else:
        findings.append("전체 흐름에서 현실 고민/감정 단어가 부족합니다.")

    if any(word in joined for word in ["의지", "시스템", "회복", "원인", "문제"]):
        score += 12
    else:
        findings.append("문제 원인을 재정의하는 장면이 약합니다.")

    if count_matches(joined, ACTION_WORDS) >= 3:
        score += 12
    else:
        findings.append("오늘 바로 할 수 있는 행동 제안이 부족합니다.")

    # 5대 공유 요인 추가 검증
    # 중간 장(3~4장) 이타주의 자극 3단계 실천 팁
    mid_pages_text = ""
    if len(pages) >= 4:
        mid_pages_text = " ".join([text_of(pages[2]), text_of(pages[3])])
    elif len(pages) >= 3:
        mid_pages_text = text_of(pages[2])
    
    has_altruistic_tip = any(word in mid_pages_text for word in ["단계", "팁", "방법", "원칙", "요약"])
    if has_altruistic_tip:
        score += 8
    else:
        findings.append("중간 장(3~4장)에 이타주의 자극을 위한 명확한 3단계 실천 팁/요약이 부족합니다.")

    last_text = text_of(pages[-1]) if pages else ""

    # 마지막 장 인증/챌린지 템플릿
    has_status_template = any(word in last_text for word in ["챌린지", "템플릿", "인증", "선언", "기록지", "미션"])
    if has_status_template:
        score += 8
    else:
        findings.append("마지막 장에 라이트 유저의 성취 증명을 돕는 인증/챌린지 템플릿 문구가 누락되었습니다.")

    if count_matches(last_text, SAVE_WORDS) >= 1:
        score += 12
    else:
        findings.append("마지막 장에 저장할 이유나 CTA가 부족합니다.")

    prompts = [page.get("image_prompt", "").strip() for page in pages]
    if all(prompts) and len(set(prompts)) == len(prompts):
        score += 8
    else:
        findings.append("이미지 프롬프트가 비어 있거나 장별 차이가 약합니다.")

    short_pages = [
        page.get("page", index + 1)
        for index, page in enumerate(pages)
        if len(text_of(page)) <= 75
    ]
    if len(short_pages) >= max(1, len(pages) - 1):
        score += 6
    else:
        findings.append("일부 장의 텍스트가 길어 카드뉴스 호흡이 무겁습니다.")

    abstract_count = count_matches(joined, ABSTRACT_WORDS)
    pain_count = count_matches(joined, PAIN_WORDS)
    if abstract_count <= pain_count + 2:
        score += 8
    else:
        findings.append("추상적인 동기부여 단어가 현실 고민보다 많습니다.")

    minimum_score = int(strategy.get("quality_bar", {}).get("minimum_score", 72))
    passed = score >= minimum_score and not any("1장" in item for item in findings[:1])
    report = {
        "score": score,
        "minimum_score": minimum_score,
        "passed": passed,
        "findings": findings,
        "recommendation": build_recommendation(findings),
    }

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if passed:
        if os.path.exists(feedback_file):
            os.remove(feedback_file)
        print(f"[Quality Agent] 통과: {score}/{minimum_score}")
    else:
        with open(feedback_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"[Quality Agent] 미통과: {score}/{minimum_score}")
        for item in findings:
            print(f"  - {item}")

    return passed


def build_recommendation(findings):
    if not findings:
        return "업로드 가능한 수준입니다."
    return (
        "다음 재생성에서는 첫 장을 독자의 현실 고통으로 시작하고, "
        "중간에는 원인 해석을 넣고, 마지막에는 저장할 이유가 있는 구체 행동으로 끝내세요. "
        f"수정 필요: {' / '.join(findings)}"
    )


if __name__ == "__main__":
    evaluate_script_quality()
