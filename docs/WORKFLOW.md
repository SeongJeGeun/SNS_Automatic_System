# 7단계 파이프라인 워크플로우 명세

마인드팩토리 SNS 자동화는 **오케스트레이터 에이전트**의 통제 하에 총 7개의 세부 태스크가 유기적으로 흐르도록 설계되었습니다. 각 단계는 엄격한 입출력 규격을 가지고 있어 에러 발생 시 즉각 중단 및 자동 복구 모드가 작동합니다.

---

## 🔄 파이프라인 상세 프로세스

### Stage 1: 오디언스 분석 (Audience Research)
- **설명**: 타깃층의 최근 고민과 번아웃 지표를 도출합니다.
- **입력**: `prompts/STAGE_1_AUDIENCE.md`, 외부 트렌드 요청 파일 (`obsidian_vault/trend_search_*.md`)
- **출력**: `jobs/active/[JOB_ID]/audience_insight.json`

### Stage 2: 스토리 전략 설계 (Content Strategy)
- **설명**: 타깃층이 직면한 핵심 문제(Pain Point)를 찌르는 훅과 독자 이탈을 막는 스토리라인을 설계합니다.
- **입력**: `prompts/STAGE_2_STRATEGY.md`, `audience_insight.json`
- **출력**: `jobs/active/[JOB_ID]/strategy.json`

### Stage 3: 카드뉴스 대본 생성 (Story Generation)
- **설명**: 설계된 카드뉴스 템플릿에 맞추어 실제 페이지별 대본과 부제목을 작성합니다.
- **입력**: `prompts/STAGE_3_STORY.md`, `strategy.json`
- **출력**: `jobs/active/[JOB_ID]/script.json`

### Stage 4: 품질 평가 (Quality Evaluation)
- **설명**: 완성된 대본이 공감성 저하, 상투적인 단어 포함, 가독성 불량 등 품질 기준에 도달했는지 정량적으로 검증합니다.
- **입력**: `prompts/STAGE_4_QUALITY.md`, `script.json`
- **출력**: `jobs/active/[JOB_ID]/quality_report_1.json` (합격/불합격 여부 포함)

### Stage 5: 카드뉴스 비주얼 설계 및 합성 (Visual & Render)
- **설명**: 대본의 감정선과 어울리는 배경 이미지를 생성 요청하고, 텍스트 레이아웃을 안전 구역 내에 렌더링하여 최종 업로드용 PNG 이미지를 생성합니다.
- **입력**: `prompts/STAGE_5_VISUAL.md`, `script.json`
- **출력**: `jobs/active/[JOB_ID]/visual_plan.json`, `jobs/active/[JOB_ID]/cards/page1.png` ~ `pageN.png`

### Stage 6: 업로드 스케줄링 및 캡션 작성 (Upload Planning)
- **설명**: 인스타그램용 캡션 텍스트와 해시태그를 빌드하고 최종 발행 전 체크리스트와 일정을 확정합니다.
- **입력**: `prompts/STAGE_6_UPLOAD.md`, `visual_plan.json`
- **출력**: `jobs/active/[JOB_ID]/caption.json`, `jobs/active/[JOB_ID]/publish_plan.json`

### Stage 7: 최종 오케스트레이션 및 업로드 (Orchestration & Publish)
- **설명**: 임시 링크 생성용 구글 드라이브 호스팅을 처리하고, Instagram Graph API를 사용하여 피드에 즉시 게시하거나 예약을 진행합니다.
- **입력**: `prompts/STAGE_7_ORCHESTRATOR.md`, `publish_plan.json`
- **출력**: `jobs/active/[JOB_ID]/final_status.json`

---

## 🛡️ 품질 게이트 및 자가 복구(Self-Healing) 규칙

1. **Stage 4 품질 게이트 탈락 시**:
   - `quality_report_1.json`의 `passed` 결과가 `false`인 경우 파이프라인은 1회 즉시 재시도 모드로 전환됩니다.
   - `quality_report_1.json`에 포함된 개선 요청사항(`revisions_required`)을 `self_healing_generator.py`에 주입하여 대본을 재생성하고, `quality_report_2.json`을 작성해 최종 판단합니다.
   - 2차 검증에서도 탈락 시 파이프라인은 업로드를 차단하고 상태를 `stopped`로 업데이트합니다.

2. **인스타그램 저성과 자가치유 (Performance Self-Healing)**:
   - 이전 포스팅의 조회수가 100회 미만일 경우 `need_healing` 플래그가 활성화됩니다.
   - 이 경우 에이전트는 기획 단계에서 형광색 포인트와 강력한 질문형 후크를 강화하도록 유도하는 `self_healing_strategy.json` 지침을 자동으로 생성하여 파이프라인 전반에 반영합니다.
