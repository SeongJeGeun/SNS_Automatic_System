# 프롬프트 가버넌스 및 관리 정책

에이전트 제어 프롬프트 파일은 하드코딩되지 않고 모두 마크다운 파일 형태로 통합 관리됩니다. AI 에이전트는 기동할 때마다 `prompts/` 폴더 안의 대응 파일을 읽어 동작하므로 안정적인 버전 관리가 요구됩니다.

---

## 📋 프롬프트 파일 리스트 및 역할

| 파일명 | 대상 에이전트 | 핵심 동작 가이드라인 |
|---|---|---|
| [SYSTEM_PROMPT.md](../prompts/SYSTEM_PROMPT.md) | 전체 에이전트 공통 | 마인드팩토리의 감성 톤앤매너, 금지 키워드, 외부 API 호출 제한 규칙 정의 |
| [STAGE_1_AUDIENCE.md](../prompts/STAGE_1_AUDIENCE.md) | Audience Agent | 2030 직장인의 현실적인 심리 통계 및 최근 감정 키워드 분석 지침 |
| [STAGE_2_STRATEGY.md](../prompts/STAGE_2_STRATEGY.md) | Strategy Agent | 논리 전개 구성, 카드뉴스에 적합한 3단 후킹 및 반전 프레임 설계 |
| [STAGE_3_STORY.md](../prompts/STAGE_3_STORY.md) | Story Agent | 문장당 최대 글자 수, 가독성이 뛰어난 행 분리 및 부제목 패턴 작성 지침 |
| [STAGE_4_QUALITY.md](../prompts/STAGE_4_QUALITY.md) | Quality Agent | 심리 분석 공감도(Resonance), 저장 가치 등 6개 차원 정량 평가 지침 |
| [STAGE_5_VISUAL.md](../prompts/STAGE_5_VISUAL.md) | Visual Agent | 미니멀리즘 에디토리얼 이미지 프롬프트 작성 및 여백 안전 지역 검사 |
| [STAGE_6_UPLOAD.md](../prompts/STAGE_6_UPLOAD.md) | Upload Agent | 가독성 높은 줄바꿈 캡션 구조, 관련도 높은 태그(8개 이내) 제약 설정 |
| [STAGE_7_ORCHESTRATOR.md](../prompts/STAGE_7_ORCHESTRATOR.md) | Orchestrator | 전체 공정 상태 기록 및 각 단계별 통과/재전송 여부 의사결정 규칙 |

---

## 📈 버전 관리 및 백업 규칙

- **수정 규칙**: 기존 동작이 검증된 프롬프트를 대폭 수정하기 전, 이전 프롬프트 버전을 반드시 `prompts/archive/` 하위 폴더에 보존합니다.
  - 백업 네이밍 형식: `prompts/archive/STAGE_X_NAME_YYYYMMDD.md`
- **단일 원칙**: 활성화된 동작용 프롬프트는 반드시 `prompts/` 하위에 지정된 규격 파일명 하나만 유지해야 합니다. (동일 명칭의 사본이 루트나 타 디렉토리에 혼재할 수 없습니다.)

---

## ⚠️ 프롬프트 수정 시 필수 주의사항

1. **외부 검색 금지 및 외부 AI API 제약**:
   - 프롬프트 지시어에 임의로 외부 API 연결이나 `requests` 등을 요구하는 구문을 포함하지 마십시오.
2. **JSON Format 강제**:
   - `STAGE_3_STORY.md` 등 산출물을 JSON 구조로 받아내야 하는 프롬프트 하단에는 반드시 출력 스키마(예: `samples/script.sample.json`)를 설명하는 내용이 파싱 조건으로 박제되어 있어야 합니다.
