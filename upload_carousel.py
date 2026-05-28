import os
import sys
import json
import requests
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google_sheet_manager import GoogleSheetManager
from obsidian_publish_sync import sync_publish_report

load_dotenv()

# =====================================================================
# [설정 변수]
# =====================================================================
ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
API_VERSION = os.getenv("INSTAGRAM_API_VERSION", "v19.0")

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
IMGUR_CLIENT_ID = os.getenv("IMGUR_CLIENT_ID", "")
MANUAL_IMAGE_URLS = []
PUBLISH_COOLDOWN_FILE = os.path.join("agent_runs", "instagram_publish_cooldown.json")
LAST_UPLOAD_REPORT_FILE = os.path.join("agent_runs", "instagram_last_upload_report.json")


def write_upload_report(report):
    os.makedirs("agent_runs", exist_ok=True)
    with open(LAST_UPLOAD_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    try:
        sync_publish_report("instagram", LAST_UPLOAD_REPORT_FILE)
    except Exception as exc:
        print(f"[Warning] Obsidian 발행 데이터 동기화 실패: {exc}")


def extract_graph_error(response_data):
    error = response_data.get("error", {}) if isinstance(response_data, dict) else {}
    return {
        "message": error.get("message", ""),
        "type": error.get("type", ""),
        "code": error.get("code"),
        "subcode": error.get("error_subcode"),
        "user_title": error.get("error_user_title", ""),
        "user_message": error.get("error_user_msg", ""),
        "fbtrace_id": error.get("fbtrace_id", ""),
    }


def is_action_blocked(error_info):
    return error_info.get("code") == 4 or error_info.get("subcode") == 2207051


def should_retry_publish(error_info):
    if is_action_blocked(error_info):
        return False
    return error_info.get("code") in {-1, 1, 2}


def _parse_time(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except ValueError:
            pass
    return None


def _cooldown_until(payload):
    explicit_until = _parse_time(payload.get("cooldown_until"))
    if explicit_until:
        return explicit_until
    created_at = _parse_time(payload.get("created_at"))
    wait_hours = float(payload.get("recommended_wait_hours", 24))
    if not created_at:
        return None
    return created_at + timedelta(hours=wait_hours)


def read_publish_cooldown():
    if not os.path.exists(PUBLISH_COOLDOWN_FILE):
        return None
    try:
        with open(PUBLISH_COOLDOWN_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        until = _cooldown_until(payload)
        if not until:
            return None
        now = datetime.now()
        if now < until:
            return {
                "active": True,
                "cooldown_until": until.strftime("%Y-%m-%d %H:%M:%S"),
                "remaining_seconds": int((until - now).total_seconds()),
                "payload": payload,
            }
        return {"active": False, "cooldown_until": until.strftime("%Y-%m-%d %H:%M:%S"), "payload": payload}
    except Exception as exc:
        print(f"[Warning] Instagram cooldown file read failed: {exc}")
        return None


def write_publish_cooldown(error_info):
    os.makedirs("agent_runs", exist_ok=True)
    created_at = datetime.now()
    until = created_at + timedelta(hours=24)
    payload = {
        "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "cooldown_until": until.strftime("%Y-%m-%d %H:%M:%S"),
        "reason": "instagram_action_blocked",
        "recommended_wait_hours": 24,
        "error": error_info,
    }
    with open(PUBLISH_COOLDOWN_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def maybe_skip_for_cooldown(stage="pre_container"):
    cooldown = read_publish_cooldown()
    if not cooldown or not cooldown.get("active"):
        return False

    report = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ok": False,
        "skipped": True,
        "skip_stage": stage,
        "reason": "instagram_publish_cooldown_active",
        "cooldown_until": cooldown.get("cooldown_until"),
        "remaining_seconds": cooldown.get("remaining_seconds"),
        "published_id": None,
    }
    write_upload_report(report)
    print(
        "[Instagram] cooldown active -> skip container creation. "
        f"until={cooldown.get('cooldown_until')}, "
        f"remaining={cooldown.get('remaining_seconds')}s"
    )
    return True

# =====================================================================
# 1. 캡션 생성 (script.json 연동)
# =====================================================================
def get_script_data():
    script_file = "script.json"
    if not os.path.exists(script_file):
        raise FileNotFoundError(f"[Error] {script_file} 파일을 찾을 수 없습니다. 먼저 1단계를 완료하세요.")

    with open(script_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def build_caption(data):
    title = data.get("title", "오늘의 AI 트렌드")
    pages = data.get("pages", [])

    caption_parts = []
    caption_parts.append(f"🔥 {title} 🔥\n")

    for page in pages:
        p_num = page.get("page", 0)
        p_heading = page.get("heading", "").replace("\n", " ")
        p_sub = page.get("sub_text", "").replace("\n", " ")
        p_text = f"{p_heading} - {p_sub}" if p_sub else p_heading
        caption_parts.append(f"{p_num}장: {p_text}")

    caption_parts.append("\n📌 타협 없는 규율과 몰입, 마인드팩토리에서 당신의 한계를 깨부수세요.\n")
    caption_parts.append("#동기부여 #자기계발 #마인드팩토리 #규율 #몰입 #멘탈팩폭 #갓생 #성공루틴")

    return "\n".join(caption_parts)

# =====================================================================
# 2. 이미지 퍼블릭 URL 준비 (폴백용)
# =====================================================================
def get_image_urls(pages_count=None):
    pages_count = pages_count or len(get_script_data().get("pages", [])) or 5
    if MANUAL_IMAGE_URLS and len(MANUAL_IMAGE_URLS) == pages_count:
        return MANUAL_IMAGE_URLS

    image_filenames = [f"page{i}.png" for i in range(1, pages_count + 1)]

    for img_name in image_filenames:
        if not os.path.exists(img_name):
            raise FileNotFoundError(f"로컬 이미지 '{img_name}' 파일이 존재하지 않습니다.")

    if PUBLIC_BASE_URL:
        return [f"{PUBLIC_BASE_URL.rstrip('/')}/{img_name}" for img_name in image_filenames]

    if IMGUR_CLIENT_ID:
        imgur_urls = []
        for img_name in image_filenames:
            url = upload_to_imgur(img_name)
            if url:
                imgur_urls.append(url)
                time.sleep(1)
            else:
                raise RuntimeError(f"Imgur 업로드 실패: {img_name}")
        return imgur_urls

    raise ValueError(
        "인스타그램 그래프 API 업로드 시 퍼블릭 URL이 반드시 필요합니다. "
        "PUBLIC_BASE_URL 또는 구글 드라이브 임시 업로드 아키텍처를 연동해주십시오."
    )


def upload_to_imgur(file_path):
    headers = {"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"}
    url = "https://api.imgur.com/3/image"
    try:
        with open(file_path, "rb") as img:
            payload = {"image": img.read()}
            res = requests.post(url, headers=headers, files=payload)
            res_data = res.json()
            if res.status_code == 200 and res_data.get("success"):
                return res_data["data"]["link"]
            return None
    except Exception:
        return None

# =====================================================================
# 3. Instagram Graph API를 통한 업로드 프로세스
# =====================================================================
def wait_for_container_status(container_id):
    check_url = f"https://graph.facebook.com/{API_VERSION}/{container_id}"
    params = {
        "fields": "status_code",
        "access_token": ACCESS_TOKEN,
    }

    print(f"  - 컨테이너 {container_id} 상태 확인 중...")
    for _ in range(15):
        try:
            res = requests.get(check_url, params=params, timeout=10)
            res_data = res.json()
            status = res_data.get("status_code", "").upper()
            if status == "FINISHED":
                print(f"  - 컨테이너 {container_id} 준비 완료 (FINISHED)")
                return True
            elif status == "ERROR":
                raise RuntimeError(f"컨테이너 생성 오류 상태 감지: {res_data}")
            else:
                print(f"    - 현재 상태: {status or 'PENDING'}... 5초 대기 후 재조회")
                time.sleep(5)
        except Exception as e:
            print(f"    - 상태 파싱 중 경고: {e}")
            time.sleep(5)
    return False


def upload_to_instagram(image_urls, caption):
    if not ACCESS_TOKEN or not INSTAGRAM_ACCOUNT_ID:
        raise ValueError("INSTAGRAM_ACCESS_TOKEN 또는 INSTAGRAM_ACCOUNT_ID가 .env에 설정되지 않았습니다.")

    if maybe_skip_for_cooldown(stage="pre_container"):
        return None

    base_url = f"https://graph.facebook.com/{API_VERSION}/{INSTAGRAM_ACCOUNT_ID}"

    child_ids = []
    report = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "image_count": len(image_urls),
        "child_container_ids": [],
        "parent_container_id": None,
        "published_id": None,
        "ok": False,
    }
    print("\n[Step 1] 자식 미디어 컨테이너(각 슬라이드) 생성 중...")

    for i, img_url in enumerate(image_urls):
        params = {
            "image_url": img_url,
            "is_carousel_item": "true",
            "access_token": ACCESS_TOKEN,
        }
        res = requests.post(f"{base_url}/media", params=params)
        res_data = res.json()

        if res.status_code == 200 and "id" in res_data:
            child_id = res_data["id"]
            child_ids.append(child_id)
            report["child_container_ids"].append(child_id)
            print(f"  - 슬라이드 {i+1} 컨테이너 생성 성공 (ID: {child_id})")
        else:
            report["error_stage"] = "child_container_create"
            report["error"] = extract_graph_error(res_data)
            write_upload_report(report)
            raise RuntimeError(f"슬라이드 {i+1} 컨테이너 생성 실패: {res_data}")

        time.sleep(2)

    print("\n[Step 1-2] 각 자식 미디어의 Meta 서버 다운로드 상태 검증...")
    for cid in child_ids:
        if not wait_for_container_status(cid):
            print(f"[Warning] 컨테이너 {cid} 상태 확인 타임아웃. 발행 프로세스를 강행합니다.")

    print("\n[Step 2] 부모 카러셀 컨테이너 생성 중...")
    children_str = ",".join(child_ids)

    params = {
        "media_type": "CAROUSEL",
        "children": children_str,
        "caption": caption,
        "access_token": ACCESS_TOKEN,
    }

    res = requests.post(f"{base_url}/media", params=params)
    res_data = res.json()

    if res.status_code == 200 and "id" in res_data:
        parent_container_id = res_data["id"]
        report["parent_container_id"] = parent_container_id
        print(f"  - 부모 카러셀 컨테이너 생성 성공 (ID: {parent_container_id})")
    else:
        report["error_stage"] = "parent_container_create"
        report["error"] = extract_graph_error(res_data)
        write_upload_report(report)
        raise RuntimeError(f"부모 카러셀 컨테이너 생성 실패: {res_data}")

    if not wait_for_container_status(parent_container_id):
        print(f"[Warning] 부모 컨테이너 {parent_container_id} 상태 확인 타임아웃. 발행 프로세스를 강행합니다.")

    print("\n[Step 3] 인스타그램 최종 발행(Publish) 진행 중...")
    publish_params = {
        "creation_id": parent_container_id,
        "access_token": ACCESS_TOKEN,
    }

    published_id = None
    for attempt in range(1, 4):
        print(f"  - 발행 시도 {attempt}회차...")
        publish_res = requests.post(f"{base_url}/media_publish", params=publish_params)
        publish_data = publish_res.json()

        if publish_res.status_code == 200 and "id" in publish_data:
            published_id = publish_data["id"]
            report["published_id"] = published_id
            report["ok"] = True
            report["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            write_upload_report(report)
            print(f"\n🎉 인스타그램 게시물 슬라이드 발행 성공! (게시물 ID: {published_id})")
            break
        else:
            print(f"  - 시도 실패: {publish_data}")
            error_info = extract_graph_error(publish_data)
            report["error_stage"] = "media_publish"
            report["error"] = error_info
            report["failed_attempt"] = attempt
            write_upload_report(report)
            if is_action_blocked(error_info):
                write_publish_cooldown(error_info)
                raise RuntimeError(
                    "Instagram이 현재 계정의 발행 행동을 제한했습니다. "
                    "자동 재시도는 중단했고 24시간 쿨다운을 기록했습니다. "
                    f"응답: {publish_data}"
                )
            if attempt < 3 and should_retry_publish(error_info):
                print("  - 10초 후 재시도합니다...")
                time.sleep(10)
            else:
                raise RuntimeError(f"인스타그램 최종 발행에 완전히 실패했습니다. 응답: {publish_data}")

    return published_id

# =====================================================================
# Main
# =====================================================================
def main(override_urls=None, sheet_manager=None):
    print("=" * 60)
    print(" Instagram Carousel Auto Uploader (Meta Graph API) ")
    print("=" * 60)

    if maybe_skip_for_cooldown(stage="pre_upload_main"):
        return None

    script_data = get_script_data()
    title = script_data.get("title", "오늘의 AI 트렌드")

    caption = build_caption(script_data)
    print("\n[Info] 빌드된 포스팅 캡션 본문:")
    print("-" * 50)
    print(caption)
    print("-" * 50)

    if override_urls:
        image_urls = override_urls
        print("[Info] 주입된 구글 드라이브 이미지 호스팅 URL 목록을 사용합니다.")
    else:
        image_urls = get_image_urls(len(script_data.get("pages", [])))

    published_id = upload_to_instagram(image_urls, caption)

    if published_id:
        try:
            print("\n[Step 4] 구글 시트에 업로드 로그 기록 중...")
            content_summary = "\n".join([
                f"{p.get('heading', '')} - {p.get('sub_text', '')}".replace("\n", " ")
                for p in script_data.get("pages", [])
            ])
            if sheet_manager:
                sheet_manager.append_upload_row(published_id, title, content_summary)
            else:
                gsm = GoogleSheetManager()
                gsm.append_upload_row(published_id, title, content_summary)
        except Exception as e:
            print(f"[Warning] 구글 시트 로그 기록 실패: {e}")

        print("\n[Step 5] 업로드 완료에 따른 임시 로컬 이미지 제거 중...")
        for i in range(1, len(script_data.get("pages", [])) + 1):
            img_path = f"page{i}.png"
            if os.path.exists(img_path):
                try:
                    os.remove(img_path)
                    print(f"  - 임시 파일 삭제 성공: {img_path}")
                except Exception as ex:
                    print(f"  - 임시 파일 삭제 실패 ({img_path}): {ex}")

    return published_id


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ [Error] 업로드 비정상 종료: {e}")
        sys.exit(1)
