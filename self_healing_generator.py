"""Self-Healing Content Generator with Obsidian context flag support.

Batch 32 — obsidian_context_enabled wired from content_strategy.json
----------------------------------------------------------------------
``main()`` now reads ``obsidian_context_enabled`` from ``content_strategy.json``
(written by ``content_strategy.py`` when strategy_mode == "reinforce_theme").

If the flag is True:
- RAG search query is enriched with theme-continuity keywords.
- An additional prompt block (``[OBSIDIAN_REINFORCE]``) is injected between
  the strategy context and the Obsidian RAG section, requesting the model to
  reinforce theme continuity and cross-reference stored note themes.

If the flag is False or absent:
- Behaviour is unchanged from the previous version.

All enrichment is **non-blocking**: any exception in the enrichment path
is swallowed and the generator falls back to its existing prompt construction.

TODO (Batch 33+): Replace ``_build_obsidian_reinforce_block()`` static note
    injection with direct Obsidian vault retrieval using the previous job's
    ``script.json`` title as the RAG query, so the model receives actual
    prior-content excerpts rather than a general continuity directive.
TODO (Batch 33+): Expose ``obsidian_context_enabled`` status in the
    ``agent_status.json`` heartbeat for dashboard visibility.
"""

import os
import sys
import json
from dotenv import load_dotenv
from google_sheet_manager import GoogleSheetManager
from constants import MINDSET_PHILOSOPHY, COVER_HOOK_RULES, OBSIDIAN_VAULT_PATH
from obsidian_rag import ObsidianRAGEngine
from codex_text_bridge import read_json_response, write_story_request

# 환경 변수 로드
load_dotenv()


# ---------------------------------------------------------------------------
# Batch 32: obsidian_context_enabled helpers (non-blocking)
# ---------------------------------------------------------------------------

def _load_obsidian_context_flag(strategy_file: str = "content_strategy.json") -> bool:
    """Read ``obsidian_context_enabled`` from *strategy_file*.

    Returns ``True`` only when the flag is explicitly ``True`` (bool).
    Missing file, parse error, or any other value → ``False`` (current
    behaviour preserved).

    Non-blocking: all exceptions are caught and logged.

    TODO (Batch 33+): Accept an explicit job-scoped path so this works
        correctly when strategy artifacts are stored under ``jobs/[JOB_ID]/``.
    """
    try:
        with open(strategy_file, "r", encoding="utf-8") as f:
            strategy = json.load(f)
        flag = strategy.get("obsidian_context_enabled", False)
        return flag is True
    except FileNotFoundError:
        return False
    except Exception as exc:
        print(f"[Warning] obsidian_context_enabled 플래그 읽기 실패 (non-blocking): {exc}")
        return False


def _enrich_rag_query(base_query: str) -> str:
    """Return a theme-continuity-enriched RAG query when reinforce_theme is active.

    Appends continuity-relevant Korean terms so the RAG engine surfaces notes
    that overlap with the previous content series rather than purely
    recency-ranked results.

    TODO (Batch 33+): Read the previous ``script.json`` title dynamically
        instead of appending static terms.
    """
    continuity_terms = "시리즈 연속 주제 강화 이전 카드뉴스 연결"
    return f"{base_query} {continuity_terms}"


def _build_obsidian_reinforce_block(obsidian_context: str) -> str:
    """Build a deterministic prompt block requesting theme continuity.

    The block is inserted *before* the Obsidian RAG section in the main prompt
    so the model is explicitly primed to treat the RAG excerpts as a
    theme-continuity anchor rather than a fresh inspiration source.

    Parameters
    ----------
    obsidian_context:
        The RAG-retrieved Obsidian excerpt string (may be empty).

    Returns
    -------
    str
        A formatted prompt block. Returns an empty string if
        *obsidian_context* is empty, to avoid injecting a useless section.

    TODO (Batch 33+): Include the previous job's ``title`` field from
        ``script.json`` so the model has an explicit anchor phrase.
    """
    if not obsidian_context or not obsidian_context.strip():
        return ""

    return """
======================================================
🔁 [OBSIDIAN_REINFORCE] 테마 연속성 강화 지침 (strategy_mode=reinforce_theme)
이번 카드뉴스는 이전 시리즈의 핵심 주제를 동일 관점에서 심화하는 연속 편입니다.
아래 지침을 반드시 준수하세요:
1. 이전 시리즈에서 사용된 주제 키워드(규율, 몰입, 번아웃, 시스템 등)를 이번 기획에도
   핵심 어조로 유지하되, 동일 문장을 그대로 반복하지 말고 새로운 각도에서 재해석하세요.
2. 옵시디언 메모(아래 RAG 결과)를 이전 시리즈의 철학적 맥락 확장에 우선 활용하세요.
   신선한 인사이트를 추가하되, 브랜드 톤앤매너의 일관성을 최우선으로 유지하세요.
3. 1장 훅은 이전 시리즈를 이미 본 독자가 '오, 다음 편이구나'라고 느낄 수 있는
   연속성 있는 표현으로 열되, 처음 보는 독자도 즉시 공감할 수 있는 보편적 고통으로
   시작해야 합니다.
======================================================
"""


# ---------------------------------------------------------------------------
# Original helpers (unchanged from pre-Batch-32)
# ---------------------------------------------------------------------------

def build_fallback_script(obsidian_context):
    """RAG 맥락을 덧댄 정체성 높은 폴백 script.json 작성 (7장 분량의 고급 매거진 스타일)"""
    print("[Self-Healing] 외부 API 장애 또는 제한을 감지하여 로컬 자가 복구 메커니즘을 가동합니다...")

    fallback_data = {
      "title": "규율이라는 고귀한 속박",
      "pages": [
        {
          "page": 1,
          "image_prompt": "Minimalist photography of a single glowing gold line running across a matte black texture, high contrast, elegant serif font feeling, silent atmosphere, low saturation, no text",
          "heading": "무기력과 번아웃의 늪",
          "sub_text": "침대 위에서 느끼는 비교와 자책의 피로감.",
          "theme_color": "deep_navy"
        },
        {
          "page": 2,
          "image_prompt": "High-end editorial black and white photo of structured stone pillars standing firm against foggy wind, low saturation, high grain, architectural harmony, no text",
          "heading": "의지가 아닌 시스템의 문제",
          "sub_text": "원인을 찾으려 힘쓰지 마라. 무너진 일상을 회복하는 시스템을 설계하라.",
          "theme_color": "slate_gray"
        },
        {
          "page": 3,
          "image_prompt": "Minimalist study room with deep navy walls, wooden desk with a single focused vintage lamp illuminating an open book, elegant, quiet, gold point, no text",
          "heading": "회복을 위한 3단계 몰입 방법",
          "sub_text": "첫째, 스마트폰을 끄고 지금 할 일 딱 하나에만 10분간 걷기든 쓰기든 시작하라.",
          "theme_color": "cream"
        },
        {
          "page": 4,
          "image_prompt": "Low key low saturation photography of a person's hands carving wood or stone, fine details, focus, craftsmanship, dark slate gray tones, no text",
          "heading": "불편함을 마주하는 원칙",
          "sub_text": "오늘 회피한 그 고통은 내일 당신의 한계를 가두는 벽이 된다.",
          "theme_color": "deep_navy"
        },
        {
          "page": 5,
          "image_prompt": "Fine art black and white photo of an empty path disappearing into misty trees, high texture, premium mood, silent, no text",
          "heading": "가장 확실한 멘탈 루틴",
          "sub_text": "지금 당장 찬물 한 잔을 마셔라. 신체의 각성이 뇌의 각성을 시작한다.",
          "theme_color": "cream"
        },
        {
          "page": 6,
          "image_prompt": "A sharp beam of light cutting through a dark concrete space, minimal composition, slate gray and cold light, premium architectural photography, no text",
          "heading": "규율이 만드는 고유한 자유",
          "sub_text": "스스로를 통제할 때 지친 멘탈은 가장 단단하게 단련된다.",
          "theme_color": "slate_gray"
        },
        {
          "page": 7,
          "image_prompt": "Deep navy background with a thin gold geometric frame at the center, highly elegant and premium magazine layout, gold accents, no text",
          "heading": "나의 규율 선언 템플릿",
          "sub_text": "이 가이드를 저장하고, 삶이 무너지는 날 꺼내어 다시 기억해 보세요.",
          "theme_color": "deep_navy"
        }
      ]
    }
    return fallback_data

def load_audience_insight():
    insight_file = "audience_insight.json"
    if not os.path.exists(insight_file):
        return ""
    try:
        with open(insight_file, "r", encoding="utf-8") as f:
            insight = json.load(f)
        return json.dumps(insight, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Warning] audience_insight.json 로드 실패: {e}")
        return ""

def load_optional_json_context(path, label):
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"\n[{label}] 이전 단계 산출물을 대본 기획에 반영합니다.")
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Warning] {path} 로드 실패: {e}")
        return ""

def main():
    print("="*60)
    print(" MindFactory Self-Healing Content Generator (Obsidian RAG V4) ")
    print("="*60)

    # 1. 브랜드 철학 로드
    print("\n[Step 1] 마인드팩토리 고유 철학 가이드 로드 중...")
    philosophy_str = json.dumps(MINDSET_PHILOSOPHY, ensure_ascii=False, indent=2)
    hook_rules_str = json.dumps(COVER_HOOK_RULES, ensure_ascii=False, indent=2)

    # 2. 구글 시트 성과 데이터 추출
    gsm = GoogleSheetManager()

    print("\n[Step 2] 구글 시트 성과 지표(상/하위 3개) 분석 중...")
    top_posts = gsm.get_top_posts(limit=3)
    bottom_posts = gsm.get_bottom_posts(limit=3)

    top_context = ""
    print("  - 성공 사례 (상위 조회수):")
    for idx, post in enumerate(top_posts, start=1):
        print(f"    {idx}. {post.get('타이틀')} (조회수: {post.get('조회수')}회)")
        top_context += f"제목: {post.get('타이틀')} / 본문: {post.get('본문내용')} (조회수: {post.get('조회수')}회)\n"

    bottom_context = ""
    print("  - 실패 사례 (하위 조회수):")
    for idx, post in enumerate(bottom_posts, start=1):
        print(f"    {idx}. {post.get('타이틀')} (조회수: {post.get('조회수')}회)")
        bottom_context += f"제목: {post.get('타이틀')} / 본문: {post.get('본문내용')} (조회수: {post.get('조회수')}회)\n"

    # 3. [NEW] 옵시디언 로컬 보관소 RAG 정보 조회
    print("\n[Step 3] 옵시디언 뇌(RAG) 검색 가동...")
    # 조회수 1위 성공 사례 타이틀 키워드를 쿼리로 사용해 내 생각 노트를 역추적 검색
    search_query = "규율 성장 몰입"
    if top_posts:
        search_query = top_posts[0].get("타이틀", "규율 성장 몰입")

    # ------------------------------------------------------------------
    # Batch 32: read obsidian_context_enabled flag (non-blocking)
    # ------------------------------------------------------------------
    obsidian_context_enabled = _load_obsidian_context_flag()

    if obsidian_context_enabled:
        # Enrich the RAG query with theme-continuity terms so the retrieval
        # engine surfaces notes relevant to the prior content series.
        enriched_query = _enrich_rag_query(search_query)
        print(
            f"  - [reinforce_theme] obsidian_context_enabled=True: "
            f"RAG 쿼리 강화 적용 → '{enriched_query}'"
        )
        search_query = enriched_query

    rag = ObsidianRAGEngine(vault_path=OBSIDIAN_VAULT_PATH)
    obsidian_context = rag.retrieve_context(search_query, k=3)

    if obsidian_context:
        print("  - 유사도 검색 완료! 매칭된 생각 노트 컨텍스트 확보.")
    else:
        print("  - [Info] 검색 결과가 비어 있거나 로컬 경로 부재로 RAG 컨텍스트를 스킵합니다.")

    # ------------------------------------------------------------------
    # Batch 32: build reinforce-theme context block (non-blocking)
    # ------------------------------------------------------------------
    obsidian_reinforce_block = ""
    if obsidian_context_enabled:
        try:
            obsidian_reinforce_block = _build_obsidian_reinforce_block(obsidian_context)
            if obsidian_reinforce_block:
                print("  - [reinforce_theme] 테마 연속성 강화 프롬프트 블록 생성 완료.")
        except Exception as exc:
            print(f"[Warning] reinforce 블록 생성 실패 (non-blocking): {exc}")
            obsidian_reinforce_block = ""

    # ------------------------------------------------------------------
    # Batch 33: patch job status with obsidian_context_enabled (non-blocking)
    # ------------------------------------------------------------------
    try:
        from agent_status_writer import update_job_status
        from artifact_mirror import resolve_job_artifact_root
        _job_root = resolve_job_artifact_root()
        update_job_status(
            _job_root.root,
            {
                "obsidian_context_enabled": obsidian_context_enabled,
                "story_agent_stage": "prompt_assembly",
            },
        )
    except Exception as _exc:
        print(f"[Warning] story agent status 업데이트 실패 (non-blocking): {_exc}")

    # 3.5 [NEW] 자가치유 피드백 분석 보고서 로드
    strategy_context = ""
    strategy_file = "self_healing_strategy.json"
    if os.path.exists(strategy_file):
        try:
            with open(strategy_file, "r", encoding="utf-8") as sf:
                strategy_data = json.load(sf)
            analysis = strategy_data.get("analysis", "")
            action_items = strategy_data.get("action_items", "")
            prompt_injection = strategy_data.get("prompt_injection", "")

            print(f"\n🧠 [자가치유 연동] 직전 피드백 분석 결과가 있습니다. 대본 기획에 강제 반영합니다.")
            print(f"  - 저조 원인 분석: {analysis}")
            print(f"  - 개선 액션 아이템: {action_items}")

            strategy_context = f"""
======================================================
🚨 [실시간 자가치유 피드백 개선 지침]
- 직전 피드 성과 분석 결과: {analysis}
- 극복을 위한 개선 액션 아이템: {action_items}
- 이번 기획에 무조건 반영해야 하는 강제 프롬프트 지침: {prompt_injection}
======================================================
"""
        except Exception as se_err:
            print(f"[Warning] 자가치유 전략 파일 로드 실패: {se_err}")

    audience_context = load_audience_insight()
    if audience_context:
        print("\n[Audience Agent] 사람들의 현재 고민/감정 인사이트를 대본 기획에 반영합니다.")

    strategy_context_json = load_optional_json_context("content_strategy.json", "Strategy Agent")
    quality_feedback_context = load_optional_json_context("content_quality_feedback.json", "Quality Agent")

    # 4. 데이터 + 옵시디언 뇌(RAG) 기반 프롬프트 조립
    # obsidian_reinforce_block is "" when obsidian_context_enabled is False,
    # so inserting it is always safe and produces no diff in the default path.
    prompt = f"""너는 인스타그램에서 조회수를 폭발시키는 마인드팩토리의 수석 카피라이터이자 대본 기획자야.
우리의 핵심 브랜드 마인드셋 철학과 가이드라인은 다음과 같아:
{philosophy_str}

그리고 1장 표지 작성 시 무조건 반영해야 하는 '표지 어그로 및 비주얼 훅 규칙'은 다음과 같아:
{hook_rules_str}
{strategy_context}
이번 카드뉴스를 만들기 전에 반드시 먼저 이해해야 하는 '요즘 사람들이 실제로 힘들어하는 삶의 상태' 분석이야:
======================================================
{audience_context}
======================================================
이 인사이트를 바탕으로 독자가 "내 이야기다"라고 느끼게 만들어야 해.
단순한 팩폭이나 훈계가 아니라, 공감 -> 문제 정의 -> 관점 전환 -> 작게 실천할 행동 -> 저장 유도 순서의 스토리텔링을 구성해.
위로와 동기부여의 비율은 4:6으로 유지하고, 사람을 비난하지 말고 무너진 시스템을 다시 세우는 방향으로 설계해.

★ [CRITICAL] 5대 공유 동기 및 조절 효과 공식 상시 연동 지침 ★
카드뉴스를 기획할 때 아래의 심리학/마케팅 학술 데이터 기반 공유 동기를 강력하게 저격하여 기획해야 해:
1. 자기표현(β=0.48) & 사회연결(β=0.30) 최우선 자극:
   - 독자가 이 글을 저장하거나 공유함으로써 "나 이렇게 치열하게 살고 있어, 나 이런 가치관을 가진 사람이야"라는 정체성을 주변에 세련되게 전달할 수 있도록 카피를 구성해라.
   - 빽빽하고 유치한 설명조를 철저히 배제하고, 여백과 명조체 기반의 깊이 있고 울림이 있는 문학적/철학적 카피를 완성해라.
2. 남성 타겟 ➔ '자기표현' 소구:
   - 남성은 자기표현 동기가 만족도에 가장 강한 영향을 미친다. 마인드팩토리의 '규율/몰입/멘탈팩폭' 주제를 다룰 때 남성 타겟이 스스로의 굳건한 정체성을 표출하고 싶게끔 어조를 한층 매섭고 묵직하며 날카롭게 유지해라.
3. 라이트 유저(Light User) ➔ '지위 추구' 소구:
   - 게시물을 자주 올리지 않는 라이트 유저들은 자신의 성취나 사회적 지위를 은근히 과시하고 싶을 때만 엄선하여 공유한다.
   - 이를 위해 카드뉴스 마지막 페이지(마지막 장)에 독자의 성취와 지위를 증명할 수 있는 인증 템플릿(예: "오늘의 몰입 시간 기록지", "나의 규율 선언 템플릿", "100일 챌린지 양식")이나 챌린지 요소를 대본과 디자인 지침에 반드시 반영해라.
4. 헤비 유저(Heavy User) ➔ '이타주의' 자극:
   - 공유 빈도가 높은 헤비 유저들은 타인에게 실질적인 도움을 주는 이타주의적 가치에 공유 만족을 느낀다.
   - 카드뉴스 중간 단계(예: 3장~4장)에 독자들이 다른 사람에게 '당장 알려주고 싶을 만한' 실질적인 성장 및 몰입 팁을 명확한 '3단계 실천 요약' 등의 형태로 구체적으로 제시해라.
5. 오락성 배제 및 깊이 있는 서사:
   - 가벼운 유머나 오락성(β=0.03)은 구전 효과가 전혀 없다. 따라서 네온이나 화려하고 가벼운 디자인 배색을 지양하고 깊이 있는 서사 구조를 사수해라.

위 5가지 학술 지침을 전체 장(페이지)의 흐름에 유기적으로 녹여내서 기획할 것!

이번 카드뉴스의 전략 문서야. 이 구조를 반드시 따라:
======================================================
{strategy_context_json}
======================================================

이전 생성물이 품질 검사에서 탈락했다면 아래 피드백을 반드시 고쳐:
======================================================
{quality_feedback_context}
======================================================
{obsidian_reinforce_block}
여기에 더해, 우리가 이 대본을 작성할 때 반드시 참고하고 녹여내야 하는 질문자님의 '실제 생각 노트(Obsidian RAG)' 내용들이야:
======================================================
{obsidian_context}
======================================================
위 질문자님의 고유 옵시디언 메모 내용을 100% 흡수하고 독창적으로 재해석해서, 뻔한 이야기가 아닌 질문자님 고유의 통찰이 듬뿍 담긴 마인드팩토리의 카드뉴스 대본을 기획해줘.

너는 과거에 제작했던 카드뉴스 중 성공했던 사례와 실패했던 사례를 분석해서 스스로 피드백 루프를 적용해야 해.

[과거 분석 데이터]
* 성공작 (계승해야 할 화풍 및 카피라이팅 방식):
{top_context}

* 실패작 (가독성이 떨어지거나 뻔해서 피해 가야 할 내용):
{bottom_context}

[대본 작성 및 디자인 규칙]
1. 주제 및 장수 기획: 오디언스 인사이트, 마인드팩토리 고유 철학, 옵시디언 메모, 최신 트렌드 맥락을 결합해 **5장 이상 10장 이하(5~10장 사이, 인스타그램 API 제한으로 인해 절대 10장을 초과하면 안 됨)**의 카드뉴스 대본을 기획할 것.
   - 1장: 독자의 현재 삶과 고통을 정확히 찌르는 공감형 후킹
   - 2~3장: 왜 무너지는지 원인 해석 및 헤비 유저를 저격하는 이타주의적 3단계 실천 요약 팁 제시
   - 중간 장: 관점 전환 및 동기부여
   - 마지막 장: 라이트 유저의 지위 추구와 성취 증명을 돕는 인증/챌린지 템플릿(글귀)과 저장하고 다시 볼 수 있는 구체적 행동/루틴 제안
2. 비주얼 톤앤매너 (Sophisticated Storytelling):
   - 자극적인 네온 핑크, 네온 그린, 원색 위주의 가벼운 배색 절대 금지.
   - Deep Navy (#0F172A), Slate Gray (#334155), Cream (#F8FAF0)을 주력 배경 색상으로 설정.
   - 포인트 컬러는 신뢰감을 주는 Muted Blue 또는 Gold 계열로 극히 절제하여 사용.
   - 이미지 묘사(image_prompt)는 글귀의 철학을 고품격으로 보조하는 고해상도 흑백(black and white) 또는 저채도(low saturation) 스톡 이미지나 매거진 스타일 레이아웃으로 영어 프롬프트 작성할 것 (글자 묘사 및 text placeholder 금지, no text, no letters 필수).
3. 텍스트 레이아웃 및 폰트 연출:
   - 각 장의 텍스트는 빽빽하지 않고 여백의 미가 돋보이는 미니멀 구조로 기획할 것.
   - 문구를 제목("heading", 명조체 매거진 헤드라인 스타일)과 부연 설명("sub_text", 차분한 고딕체 스타일)으로 분리하여 제공할 것.
   - 줄바꿈 포함 각 텍스트는 2줄 이내로 극도로 짧게 제한할 것.
4. 출력 형식:
   - 다른 설명 없이, 아래 JSON 스키마를 만족하는 순수 JSON 데이터만 딱 하나 반환해줘.
   - "멋있는 말"보다 "독자가 겪는 구체 상황"을 우선할 것.
   - 각 장은 한 문장에 하나의 생각만 담을 것.
   - 마지막 장에는 저장할 이유가 자연스럽게 들어가야 함.

{{
  "title": "이번 탐색 주제 요약",
  "pages": [
    {{
      "page": 1,
      "image_prompt": "Background stock image description in English (low saturation/black and white, elegant)",
      "heading": "표지 또는 각 장의 대제목 (명조체 적용)",
      "sub_text": "설명 혹은 강조용 소제목 (고딕체 적용)",
      "theme_color": "deep_navy" // cream, deep_navy, slate_gray 중 배경 톤 선택
    }}
  ]
}}
"""

    # 5. Antigravity 요청 파일 생성 및 응답 파일 확인
    print("\n[Step 4] Antigravity 중심 대본 생성 요청 준비...")
    script_data = write_story_request(prompt) or read_json_response("codex_story_response.json")

    if script_data:
        print("✅ Antigravity 응답 JSON을 읽어 대본 생성을 완료했습니다.")
    else:
        print("[Antigravity] codex_story_response.json이 없어 로컬 폴백 대본을 사용합니다.")
        script_data = build_fallback_script(obsidian_context)

    # 6. script.json 파일로 저장
    output_file = "script.json"
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)
        print(f"🎉 최종 카드뉴스 대본이 기획 완료되어 '{output_file}'에 안전하게 저장되었습니다!")
    except Exception as e:
        print(f"[Error] 최종 script.json 파일 저장 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
