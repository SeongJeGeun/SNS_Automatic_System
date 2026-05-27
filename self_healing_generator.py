import os
import sys
import json
import requests
from dotenv import load_dotenv
from google_sheet_manager import GoogleSheetManager
from constants import MINDSET_PHILOSOPHY, COVER_HOOK_RULES, OBSIDIAN_VAULT_PATH
from obsidian_rag import ObsidianRAGEngine

# 환경 변수 로드
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def query_claude_api(prompt):
    if not CLAUDE_API_KEY:
        return None
    print("[Backup AI] Gemini API 장애로 인해 2순위 백업 모델 Claude API를 가동합니다...")
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}],
        "system": "너는 인스타그램에서 조회수를 폭발시키는 마인드팩토리의 수석 카피라이터야. 다른 설명이나 인사 없이 오직 요구된 JSON 데이터만 단 하나 반환해줘."
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        if res.status_code == 200:
            return res.json()["content"][0]["text"]
        else:
            print(f"[Warning] Claude API 호출 실패 (상태 코드: {res.status_code}): {res.text}")
    except Exception as e:
        print(f"[Warning] Claude API 통신 중 오류 발생: {e}")
    return None

def query_openai_api(prompt):
    if not OPENAI_API_KEY:
        return None
    print("[Backup AI] Gemini/Claude API 장애로 인해 3순위 백업 모델 OpenAI GPT API를 가동합니다...")
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "너는 인스타그램에서 조회수를 폭발시키는 마인드팩토리의 수석 카피라이터야. 다른 설명이나 인사 없이 오직 요구된 JSON 데이터만 단 하나 반환해줘."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        if res.status_code == 200:
            return res.json()["choices"][0]["message"]["content"]
        else:
            print(f"[Warning] OpenAI API 호출 실패 (상태 코드: {res.status_code}): {res.text}")
    except Exception as e:
        print(f"[Warning] OpenAI API 통신 중 오류 발생: {e}")
    return None


def query_gemini_api(prompt):
    if not GEMINI_API_KEY:
        print("[Warning] .env 파일에 GEMINI_API_KEY가 존재하지 않습니다. 자가 복구용 모의 스크립트를 생성합니다.")
        return None
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        res_data = res.json()
        if res.status_code == 200:
            text_response = res_data["candidates"][0]["content"]["parts"][0]["text"]
            return text_response
        else:
            print(f"[Warning] Gemini API 호출 실패 (상태 코드: {res.status_code}): {res_data}")
            return None
    except Exception as e:
        print(f"[Warning] Gemini API 통신 중 오류 발생: {e}")
        return None

def build_fallback_script(obsidian_context):
    """RAG 맥락을 덧댄 정체성 높은 폴백 script.json 작성 (7장 분량의 고급 매거진 스타일)"""
    print("[Self-Healing] 외부 API 장애 또는 제한을 감지하여 로컬 자가 복구 메커니즘을 가동합니다...")
    
    fallback_data = {
      "title": "규율이라는 고귀한 속박",
      "pages": [
        {
          "page": 1,
          "image_prompt": "Minimalist photography of a single glowing gold line running across a matte black texture, high contrast, elegant serif font feeling, silent atmosphere, low saturation, no text",
          "heading": "동기부여라는 값싼 자극",
          "sub_text": "그것은 2시간짜리 오락에 불과하다.",
          "theme_color": "deep_navy"
        },
        {
          "page": 2,
          "image_prompt": "High-end editorial black and white photo of structured stone pillars standing firm against foggy wind, low saturation, high grain, architectural harmony, no text",
          "heading": "인생을 지배하는 기둥",
          "sub_text": "성공하는 하루를 만드는 것은 기분이나 날씨가 아닌, 철저한 규율이다.",
          "theme_color": "slate_gray"
        },
        {
          "page": 3,
          "image_prompt": "Minimalist study room with deep navy walls, wooden desk with a single focused vintage lamp illuminating an open book, elegant, quiet, gold point, no text",
          "heading": "하루 2시간의 진공 상태",
          "sub_text": "세상의 모든 소음과 스마트폰 불빛을 끄고 오직 단 하나에만 몰입하라.",
          "theme_color": "cream"
        },
        {
          "page": 4,
          "image_prompt": "Low key low saturation photography of a person's hands carving wood or stone, fine details, focus, craftsmanship, dark slate gray tones, no text",
          "heading": "불편한 진실과의 마주함",
          "sub_text": "어제보다 1% 불편한 길을 택하라. 성장은 그 틈에서 피어난다.",
          "theme_color": "deep_navy"
        },
        {
          "page": 5,
          "image_prompt": "Fine art black and white photo of an empty path disappearing into misty trees, high texture, premium mood, silent, no text",
          "heading": "오늘 회피한 그 고통",
          "sub_text": "내일 당신의 한계를 가두는 보이지 않는 벽이 된다.",
          "theme_color": "cream"
        },
        {
          "page": 6,
          "image_prompt": "A sharp beam of light cutting through a dark concrete space, minimal composition, slate gray and cold light, premium architectural photography, no text",
          "heading": "규율이라는 고귀한 자유",
          "sub_text": "스스로를 완벽히 통제할 수 있는 자만이 진정한 자유를 얻는다.",
          "theme_color": "slate_gray"
        },
        {
          "page": 7,
          "image_prompt": "Deep navy background with a thin gold geometric frame at the center, highly elegant and premium magazine layout, gold accents, no text",
          "heading": "나를 재설계하라",
          "sub_text": "타협 없는 규율의 미학을 삶에 이식하려면, 이 가이드를 저장하라.",
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
        
    rag = ObsidianRAGEngine(vault_path=OBSIDIAN_VAULT_PATH)
    obsidian_context = rag.retrieve_context(search_query, k=3)
    
    if obsidian_context:
        print("  - 유사도 검색 완료! 매칭된 생각 노트 컨텍스트 확보.")
    else:
        print("  - [Info] 검색 결과가 비어 있거나 로컬 경로 부재로 RAG 컨텍스트를 스킵합니다.")
        
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

이번 카드뉴스의 전략 문서야. 이 구조를 반드시 따라:
======================================================
{strategy_context_json}
======================================================

이전 생성물이 품질 검사에서 탈락했다면 아래 피드백을 반드시 고쳐:
======================================================
{quality_feedback_context}
======================================================

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
   - 2~3장: 왜 무너지는지 원인 해석
   - 중간 장: 관점 전환 및 동기부여
   - 마지막 장: 저장하고 다시 볼 수 있는 구체적 행동/루틴 제안
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

    # 5. Gemini API 호출 또는 자가 치유 폴백 실행
    print("\n[Step 4] RAG 결합형 대본 생성 중...")
    raw_response = query_gemini_api(prompt)
    
    # 2순위 백업 체인 구동
    if not raw_response:
        raw_response = query_claude_api(prompt)
    if not raw_response:
        raw_response = query_openai_api(prompt)
        
    script_data = None
    if raw_response:
        try:
            cleaned_response = raw_response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            script_data = json.loads(cleaned_response)
            print("✅ AI API를 통해 옵시디언 RAG 맞춤형 대본 생성을 성공적으로 완료했습니다.")
        except Exception as e:
            print(f"[Warning] 생성 데이터 파싱 에러: {e}. 로컬 자가치유 폴백을 구동합니다.")
            script_data = build_fallback_script(obsidian_context)
    else:
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
