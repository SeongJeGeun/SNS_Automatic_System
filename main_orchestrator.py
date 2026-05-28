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
import threads_publisher
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


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def get_run_mode():
    return os.getenv("RUN_MODE", "research").strip().lower()


def get_rag_mode():
    return os.getenv("RAG_MODE", "search").strip().lower()


def should_skip_image_generation():
    return env_bool("SKIP_IMAGE_GENERATION", get_run_mode() == "research")


def should_skip_drive_upload():
    return env_bool("SKIP_DRIVE_UPLOAD", get_run_mode() == "research")


def should_skip_instagram_publish():
    return env_bool("SKIP_INSTAGRAM_PUBLISH", get_run_mode() == "research")


def should_skip_threads_image_publish():
    return env_bool("SKIP_THREADS_IMAGE_PUBLISH", get_run_mode() == "research")


def should_rebuild_rag_index():
    return get_rag_mode() in {"rebuild", "incremental", "build"}


def run_rag_memory_step():
    """Use Obsidian as memory without blocking every 6-hour cycle on full indexing."""
    rag_mode = get_rag_mode()
    if rag_mode in {"off", "skip", "none"}:
        print("[RAG] RAG_MODE=off → 옵시디언 RAG 단계를 건너뜁니다.")
        return

    try:
        with agent_step("RAG Agent", f"옵시디언 메모 처리 ({rag_mode})"):
            from constants import OBSIDIAN_VAULT_PATH
            print(f"\n[RAG] 모드: {rag_mode}")
            print(f"[RAG] 옵시디언 보관소: {OBSIDIAN_VAULT_PATH}")

            if should_rebuild_rag_index():
                print("[RAG] 인덱스 빌드/갱신을 실행합니다. 시간이 오래 걸릴 수 있습니다.")
                from obsidian_rag import ObsidianRAGEngine
                rag = ObsidianRAGEngine(vault_path=OBSIDIAN_VAULT_PATH)
                rag.build_or_update_db()
                print("[RAG] 인덱스 빌드/갱신 완료")
            else:
                print("[RAG] RAG_MODE=search → 기존 인덱스/옵시디언 메모를 두뇌로 유지하되, 매 회차 전체 재인덱싱은 하지 않습니다.")
    except Exception as e:
        print(f"[Warning] 옵시디언 RAG 단계 실패. 파이프라인은 계속 진행합니다: {e}")


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

위 자료들과 마인드팩토리의 브랜드 철학을 결합해 다음 포스팅에 적용할
1. 실패 원인 가설 3가지
2. 개선된 후킹 전략
3. 새로운 비주얼 컨셉
4. 재시도용 콘텐츠 방향성
을 JSON 형식으로 작성해줘.
"""

    request_file = "codex_strategy_requests.md"
    response_file = "codex_strategy_response.json"
    with open(request_file, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"[Antigravity] 전략 분석 요청 파일 생성: {request_file}")

    try:
        import subprocess
        proc = subprocess.run(
            ["antigravity", "run", "--input", request_file, "--output", response_file],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if proc.returncode != 0:
            print(f"[Warning] Antigravity 전략 실행 실패: {proc.stderr.strip()}")
    except FileNotFoundError:
        print("[Warning] Antigravity CLI가 설치되어 있지 않아 전략 요청 파일만 생성했습니다.")
    except Exception as e:
        print(f"[Warning] Antigravity 전략 실행 중 예외: {e}")

    if os.path.exists(response_file):
        try:
            with open(response_file, "r", encoding="utf-8") as f:
                strategy_json = json.load(f)
        except Exception:
            strategy_json = {"raw_response": open(response_file, encoding="utf-8").read()}
    else:
        strategy_json = {
            "hypotheses": [
                "초반 훅이 감정적 긴장감을 충분히 만들지 못했을 가능성",
                "슬라이드별 행동 지침이 추상적이어서 저장 가치가 낮았을 가능성",
                "비주얼 톤이 이전 게시물과 유사해 피드 내 차별성이 약했을 가능성",
            ],
            "hook_strategy": "첫 장에서 독자의 현재 고통을 단정적으로 명명하고, 마지막 장에서 즉시 따라 할 수 있는 루틴을 제시한다.",
            "visual_concept": "어두운 배경 + 강한 대비 텍스트 + 1슬라이드 1문장 중심의 압박감 있는 카드뉴스",
            "next_direction": "번아웃/무기력/자기혐오에서 벗어나는 3단계 행동 루틴",
        }

    with open("self_healing_strategy.json", "w", encoding="utf-8") as f:
        json.dump(strategy_json, f, ensure_ascii=False, indent=2)
    print("✅ 자가치유 전략이 self_healing_strategy.json에 저장되었습니다.")

# =====================================================================
# E. 대본 생성 에이전트 호출
# =====================================================================
def run_generator_script(diversify=False):
    print("\n[Step 1] 대본 자동 기획 가동...")
    import generator
    generator.generate_script(diversify=diversify)

# =====================================================================
# F. 구글 드라이브 임시 이미지 호스팅
# =====================================================================
def upload_temp_image_to_drive(drive_service, file_path, folder_id):
    if not drive_service:
        return None, f"mock_public_url_for_{file_path}"
    if not os.path.exists(file_path):
        return None, None

    file_metadata = {"name": os.path.basename(file_path), "parents": [folder_id]}
    media = MediaFileUpload(file_path, mimetype="image/png")
    file = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    file_id = file.get("id")

    drive_service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    print(f"  - 드라이브 임시 업로드 완료: {file_path} -> {direct_url}")
    return file_id, direct_url


def clean_drive_temp_files(drive_service, file_ids):
    if not drive_service:
        return
    print("\n[Step 4] 구글 드라이브 내 임시 호스팅 이미지 삭제 중...")
    for fid in file_ids:
        try:
            drive_service.files().delete(fileId=fid).execute()
            print(f"  - 드라이브 임시 파일 삭제 성공: ID {fid}")
        except Exception as e:
            print(f"  - 드라이브 임시 파일 삭제 실패: ID {fid}, 이유: {e}")

# =====================================================================
# G. 일일 보고서 생성
# =====================================================================
def check_and_create_daily_report(drive_service, docs_service, worksheet, report_folder_id):
    now = datetime.now()
    report_flag_file = f"report_sent_{now.strftime('%Y%m%d')}.txt"

    if now.hour < 9 or os.path.exists(report_flag_file):
        return

    print("\n📢 [일일 보고] 아침 9시 이후가 되어 일일 성과 보고서를 생성합니다...")
    report_content = f"# 마인드팩토리 SNS 일일 성과 보고 ({now.strftime('%Y-%m-%d')})\n\n"
    report_content += "## 1. 오늘의 업로드 현황\n"

    rows = []
    if worksheet:
        try:
            all_records = worksheet.get_all_records()
            today_str = now.strftime('%Y-%m-%d')
            rows = [r for r in all_records if str(r.get('날짜', '')).startswith(today_str)]
        except Exception as e:
            print(f"[Warning] 시트 데이터 읽기 실패: {e}")

    if not rows:
        report_content += "- 아직 오늘 업로드 기록이 없습니다.\n"
    else:
        for r in rows:
            report_content += f"- {r.get('타이틀', '제목 없음')} / 미디어ID: {r.get('미디어ID')} / 조회수: {r.get('조회수', 'N/A')}\n"

    report_content += "\n## 2. 시스템 상태\n- 자동 기획/생성/업로드 파이프라인 정상 가동 중\n"

    report_filename = f"daily_report_{now.strftime('%Y%m%d')}.md"
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(report_content)

    if drive_service and docs_service:
        file_metadata = {
            "name": report_filename,
            "mimeType": "application/vnd.google-apps.document",
            "parents": [report_folder_id]
        }
        doc = drive_service.files().create(body=file_metadata, fields="id").execute()
        doc_id = doc.get("id")
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={
                "requests": [
                    {"insertText": {"location": {"index": 1}, "text": report_content}}
                ]
            }
        ).execute()
        print(f"✅ 구글 Docs 일일 보고서 생성 완료: {doc_id}")
    else:
        print(f"✅ 로컬 일일 보고서 생성 완료: {report_filename}")

    with open(report_flag_file, "w") as f:
        f.write("sent")

# =====================================================================
# H. SNS 채널별 독립 발행
# =====================================================================
def run_sns_publish(script_data, direct_urls, gsm):
    topic = script_data.get("title", "SNS 콘텐츠")
    instagram_ok = False
    threads_ok = False

    if should_skip_instagram_publish():
        print("[Instagram] SKIP_INSTAGRAM_PUBLISH/RUN_MODE=research → Instagram 발행 전체를 건너뜁니다.")
    else:
        try:
            upload_success = upload_carousel.main(override_urls=direct_urls, sheet_manager=gsm)
            instagram_ok = bool(upload_success)
        except Exception as inst_err:
            print(f"⚠️ [Instagram] 예외 발생: {inst_err} — 패스")
            notify_publish_failure("Instagram", topic, "이번 회차 인스타 발행 건너뜀. 다음 회차(21600초 후)에 재시도.")

    if should_skip_threads_image_publish():
        print("[Threads] SKIP_THREADS_IMAGE_PUBLISH/RUN_MODE=research → Threads 이미지 발행을 건너뜁니다.")
    else:
        try:
            post_id = threads_publisher.publish_image_post(direct_urls[0], threads_publisher.build_text_from_script(script_data))
            if post_id:
                threads_ok = True
            else:
                print("⚠️ [Threads] 발행 실패 (post_id 없음)")
                notify_publish_failure("Threads", topic, "이번 회차 Threads 발행 건너뜀. 다음 회차에 재시도.")
        except Exception as th_err:
            print(f"⚠️ [Threads] 예외 발생: {th_err} — 패스")
            notify_publish_failure("Threads", topic, "이번 회차 Threads 발행 건너뜀. 다음 회차에 재시도.")

    return instagram_ok, threads_ok


def notify_publish_failure(channel, topic, detail):
    message = (
        f"⚠️ [{channel} 발행 실패]\n"
        f"주제: {topic}\n"
        f"{detail}"
    )
    send_telegram_message(message)


def finish_research_cycle(script_data):
    topic = script_data.get("title", "SNS 콘텐츠")
    print("[Pipeline] RUN_MODE=research → 이미지 생성/Drive 업로드/SNS 발행 없이 기획 산출물만 저장하고 종료합니다.")
    send_telegram_message(
        "✅ [Research Cycle 완료]\n"
        f"주제: {topic}\n"
        "이미지 생성과 SNS 발행은 건너뛰고, 대본/전략 산출물만 저장했습니다."
    )
    update_pipeline(
        state="waiting",
        last_run_finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        last_result="research_success",
    )
    write_human_summary()

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

    # Antigravity CLI 트렌드 조사
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

    # 옵시디언 RAG 메모리 처리
    run_rag_memory_step()

    # 5. 오디언스 분석
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

    # 6. 대본 기획
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

    if should_skip_image_generation():
        finish_research_cycle(script_data)
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

    if should_skip_drive_upload():
        print("[Pipeline] SKIP_DRIVE_UPLOAD=true → Drive 임시 업로드와 SNS 발행을 건너뜁니다.")
        finish_research_cycle(script_data)
        return

    # 9. 구글 드라이브 임시 호스팅
    drive_file_ids = []
    direct_urls = []

    try:
        with agent_step("Hosting Agent", "Google Drive 임시 이미지 호스팅"):
            for i in range(1, pages_count + 1):
                file_path = f"page{i}.png"
                fid, durl = upload_temp_image_to_drive(drive_service, file_path, report_folder_id)
                if fid and durl:
                    drive_file_ids.append(fid)
                    direct_urls.append(durl)
                else:
                    raise Exception(f"드라이브 임시 업로드 실패: {file_path}")
    except Exception as host_err:
        print(f"[Error] 드라이브 호스팅 실패: {host_err}")
        update_pipeline(
            state="error",
            last_run_finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            last_result=str(host_err),
        )
        write_human_summary()
        return

    # 10. Instagram + Threads 독립 발행 (실패해도 파이프라인 계속)
    try:
        instagram_ok, threads_ok = run_sns_publish(script_data, direct_urls, gsm)

        topic = script_data.get("title", "SNS 콘텐츠")
        if instagram_ok or threads_ok:
            result_summary = (
                f"Instagram: {'✅ 성공' if instagram_ok else '⚠️ 실패'} | "
                f"Threads: {'✅ 성공' if threads_ok else '⚠️ 실패'}"
            )
            print(f"[Pipeline] 발행 결과 — {result_summary}")
        else:
            print("[Pipeline] Instagram/Threads 모두 실패 — 다음 회차 재시도")

    finally:
        # 11. 드라이브 임시 파일 클리닝 (항상 실행)
        if drive_file_ids:
            with agent_step("Cleanup Agent", "임시 호스팅 파일 정리"):
                clean_drive_temp_files(drive_service, drive_file_ids)

    # 12. 아침 9시 성과 보고서
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
    INTERVAL_SECONDS = int(os.getenv("PIPELINE_INTERVAL_SECONDS", 6 * 3600))  # 기본 6시간
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