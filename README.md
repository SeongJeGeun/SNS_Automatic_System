# 🧠 MindFactory SNS Automatic System (마스터 운영 매뉴얼)

마인드팩토리의 핵심 3대 철학(**게으름 팩폭, 시스템 구축, 규율과 자유**)을 관통하여 텍스트 소통 중심의 **Threads**와 시각 요약/저장 중심의 **Instagram**을 유기적으로 연동하여 무인으로 운영하는 **텔레그램 연동형 멀티 에이전트 자동화 시스템**입니다.

---

## 🎯 1. 플랫폼 아키텍처 및 역할

본 시스템은 Z세대의 '비공개 DM 공유(Sends)' 및 '판단 유예용 저장(Saves)' 행동 양식을 자극하여 플랫폼 간 유기적 트래픽 순환을 유도합니다.

| 플랫폼 | 주요 역할 | 주요 소비 행동 | 핵심 톤 앤 매너 |
| :--- | :--- | :--- | :--- |
| **Threads** | - 화두 던지기 및 1차 훅<br>- 실시간 댓글 핑퐁 소통 | 답글 소통, 리포스트, 친근 리액션 | - **대화체 (~죠, ~요)**<br>- 가볍고 날카로운 구어체 |
| **Instagram** | - 정보의 구조화 및 시각 요약 카드뉴스<br>- 최종 저장 및 외부 공유 유도 | 저장(Saves), DM 공유(Sends) | - **단정체 (~입니다, ~하세요)**<br>- 신뢰감 있는 브랜드 관점 |
| **Telegram** | - 양방향 제어 명령 입력<br>- 성공/실패/에스컬레이션 실시간 보고 | 시스템 원격 통제 | - 직관적인 명령 및 에러 스택 보고 |
| **Sheets / Excel** | - 계정 성장 원장 및 리포트 보존 | 일일 성과 통계 분석 | - 일일/주간 누적 성과 요약 테이블 |

---

## 🤖 2. 에이전트 인프라 구성 (7대 구성원)

1. **Topic Agent**: RAG 분석을 바탕으로 금주 핵심 주제 1개와 서브 메시지 3개를 도출하고 금지 키워드를 활성화합니다.
2. **Threads Agent**: 1~2문장의 강한 구어체 훅 포스트와 질문형 댓글 유도 스레드를 기획합니다.
3. **Instagram Agent**: 쓰레드 반응이 좋았던 주제를 1:3 법칙에 입각하여 7장의 카드뉴스 대본으로 확장하며 저장 유도형 캡션을 작성합니다.
4. **Engagement Agent**: 댓글과 답글 반응을 5가지 범주(공감, 질문, 반박, 경험공유, 무반응)로 파싱하여 다음 콘텐츠 기획 소재로 피드백합니다.
5. **Self-Healing Agent**: 토큰 만료, API 제한(429), 파싱 오류 및 톤 이탈을 실시간 감지하여 자동 백오프 리트라이 및 에스컬레이션을 처리합니다.
6. **Telegram Interface**: `/status`, `/report`, `/retry`, `/pause` 등의 명령을 처리하고 상태를 회신합니다.
7. **Spreadsheet Reporter**: 매일 아침 9시, 전날의 총 게시 수, 반응 지표 및 실패 건수를 구글 시트에 일일 보고서로 자동 기록합니다.

---

## 🔄 3. 운영 라이프사이클 및 8대 상태 기계

```
[주제 생성] ➡️ [Threads 훅 포스트] ➡️ [인스타 7장 카드뉴스 가공] ➡️ [자동 렌더링] ➡️ [교차 발행 및 피드백]
```

각 콘텐츠 컨테이너는 아래 8가지 상태값을 가지며, 시스템 상태 파일(`agent_runs/agent_status.md` 및 `manifest.json`)에 영구 기록됩니다.
* **`draft`**: 에이전트가 텍스트 및 이미지를 생성한 최초 임시 상태.
* **`approved`**: 텔레그램/대시보드를 통해 사용자가 승인 처리를 완료한 상태 (수동 게이트).
* **`scheduled`**: 업로드 예약 시각이 지정되어 퍼블리셔 큐에서 대기 중인 상태.
* **`published`**: API 업로드가 최종 완료된 상태.
* **`failed`**: API 오류나 타임아웃 한계 초과로 영구 실패 처리된 상태.
* **`recovering`**: 자기치유 모듈이 1차 백오프 리트라이 또는 프롬프트 단순화를 적용 중인 상태.
* **`recycle_candidate`**: 성과 점수가 기준치(130%)를 초과하여 차주 기획 최우선 소재로 분류된 상태.
* **`escalated`**: API 한도 제한 등으로 인해 사람의 직접 수동 조치 승인을 홀드 대기 중인 상태.

---

## 🛡️ 4. 연동 운영 및 드리프트 가드 (Drift Guard)

1. **중복 복사 금지**: Threads(대화형 구어체)와 Instagram(단정형 명조체)은 플랫폼별 성향에 맞춰 어투와 캡션 형식을 철저히 분리하며, 동일한 텍스트를 그대로 복사하여 붙여넣지 않습니다.
2. **소통 SLA 준수**: Threads 포스트 업로드 후 **최초 6시간 이내**에 달린 상위 5개의 피드백 댓글에는 알고리즘 보상을 위해 반드시 답글 피드백을 완료합니다.
3. **승인 게이트 보존**: 렌더링 카드 가독성 검수 및 텍스트 훅의 톤앤매너 1차 검수는 반드시 인간 관리자가 직접 검토하여 게시물 오염을 방지합니다.

---

## 📈 5. Threads 테스트 업로드 빈도 제어 및 반응 조율 (Growth Hack)

초기 업로드 시 계정의 도달률 급감(Shadow Ban) 및 반응 분산을 방지하고 데이터 기반으로 점진적으로 채널을 확장하는 지침입니다.

### 1) 빈도 조절 원칙 (Frequency Control Steps)
* **초기 1~2일차 (Warm-Up 단계)**:
  - 하루 업로드 빈도를 **3~4회**로 극도 제한합니다. (최소 6~8시간의 간격 유지)
  - `.env` 파일 내 `PIPELINE_INTERVAL_SECONDS=21600` 설정을 통해 6시간 주기로 스케줄러를 제한 가동합니다.
* **3일차 이후 (Scalability 단계)**:
  - 초기 반응 지표(좋아요, 댓글 수)가 최근 게시물 평균의 100% 이상을 유지할 경우, 점진적으로 주기를 좁혀 **최종 3시간 간격(`PIPELINE_INTERVAL_SECONDS=10800`)** 업로드 파이프라인으로 확대합니다.
* **도달률 저하 시 (Cool-Down 단계)**:
  - 도달률(노출수) 및 반응 지표가 연속 3회 이상 하락세를 보일 경우, 즉시 업로드 빈도를 다시 하루 3~4회 수준으로 낮추고, RAG 분석을 통해 콘텐츠 품질과 첫 장 훅의 카피라이팅 개선 작업을 선행합니다.

### 2) 3단계 성과 보고 체계
* **1차 보고 (게시 직후)**: `post_id`, `permalink`, `게시 시각`을 텔레그램으로 즉시 알림 발송.
* **2차 보고 (게시 24시간 뒤)**: `조회수`, `좋아요 수`, `댓글 수`, `리포스트/인용 수`, `프로필 유입/팔로우 증가 여부`를 텔레그램 요약 발송.
* **3차 최종 보고 (게시 72시간 뒤)**: 72시간 누적 지표 종합 및 피드백 루프 조율 (계정 5회 평균치와 비교 분석하여 업로드 간격 및 차기 RAG 훅 어조 수위 동적 조정).

---

## 🚨 6. 장애 대응 및 자가 치유(Self-Healing)

* **토큰 만료 (HTTP 401)**: `Short-Lived` 토큰 만료 전 `instagram_token_manager.py`를 통한 30일 주기 자동 연장 검증. Threads 전용 사용자 토큰(`THREADS_ACCESS_TOKEN`)은 만료 전 개발자 콘솔을 통해 수동 갱신 후 `.env`에 이식.
* **API 차단 및 Rate Limit (HTTP 429)**: 인스타그램 Action Blocked 감지 시 즉시 `instagram_publish_cooldown.json` 파일을 기록하고 **24시간 강제 쿨다운 진입**.
* **자가 치유 임계치 초과**: 자가 치유 에이전트가 프롬프트 자동 조정을 2회 시도했음에도 품질 미달 혹은 발행 오류가 지속될 시, 상태를 즉시 `escalated`로 전환하고 **무인 발행을 전면 홀딩(Hold)**한 뒤 텔레그램으로 인간 관리자 개입 알림을 발송.

---

## 🧪 7. QA 검증 및 유지관리

* **[ ] 정적 코드 안전 진단**: 코드 수정 직후 사전 정적 분석 검사 실행.
  ```bash
  ./scripts/qa_checks.sh
  ```
  (단 하나의 단계라도 FAILED될 경우 릴리즈 불가)
* **[ ] E2E 무발행(Safe) 테스트 검증**: 실제 인스타그램/Threads API 전송을 스킵하고 전체 생성, RAG 임베딩 및 카드뉴스 렌더링 정상 여부만 시뮬레이션 검증.
  ```bash
  python3 codex_e2e_check.py
  ```
  (`agent_runs/codex_e2e_check_report.json`에서 `"ok": true` 확인 필요)

---

## 📁 8. 리포지토리 디렉터리 레이아웃

```
.
├── README.md               # 시스템 마스터 매뉴얼
├── config/                 # 공개 가능한 전략/정책 JSON
├── docs/                   # 상세 스펙 및 규칙 폴더
│   ├── runbook.md          # 장애 대응 및 수동 조치 런북
│   ├── PUBLIC_RELEASE_CHECKLIST.md # GitHub 공개 전 점검표
│   └── THREADS_INSTAGRAM_RULES.md # 플랫폼 연동 규칙 지침
├── ops/launch_agents/      # 개인정보 없는 LaunchAgent 예시
├── scripts/                # 관리용 쉘 스크립트 폴더
│   └── qa_checks.sh        # 정적 QA 진단 도구
├── prompts/                # Antigravity/Codex 단계별 프롬프트
├── samples/                # 공개 가능한 JSON 샘플
├── static/, templates/     # 대시보드 UI
├── agent_runs/             # 로컬 상태 캐시, Git 제외
├── logs/                   # 로컬 로그, Git 제외
├── obsidian_vault/         # 로컬 Obsidian 지식 베이스, Git 제외
├── main_orchestrator.py    # 통합 오케스트레이션 루프 엔진
├── upload_carousel.py      # Instagram API 업로더
├── self_healing_generator.py # 자가 치유형 대본 생성기
├── telegram_agent.py       # Telegram 인터페이스봇
└── google_sheet_manager.py # Google Sheets 리포터
```

---

## 🔑 9. 환경 변수 설정 가이드 (.env)

시스템 구동을 위해 리포지토리 루트의 `.env` 파일에 아래 환경 변수를 명확히 선언해야 합니다.

의존성은 아래처럼 설치합니다.

```bash
python3 -m pip install -r requirements.txt
```

```env
# Meta Graph API Credentials
INSTAGRAM_ACCESS_TOKEN=your_instagram_access_token
INSTAGRAM_ACCOUNT_ID=your_instagram_account_id
THREADS_ACCESS_TOKEN=your_threads_access_token

# Telegram System
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
TELEGRAM_NOTIFICATIONS_ENABLED=true
TELEGRAM_REPORT_MUTED=true

# Google Drive & Sheets System
GOOGLE_DRIVE_PARENT_FOLDER_ID=your_google_drive_folder_id
PIPELINE_INTERVAL_SECONDS=21600 # 초기 2일간 6시간 주기 제한 설정
```
