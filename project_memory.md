# Project Memory — AI Handoff Context

본 문서는 대화 세션이 재시작되거나 다른 AI 에이전트가 투입되었을 때, 이전 작업 맥락을 10초 이내에 동기화하여 작업 파손을 막기 위한 **AI 전용 구조화 작업 기억(State Memory)**입니다.

---

## 🎯 1. 프로젝트 마스터 아웃라인

- **목적**: Z세대의 '이타주의적 비공개 DM 공유(Sends)' 및 '판단 유예용 저장(Saves)' 행동 양식을 관통하는 Threads-Instagram 연동 콘텐츠 파이프라인 운영.
- **연동 핵심 규칙**: Threads(가볍게 툭 던지는 대화형 훅) ➡️ Instagram(7장 시각 가치 정보 구조화 및 저장 챌린지) ➡️ 댓글 수집 후 스케줄 피드백.

---

## 🤖 2. 에이전트 인프라 맵 (7대 구성원)

- **Topic Agent**: 주간 RAG 분석 기반 1개 핵심 주제 도출.
- **Threads Agent**: 1~2줄 대화형 훅 및 소통 스레드 작성.
- **Instagram Agent**: 1:3 꿀팁/공감 황금 비율 기반 7장 카드뉴스 렌더링.
- **Engagement Agent**: 댓글 수집 및 Q&A 대상 분류(A/B/C/D 타입 분류).
- **Self-Healing Agent**: API 장애, 포맷 에러, 톤 드리프트 실시간 복구.
- **Telegram Interface**: `/status`, `/report`, `/retry`, `/pause` 양방향 제어.
- **Spreadsheet Reporter**: 구글 시트 M1/M2 탭 일일 리포트 요약 적재.

---

## 📉 3. 현재 구현 상태 (As-of 2026-05-28)

### ✅ 이미 완료된 항목
- [x] 리포지토리 재구조화 (`prompts/`, `samples/`, `jobs/active`, `logs/`, `docs/`, `scripts/` 격리 완료)
- [x] Z세대 공유 동기 및 2026 알고리즘 반영 기획서 작성 완료 (`docs/card_research_notes.md`)
- [x] 1:3 최적화 규칙 및 7장 가이드라인 포맷 설계 완료 (`knowledge_summary.json`)
- [x] 보상 가중치 공식 수립 완료 (`distribution_policy.json`)
- [x] 7장 대본 및 캡션/ALT 텍스트 렌더링 이미지 생성 테스트 완료 (`script.json`, `page1.png`~`page7.png`)
- [x] Threads API 연결 유효성 및 테스트 게시 성공 검증 완료 (계정: `mind_factory_us`)
- [x] 리포지토리 건강 검진 스크립트 작성 완료 (`scripts/qa_checks.sh`)

### ⚠️ 아직 남은 구현 항목 (개발 대기)
- [ ] `telegram_agent.py` 내에 `/status`, `/report` 등 4대 텔레그램 명령어 분석 및 회신 인터페이스 구축
- [ ] 검증 완료된 Threads API 릴리즈 코드의 `main_orchestrator.py` 파이프라인 이식 통합
- [ ] API 429 감지 시 Exponential Backoff 및 자동 프롬프트 수정(Self-Healing) 분기 연결
- [ ] 구글 시트 일일 자동 보고 리포터 연결

---

## 📅 4. 다음 작업 우선순위 (Next Steps)
1. **1순위**: `telegram_agent.py`에 원격 제어 및 챗봇 명령어 핸들러 추가
2. **2순위**: `main_orchestrator.py`에 Threads 텍스트 컨테이너 생성 및 업로드 모듈 공식 연동
3. **3순위**: `Self-Healing Agent` 예외 분기 활성화
4. **4순위**: `Spreadsheet Reporter` 연동

---

## 🔑 다음 세션에서 바로 볼 핵심 5줄
1. **목적지**: Threads(대화형 구어체)와 Instagram(단정형 명조체)을 유기적으로 순환시키는 멀티 에이전트 구축 단계.
2. **현 위치**: 7장 대본(`script.json`)과 렌더링 이미지 7장 생성 완료 및 Threads API 실시간 게시 연동 유효성 패스.
3. **다음 타깃**: `telegram_agent.py`를 수정하여 `/status` 및 `/report` 원격 명령어 처리 핸들러 작성.
4. **운영 규칙**: Threads와 인스타에 동일한 카피 문구를 그대로 복사해 붙여넣지 말 것.
5. **검증 가이드**: 코드를 수정한 후에는 반드시 리포지토리 루트에서 `./scripts/qa_checks.sh`를 실행해 에러를 검사할 것.
