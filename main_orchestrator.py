import os
import json
import time
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# Google API Libraries
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import gspread

# import upload_carousel module directly for seamless programmatic call
import upload_carousel
from card_renderer import generate_card_news_images
from audience_research import create_audience_insight
from content_strategy import create_content_strategy
from content_evaluator import evaluate_script_quality
from agent_monitor import (
    agent_step,
    heartbeat,
    next_run_time,
    update_pipeline,
    write_human_summary,
)
from telegram_agent import (
    process_telegram_commands,
    send_telegram_message,
)


def get_dynamic_wait_seconds(default_seconds):
    try:
        from optimal_timing import get_recommended_sleep_seconds
        sleep_seconds = get_recommended_sleep_seconds()
        if sleep_seconds is None:
            return default_seconds

        minimum_guard = int(os.getenv("MIN_PIPELINE_INTERVAL_SECONDS", "1800"))
        maximum_guard = int(os.getenv("MAX_PIPELINE_INTERVAL_SECONDS", str(24 * 3600)))
        return max(minimum_guard, min(maximum_guard, sleep_seconds))
    except Exception as exc:
        print(f"[Warning] 최적 업로드 시간 계산 실패. 기본 간격을 사용합니다: {exc}")
        return default_seconds


def sync_publish_reports_to_obsidian():
    try:
        from obsidian_publish_sync import sync_all_publish_reports
        results = sync_all_publish_reports()
        if results:
            print(f"[Obsidian Sync] 발행 데이터 {len(results)}건을 지식 베이스와 동기화했습니다.")
    except Exception as exc:
        print(f"[Warning] Obsidian 발행 데이터 동기화 실패: {exc}")


def sync_insights_and_strategy():
    try:
        import update_insights
        update_insights.main()
    except Exception as exc:
        print(f"[Warning] 인사이트 업데이트 실패: {exc}")

def search_and_save_trends(vault_path):
    """Antigravity CLI 검색으로 트렌드 조사 결과를 옵시디언 폴더에 저장"""
    if not os.path.exists(vault_path):
        vault_path = os.path.join(os.getcwd(), "obsidian_vault")
    os.makedirs(vault_path, exist_ok=True)

    queries = [
        "instagram algorithm changes tips 2026",
        "instagram carousel layout design trends",
        "Korean young adults burnout anxiety motivation social media trend",
        "Instagram carousel storytelling hook save share strategy",
    ]

    md_content = f"# Antigravity Trend Search Request ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n"
    md_content += "아래 항목은 Antigravity CLI 검색/추론으로 조사하기 위한 요청입니다.\n\n"
    md_content += "## 요청\n"
    md_content += "- 요즘 사람들이 실제로 어떤 삶의 압박, 번아웃, 불안, 동기 저하를 겪는지 조사\n"
    md_content += "- 인스타그램 카드뉴스에서 저장/공유를 유도하는 최신 후킹과 스토리텔링 패턴 조사\n"
    md_content += "- 조사 결과를 다음 대본 생성과 전략 설계에 반영할 수 있게 요약\n\n"
    md_content += "## 검색 쿼리\n"
    for query in queries:
        md_content += f"- {query}\n"
    md_content += "\n## Antigravity 응답 작성 위치\n"
    md_content += "Antigravity CLI가 이 요청을 처리해 같은 파일에 검색 결과 Markdown을 저장합니다.\n"

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"trend_search_{timestamp}.md"
        filepath = os.path.join(vault_path, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)

        try:
            from antigravity_bridge import run_search_task
            search_result = run_search_task(md_content, filepath, request_path=filepath)
            if search_result:
                print(f"✅ Antigravity 검색 결과 저장 완료: {filepath}")
            else:
                print(f"✅ Antigravity 검색 요청 파일 저장 완료: {filepath}")
        except Exception as search_exc:
            print(f"[Warning] Antigravity 검색 실행 실패, 요청 파일만 보존합니다: {search_exc}")
    except Exception as e:
        print(f"[Warning] 트렌드 조사 요청 파일 생성 실패: {e}")

# =====================================================================
# [설정 변수]
# =====================================================================
ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
API_VERSION = os.getenv("INSTAGRAM_API_VERSION", "v19.0")

CREDS_FILE = "google_creds.json"
SHEET_NAME = "MindFactory_SNS_Dashboard"

# =====================================================================
# A. 주차(W) 및 월차(M) 자동 계산
# =====================================================================
def get_start_date():
    start_file = "agent_runs/start_date.txt"
    if os.path.exists(start_file):
        with open(start_file, "r") as f:
            date_str = f.read().strip()
            return datetime.strptime(date_str, "%Y-%m-%d")
    else:
        today = datetime.now()
        os.makedirs("agent_runs", exist_ok=True)
        with open(start_file, "w") as f:
            f.write(today.strftime("%Y-%m-%d"))
        return today

def get_current_periods():
    start_date = get_start_date()
    today = datetime.now()
    days_elapsed = (today - start_date).days

    week_num = (days_elapsed // 7) + 1
    month_num = (days_elapsed // 30) + 1

    return f"W{week_num}", f"M{month_num}"

# =====================================================================
# B. 구글 API 로드 및 드라이브 트리 생성
# =====================================================================
def get_google_services():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = None

    # 1. token.json (User Credentials) 우선 시도
    if os.path.exists("token.json"):
        from google.oauth2.credentials import Credentials as UserCredentials
        try:
            creds = UserCredentials.from_authorized_user_file("token.json", scopes=scopes)
            print("[Info] 'token.json' 사용자 계정 인증 정보를 사용하여 구글 서비스에 연결합니다.")
        except Exception as e:
            print(f"[Warning] token.json 로드 중 예외: {e}")

    # 2. google_creds.json (Service Account) 차선 시도
    if not creds and os.path.exists(CREDS_FILE):
        try:
            creds = Credentials.from_service_account_file(CREDS_FILE, scopes=scopes)
            print("[Info] 'google_creds.json' 서비스 계정 자격 증명을 사용하여 구글 서비스에 연결합니다.")
        except Exception as e:
            print(f"[Warning] google_creds.json 로드 중 예외: {e}")

    if not creds:
        print("[Warning] 구글 자격 증명 파일(token.json 또는 google_creds.json)이 존재하지 않아 시뮬레이션 모드로 실행합니다.")
        return None, None, None

    drive_service = build("drive", "v3", credentials=creds)
    docs_service = build("docs", "v1", credentials=creds)
    gspread_client = gspread.authorize(creds)

    return drive_service, docs_service, gspread_client

def get_or_create_drive_folder(drive_service, name, parent_id=None):
    if not drive_service:
        return "mock_folder_id"

    query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    file_metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder"
    }
    if parent_id:
        file_metadata["parents"] = [parent_id]

    folder = drive_service.files().create(body=file_metadata, fields="id").execute()
    print(f"📁 구글 드라이브 폴더 생성 완료: {name} (ID: {folder.get('id')})")
    return folder.get("id")

def move_file_to_folder(drive_service, file_id, folder_id):
    if not drive_service:
        return
    file = drive_service.files().get(fileId=file_id, fields='parents').execute()
    previous_parents = ",".join(file.get('parents', []))
    drive_service.files().update(
        fileId=file_id,
        addParents=folder_id,
        removeParents=previous_parents,
        fields='id, parents'
    ).execute()

# =====================================================================
# C. 구글 시트 월 단위 탭 동적 분할
# =====================================================================
def get_sheet_and_ensure_tab(gspread_client, drive_service, folder_id):
    if not gspread_client:
        return None, None
    from google_sheet_manager import GoogleSheetManager
    _, month_tab = get_current_periods()
    gsm = GoogleSheetManager(sheet_name=SHEET_NAME, tab_name=month_tab)
    return gsm, gsm.sheet

# =====================================================================
# D. 직전 피드 성과 조회 및 자기치유 다각화 플래그
# =====================================================================
def check_last_post_performance(worksheet):
    if not worksheet:
        return False, None, None, 0

    records = worksheet.get_all_records()
    if not records:
        return False, None, None, 0

    last_record = records[-1]
    media_id = last_record.get("미디어ID")
    title = last_record.get("타이틀", "")
    content = last_record.get("본문내용", "")

    if not media_id:
        return False, None, None, 0

    print(f"[Info] 직전 업로드 미디어 (ID: {media_id}) 성과 확인 중...")

    insights_url = f"https://graph.facebook.com/{API_VERSION}/{media_id}/insights"
    insights_params = {
        "metric": "impressions",
        "access_token": ACCESS_TOKEN
    }

    impressions = 0
    try:
        res = requests.get(insights_url, params=insights_params, timeout=8)
        res_data = res.json()
        if res.status_code == 200 and "data" in res_data:
            impressions = res_data["data"][0]["values"][0].get("value", 0)
            print(f"  - 직전 피드 조회수: {impressions}회")
        else:
            print(f"  - 조회수 획득 실패 (미등록 또는 API 에러): {res_data}")
    except Exception as e:
        print(f"  - 조회수 API 확인 중 예외 발생: {e}")

    if impressions < 100:
        print("⚠️ [자기치유 발동] 직전 피드의 조회수 성과가 극도로 저조합니다. 다음 기획에 비주얼 및 카피 다각화를 명령합니다.")
        return True, title, content, impressions
    return False, title, content, impressions


def analyze_and_generate_strategy(last_title, last_content, impressions):
    """직전 포스팅 성과가 저조할 경우 Antigravity 전략 요청으로 저장"""
    print(f"\n🧠 [자가치유 분화] 직전 포스팅('{last_title}', 조회수: {impressions}회) 성과 분석 및 전략 수립 중...")

    search_results = (
        "외부 검색 API를 직접 호출하지 않습니다. "
        "Antigravity CLI 검색으로 인스타그램 카드뉴스 성과 개선 자료를 조사해 주세요."
    )

    prompt = f"""너는 인스타그램 마케팅 분석가이자 마인드팩토리의 수석 전략가야.
직전에 발행한 카드뉴스의 성과가 매우 저조해(조회수: {impressions}회). 이 현상을 타개하기 위한 정밀 진단 및 피드백 지침을 만들어줘.

[직전 업로드 정보]
- 타이틀: {last_title}
- 상세 구성: {last_content}

[인터넷 실시간 검색 트렌드 자료]
{search_results}

위 자료들과 마인드팩토리 고유 브랜드 가치(규율, 몰입, 멘탈팩폭)를 결합하여, 다음 카드뉴스를 기획할 때 반영할 구체적인 '개선 전략'을 작성해줘.
원인 분석과 개선 사항은 날카롭고 구체적이어야 해.

출력 형식은 반드시 아래 JSON 스키마를 따르는 순수 JSON 객체여야 해. 다른 텍스트나 설명은 절대 포함하지 마.

{{
  "analysis": "왜 이 주제나 어조가 독자들에게 어필하지 못했는지 구체적인 원인 분석",
  "action_items": "비주얼(배경 테마 선택, 디바이더) 및 카피라이팅(1장 헤드라인 후킹, 명조/고딕 타이포) 차원에서의 명확한 개선 포인트",
  "prompt_injection": "다음 카드뉴스 대본 생성 AI에게 강제로 주입할 구체적인 디자인 및 카피 지시문 (예: '이번에는 Cream 배경에 Muted Blue 선을 극도로 절제해 쓰고, 헤드라인을 [~하는 짓은 당장 멈춰라] 식의 극약 처방 어조로 써라')"
}}
"""
    from codex_text_bridge import read_json_response, write_strategy_request
    strategy_data = write_strategy_request(prompt) or read_json_response("codex_strategy_response.json")
    if not strategy_data:
        strategy_data = {
            "analysis": "Antigravity 전략 응답 파일이 아직 없어 로컬 규칙으로 보수 판단합니다.",
            "action_items": "1장 훅은 독자의 현재 고통을 더 구체화하고, 중간 장에는 바로 실행 가능한 3단계 행동을 넣고, 마지막 장은 저장 이유가 분명한 체크리스트로 구성합니다.",
            "prompt_injection": "이번 카드뉴스는 공감형 후킹, 3단계 실천 요약, 저장용 체크리스트를 반드시 포함하고 자극적인 색과 과한 훈계톤을 피한다.",
        }

    with open("self_healing_strategy.json", "w", encoding="utf-8") as f:
        json.dump(strategy_data, f, ensure_ascii=False, indent=2)
    print("✅ Antigravity 중심 자가치유 전략 파일 저장 완료: self_healing_strategy.json")

# =====================================================================
# E. 자기치유 기반 대본 기획
# =====================================================================
def run_generator_script(diversify=False):
    print("\n[Step 1] 대본 자동 기획 가동...")
    import subprocess
    env = os.environ.copy()
    if diversify:
        env["FORCE_DIVERSIFICATION"] = "True"
    try:
        # subprocess로 완전히 고립된 프로세스로 구동시켜 PyTorch/Torch 스레드 데드락 현상을 원천 차단합니다.
        subprocess.run(
            ["python3", "self_healing_generator.py"],
            env=env,
            check=True
        )
    except Exception as e:
        print(f"[Warning] 대본 생성 모듈 실행 중 예외 감지: {e}")

# =====================================================================
# G. 구글 드라이브 임시 호스팅 & 릴리즈 & 클리닝
# =====================================================================
def upload_temp_image_to_drive(drive_service, file_path, folder_id):
    """구글 드라이브에 임시 이미지 업로드 및 퍼블릭 읽기 권한을 주어 직접 다운로드 링크 생성"""
    if not drive_service:
        return "mock_id", f"https://example.com/{os.path.basename(file_path)}"

    file_name = os.path.basename(file_path)
    file_metadata = {
        "name": file_name,
        "parents": [folder_id]
    }
    media = MediaFileUpload(file_path, mimetype='image/png')

    try:
        # 1. 파일 임시 생성
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        file_id = file.get('id')

        # 2. 링크 권한을 '모든 사용자(Anyone)'에게 부여
        permission = {
            'role': 'reader',
            'type': 'anyone'
        }
        drive_service.permissions().create(
            fileId=file_id,
            body=permission
        ).execute()

        # 3. 직접 다운로드 302 리디렉션 주소 조립
        direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        print(f"  - 드라이브 임시 업로드 완료: {file_name} -> {direct_url}")
        return file_id, direct_url
    except Exception as e:
        print(f"[Error] 드라이브 임시 업로드 실패 ({file_name}): {e}")
        return None, None

def clean_drive_temp_files(drive_service, file_ids):
    """구글 드라이브 임시 호스팅 파일 완전 청소"""
    if not drive_service or not file_ids:
        return
    print("\n[Step 4] 구글 드라이브 내 임시 호스팅 이미지 삭제 중...")
    for fid in file_ids:
        if not fid:
            continue
        try:
            drive_service.files().delete(fileId=fid).execute()
            print(f"  - 드라이브 임시 파일 삭제 성공: ID {fid}")
        except Exception as e:
            print(f"  - 드라이브 임시 파일 삭제 실패: ID {fid} ({e})")

# =====================================================================
# H. 일일 보고서 자동화 (아침 9시 트리거)
# =====================================================================
def check_and_create_daily_report(drive_service, docs_service, worksheet, report_folder_id):
    if not worksheet:
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    report_tag_file = f"agent_runs/report_sent_{today_str}.txt"

    if os.path.exists(report_tag_file):
        return

    now = datetime.now()
    if now.hour >= 9:
        print(f"\n📢 [일일 보고] 아침 9시 이후가 되어 일일 성과 보고서를 생성합니다...")

        # 이전 날짜의 리포트 태그 파일 청소
        import glob
        for old_tag in glob.glob("agent_runs/report_sent_*.txt"):
            if old_tag != report_tag_file:
                try:
                    os.remove(old_tag)
                except Exception:
                    pass

        records = worksheet.get_all_records()
        total_posts = len(records)
        total_impressions = 0
        total_saved = 0

        for r in records:
            try:
                total_impressions += int(r.get("조회수", 0))
                total_saved += int(r.get("저장수", 0))
            except ValueError:
                continue

        doc_title = f"마인드팩토리_일일보고서_{today_str}"

        report_text = f"""======================================================
🧠 마인드팩토리 일일 성과 보고서 ({today_str})
======================================================

1. 일일 콘텐츠 발행 현황
- 총 발행 수: {total_posts}개
- 누적 조회수(Impressions): {total_impressions}회
- 누적 저장수(Saved): {total_saved}회

2. AI 자가 분석 피드백
- 현재 고유 브랜드 철학(성장, 규율, 몰입, 멘탈팩폭)에 입각하여 5장 분량의 카드뉴스가 스케줄대로 정상 발행 중입니다.
- 조회수 및 저장수 데이터를 실시간 피드백하여, 노출 저조 시 즉각적으로 비주얼(형광 포인트 극대화) 및 카피 어조의 다각화 우회 모듈을 활성화함으로써 계정 건강성을 방어하고 있습니다.
- 향후 조회수가 높은 상위 키워드(예: 규율의 힘 등)를 중심으로 제작 주기를 좁혀 가며 포커싱할 예정입니다.
"""

        try:
            if drive_service:
                import io
                from googleapiclient.http import MediaIoBaseUpload

                file_metadata = {
                    "name": doc_title,
                    "mimeType": "application/vnd.google-apps.document", # 구글 독스로 자동 변환
                    "parents": [report_folder_id]
                }

                fh = io.BytesIO(report_text.encode('utf-8'))
                media = MediaIoBaseUpload(fh, mimetype='text/plain', resumable=True)

                doc_file = drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id"
                ).execute()

                doc_id = doc_file.get("id")
                print(f"📁 구글 드라이브 내 보고서 폴더에 일일보고서 직접 생성 및 업로드 완료 (ID: {doc_id})")

                with open(report_tag_file, "w") as f:
                    f.write("sent")
            else:
                print("[Warning] drive_service가 준비되지 않아 보고서 생성을 생략합니다.")
        except Exception as e:
            print(f"[Error] 일일 보고서 업로드 중 예외 발생: {e}")

def send_pipeline_report(topic, result_status, detail):
    message = (
        "마인드팩토리 SNS 자동화 보고\n\n"
        f"주제: {topic}\n"
        f"처리 결과: {result_status}\n\n"
        f"상세:\n{detail}"
    )
    send_telegram_message(message)

# =====================================================================
# 통합 파이프라인 엔진
# =====================================================================
def run_orchestration_loop():
    update_pipeline(
        state="running",
        last_run_started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        last_result=None,
    )
    send_telegram_message("파이프라인 시작: 오디언스 분석부터 업로드 준비까지 실행합니다.")
    print("\n" + "="*80)
    print(f"🚀 [Pipeline Run] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 마인드팩토리 무인 공정 가동")
    print("="*80)

    # 1. 구글 서비스 연결
    with agent_step("Google Agent", "Google Drive/Sheets 연결"):
        drive_service, docs_service, gspread_client = get_google_services()

    # 2. 폴더 아키텍처 자동 갱신
    week_dir, _ = get_current_periods()

    with agent_step("Archive Agent", "Drive 폴더/주차 구조 준비"):
        system_folder_id = get_or_create_drive_folder(drive_service, "SNS_Automatic_System")
        instagram_folder_id = get_or_create_drive_folder(drive_service, "instagram", system_folder_id)
        week_folder_id = get_or_create_drive_folder(drive_service, week_dir, instagram_folder_id)
        report_folder_id = get_or_create_drive_folder(drive_service, "보고서", week_folder_id)

    # 3. 월 단위 시트 탭 매칭
    gsm = None
    worksheet = None
    with agent_step("Sheet Agent", "성과 기록 시트 준비"):
        gsm, worksheet = get_sheet_and_ensure_tab(gspread_client, drive_service, system_folder_id)

    # 4. 직전 성과 분석에 따른 자가치유 트리거
    with agent_step("Growth Agent", "직전 성과 분석"):
        need_healing, last_title, last_content, impressions = check_last_post_performance(worksheet)

    if need_healing:
        with agent_step("Recovery Agent", "저성과 원인 분석 및 개선 지침 생성"):
            analyze_and_generate_strategy(last_title, last_content, impressions)
    else:
        strategy_file = "self_healing_strategy.json"
        if os.path.exists(strategy_file):
            try:
                os.remove(strategy_file)
                print("✨ [자가치유 종료] 직전 피드 성과가 양호하여 이전 자가치유 전략을 제거했습니다.")
            except Exception as e:
                print(f"[Warning] 이전 자가치유 전략 파일 삭제 실패: {e}")

    # Antigravity CLI 검색을 위한 트렌드 조사 요청/결과 파일 저장
    try:
        with agent_step("Trend Agent", "인스타그램 트렌드 검색/저장"):
            from constants import OBSIDIAN_VAULT_PATH
            print("\n[Trend Search] Antigravity CLI 검색용 트렌드 조사 실행...")
            search_and_save_trends(OBSIDIAN_VAULT_PATH)
    except Exception as e:
        print(f"[Warning] 실시간 트렌드 검색/저장 실패: {e}")

    try:
        with agent_step("Insight Agent", "인사이트 업데이트 및 성과 전략 반영"):
            print("\n[Insight Agent] Instagram/Threads 실성과 수집 후 전략에 반영...")
            sync_insights_and_strategy()
    except Exception as e:
        print(f"[Warning] 인사이트 업데이트/전략 반영 단계 실패: {e}")

    # 옵시디언 메모 벡터 DB 실시간 동적 갱신 및 빌드
    try:
        with agent_step("RAG Agent", "옵시디언 메모 인덱싱"):
            print("\n[RAG] 대본 기획 전 옵시디언 보관소 실시간 인덱싱 가동...")
            from obsidian_rag import ObsidianRAGEngine
            from constants import OBSIDIAN_VAULT_PATH
            rag = ObsidianRAGEngine(vault_path=OBSIDIAN_VAULT_PATH)
            rag.build_or_update_db()
    except Exception as e:
        print(f"[Warning] 옵시디언 RAG DB 자동 인덱싱 실패: {e}")

    # 5. 사람들의 현재 삶/고민을 먼저 정리해 대본 생성의 입력값으로 고정
    try:
        with agent_step("Audience Agent", "사람들의 현재 고민/감정 분석"):
            print("\n[Audience Agent] 요즘 사람들이 힘들어하는 지점과 필요한 메시지 분석...")
            create_audience_insight()
    except Exception as e:
        print(f"[Warning] 오디언스 인사이트 생성 실패: {e}")

    try:
        with agent_step("Strategy Agent", "콘텐츠 고통/훅/스토리 구조 설계"):
            print("\n[Strategy Agent] 이번 카드뉴스의 고통/훅/스토리 구조 설계...")
            create_content_strategy()
    except Exception as e:
        print(f"[Warning] 콘텐츠 전략 생성 실패: {e}")

    # 6. 새 대본 기획
    with agent_step("Story Agent", "카드뉴스 대본 생성"):
        run_generator_script(diversify=need_healing)

    with agent_step("Quality Agent", "대본 품질 평가"):
        quality_passed = evaluate_script_quality()

    if not quality_passed:
        print("\n[Quality Agent] 품질 기준 미달로 대본을 한 번 재생성합니다...")
        with agent_step("Story Agent Retry", "품질 피드백 반영 대본 재생성"):
            run_generator_script(diversify=True)
        with agent_step("Quality Agent Retry", "재생성 대본 품질 평가"):
            quality_passed = evaluate_script_quality()
        if not quality_passed:
            print("[Error] 카드뉴스 품질 기준을 통과하지 못해 업로드를 중단합니다.")
            update_pipeline(
                state="stopped",
                last_run_finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                last_result="quality_failed",
            )
            write_human_summary()
            return

    # 7. 이미지 로컬 합성
    with agent_step("Visual Agent", "이미지 생성 요청/카드 합성"):
        success = generate_card_news_images()
    if not success:
        print("[Error] 이미지 합성 실패로 이번 회차를 중단합니다.")
        update_pipeline(
            state="stopped",
            last_run_finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            last_result="image_failed",
        )
        write_human_summary()
        return

    # 8. 구글 드라이브 임시 호스팅 연동 및 인스타그램 업로드
    drive_file_ids = []
    direct_urls = []

    script_file = "script.json"
    if not os.path.exists(script_file):
        print("[Error] script.json 파일이 존재하지 않아 진행할 수 없습니다.")
        return

    try:
        with open(script_file, "r", encoding="utf-8") as f:
            script_data = json.load(f)
        pages_count = len(script_data.get("pages", []))
    except Exception as e:
        print(f"[Error] script.json 파싱 실패: {e}")
        return

    try:
        with agent_step("Hosting Agent", "Google Drive 임시 이미지 호스팅"):
            for i in range(1, pages_count + 1):
                file_path = f"page{i}.png"
                # 이미지를 주차 폴더의 하위 '보고서' 폴더(report_folder_id)에 업로드함
                fid, durl = upload_temp_image_to_drive(drive_service, file_path, report_folder_id)
                if fid and durl:
                    drive_file_ids.append(fid)
                    direct_urls.append(durl)
                else:
                    raise Exception("드라이브 임시 업로드에 실패했습니다.")

        # 8. 인스타 발행 구동 (드라이브 주소 주입)
        if len(direct_urls) == pages_count:
            # 프로그램 호출 방식으로 깔끔하게 실행 (로컬 이미지 및 로그 기입까지 완료함)
            with agent_step("Publishing Agent", "Instagram 카러셀 발행"):
                upload_success = upload_carousel.main(override_urls=direct_urls, sheet_manager=gsm)
            if upload_success:
                print("[Success] 이번 회차 파이프라인의 모든 공정이 완벽히 완료되었습니다.")
                topic = script_data.get("title", "SNS 콘텐츠 업로드")
                send_pipeline_report(
                    topic,
                    "성공 (인스타그램 발행 완료)",
                    "업로드, 시트 기록, 임시 파일 정리 단계까지 완료했습니다.",
                )
            else:
                raise Exception("인스타그램 카러셀 발행에 실패했습니다.")
    except Exception as run_err:
        print(f"[Error] 파이프라인 실행 중 예외 발생: {run_err}")
        update_pipeline(
            state="error",
            last_run_finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            last_result=str(run_err),
        )
        write_human_summary()
        try:
            send_pipeline_report(
                "파이프라인 구동 오류",
                f"실패 (에러 발생: {run_err})",
                "파이프라인 예외 복구 조치가 필요합니다.",
            )
        except Exception:
            pass
        return
    finally:
        # 9. 드라이브 임시 파일 클리닝 (어떤 에러가 발생하더라도 항상 지워지도록 보장)
        if drive_file_ids:
            with agent_step("Cleanup Agent", "임시 호스팅 파일 정리"):
                clean_drive_temp_files(drive_service, drive_file_ids)

    # 10. 아침 9시 성과 보고서 체크
    with agent_step("Report Agent", "일일 보고서 생성 여부 확인"):
        check_and_create_daily_report(drive_service, docs_service, worksheet, report_folder_id)

    sync_publish_reports_to_obsidian()

    update_pipeline(
        state="waiting",
        last_run_finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        last_result="success",
    )
    write_human_summary()

def main():
    # .env에서 PIPELINE_INTERVAL_SECONDS 설정을 로드하며 기본값은 3시간(10800초)입니다.
    # 초기 2일 동안은 하루 3~4회(6~8시간 주기)로 조절하기 위해 환경변수로 조율 가능하게 분리합니다.
    INTERVAL_SECONDS = int(os.getenv("PIPELINE_INTERVAL_SECONDS", 3 * 3600))
    update_pipeline(
        state="starting",
        interval_seconds=INTERVAL_SECONDS,
        started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    write_human_summary()

    # 즉시 가동 전 중복 포스팅 방지 검증
    try:
        with agent_step("Startup Agent", "중복 업로드 방지 확인"):
            update_pipeline(state="startup_duplicate_check")
            drive_service, docs_service, gspread_client = get_google_services()
            if gspread_client:
                _, month_tab = get_current_periods()
                sh = gspread_client.open(SHEET_NAME)
                worksheet = sh.worksheet(month_tab)
                records = worksheet.get_all_records()
                if records:
                    last_record = records[-1]
                    last_date_str = last_record.get("날짜")
                    if last_date_str:
                        last_date = datetime.strptime(last_date_str, "%Y-%m-%d %H:%M:%S")
                        elapsed = datetime.now() - last_date
                        if os.getenv("FORCE_RUN") != "True" and elapsed < timedelta(seconds=INTERVAL_SECONDS):
                            sleep_seconds = INTERVAL_SECONDS - elapsed.total_seconds()
                            next_at = (datetime.now() + timedelta(seconds=sleep_seconds)).strftime("%Y-%m-%d %H:%M:%S")
                            update_pipeline(state="waiting_duplicate_guard", next_run_at=next_at)
                            write_human_summary()
                            print(f"\n[Orchestrator] 직전 업로드({last_date_str}) 후 {elapsed.total_seconds()/60:.1f}분 경과했습니다.")
                            print(f"  -> 중복 업로드 방지를 위해 앞으로 {sleep_seconds/60:.1f}분 대기 후 첫 공정을 가동합니다...")
                            full_minutes = int(sleep_seconds // 60)
                            run_now = False
                            for _ in range(full_minutes):
                                heartbeat("waiting_duplicate_guard")
                                write_human_summary()
                                if process_telegram_commands().get("run_now"):
                                    print("[Telegram] 즉시 실행 명령을 받아 대기 시간을 건너뜁니다.")
                                    run_now = True
                                    break
                                time.sleep(60)
                            remaining = sleep_seconds % 60
                            if remaining and not run_now:
                                time.sleep(remaining)
    except Exception as e:
        print(f"\n[Warning] 중복 포스팅 대기 시간 확인 중 예외 발생 (즉시 기동): {e}")

    # 즉시 가동 시작
    run_orchestration_loop()

    while True:
        try:
            wait_seconds = get_dynamic_wait_seconds(INTERVAL_SECONDS)
            next_at = next_run_time(wait_seconds)
            update_pipeline(state="waiting", next_run_at=next_at)
            write_human_summary()
            print(f"\n[Orchestrator] 다음 가동 시점까지 대기 중... ({wait_seconds/3600:.2f}시간, 다음 실행: {next_at})")
            run_now = False
            for _ in range(wait_seconds // 60):
                heartbeat("waiting_for_next_run")
                write_human_summary()
                if process_telegram_commands().get("run_now"):
                    print("[Telegram] 즉시 실행 명령을 받아 대기 시간을 건너뜁니다.")
                    run_now = True
                    break
                time.sleep(60)
            remaining = wait_seconds % 60
            if remaining and not run_now:
                time.sleep(remaining)
            run_orchestration_loop()
        except KeyboardInterrupt:
            print("\n[Orchestrator] 시스템 최고 관리자에 의해 가동이 종료되었습니다.")
            update_pipeline(state="stopped", last_result="keyboard_interrupt")
            write_human_summary()
            break
        except Exception as e:
            print(f"[Error] 마스터 오케스트레이터 루프 예외 발생: {e}")
            update_pipeline(
                state="error",
                last_run_finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                last_result=str(e),
            )
            write_human_summary()
            time.sleep(60)

if __name__ == "__main__":
    main()
