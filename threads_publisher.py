"""
threads_publisher.py
====================
Threads 독립 발행 모듈.
- script.json 기반으로 텍스트 포스트 발행
- page1.png가 존재하면 이미지 포스트로 업로드 (단건)
- 성공/실패 여부를 bool로 반환
- main_orchestrator.py에서 Instagram 발행과 완전 독립으로 호출

[Antigravity 하네스 엔지니어링 지시사항]
이 모듈은 외부 Threads Graph API를 직접 호출한다.
- ACCESS_TOKEN: .env의 INSTAGRAM_ACCESS_TOKEN (Threads와 공용)
- USER_ID: .env의 INSTAGRAM_ACCOUNT_ID (Threads USER ID와 동일)
- API 엔드포인트: https://graph.threads.net/v1.0/{USER_ID}
- 이미지 업로드 시 퍼블릭 URL이 필요하다 (drive URL 또는 PUBLIC_BASE_URL)
- 실패 시 예외를 raise하지 않고 False를 반환한다. 파이프라인을 멈추지 않는다.
"""

import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
USER_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
API_BASE = "https://graph.threads.net/v1.0"
LAST_REPORT_FILE = os.path.join("agent_runs", "threads_last_upload_report.json")


def _write_report(report: dict):
    os.makedirs("agent_runs", exist_ok=True)
    with open(LAST_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def _build_text(script_data: dict) -> str:
    """script.json에서 Threads용 짧은 텍스트 포스트 생성"""
    title = script_data.get("title", "")
    pages = script_data.get("pages", [])
    hook = ""
    if pages:
        p1 = pages[0]
        hook = p1.get("heading", "").replace("\n", " ")
        sub = p1.get("sub_text", "").replace("\n", " ")
        if sub:
            hook = f"{hook}\n{sub}"

    text_parts = []
    if title:
        text_parts.append(f"💡 {title}")
    if hook:
        text_parts.append(f"\n{hook}")
    text_parts.append("\n마인드팩토리에서 전략적으로 성장하세요.")
    return "\n".join(text_parts)


def _publish_text(text: str) -> str | None:
    """텍스트 전용 Threads 포스트 발행. 성공 시 post_id 반환."""
    url = f"{API_BASE}/{USER_ID}/threads"
    r = requests.post(url, params={
        "media_type": "TEXT",
        "text": text,
        "access_token": ACCESS_TOKEN,
    }, timeout=15)
    data = r.json()
    container_id = data.get("id")
    if not container_id:
        print(f"[Threads] 컨테이너 생성 실패: {data}")
        return None

    time.sleep(3)
    pub_url = f"{API_BASE}/{USER_ID}/threads_publish"
    pub_r = requests.post(pub_url, params={
        "creation_id": container_id,
        "access_token": ACCESS_TOKEN,
    }, timeout=15)
    pub_data = pub_r.json()
    post_id = pub_data.get("id")
    if not post_id:
        print(f"[Threads] 발행 실패: {pub_data}")
        return None
    return post_id


def _publish_image(image_url: str, text: str) -> str | None:
    """이미지 단건 Threads 포스트 발행. 성공 시 post_id 반환."""
    url = f"{API_BASE}/{USER_ID}/threads"
    r = requests.post(url, params={
        "media_type": "IMAGE",
        "image_url": image_url,
        "text": text,
        "access_token": ACCESS_TOKEN,
    }, timeout=15)
    data = r.json()
    container_id = data.get("id")
    if not container_id:
        print(f"[Threads] 이미지 컨테이너 생성 실패: {data}")
        return None

    # 컨테이너 상태 대기 (최대 60초)
    check_url = f"{API_BASE}/{container_id}"
    for _ in range(12):
        time.sleep(5)
        status_r = requests.get(check_url, params={
            "fields": "status_code",
            "access_token": ACCESS_TOKEN,
        }, timeout=10)
        status = status_r.json().get("status_code", "").upper()
        if status == "FINISHED":
            break
        if status == "ERROR":
            print(f"[Threads] 이미지 컨테이너 오류: {status_r.json()}")
            return None

    pub_url = f"{API_BASE}/{USER_ID}/threads_publish"
    pub_r = requests.post(pub_url, params={
        "creation_id": container_id,
        "access_token": ACCESS_TOKEN,
    }, timeout=15)
    pub_data = pub_r.json()
    post_id = pub_data.get("id")
    if not post_id:
        print(f"[Threads] 이미지 발행 실패: {pub_data}")
        return None
    return post_id


def main(script_data: dict, image_url: str = None) -> bool:
    """
    Threads 발행 진입점.
    - script_data: script.json 파싱된 dict
    - image_url: (선택) page1.png의 퍼블릭 URL. 없으면 텍스트 전용 포스트.
    - 반환값: 성공 True / 실패 False (예외 없음)
    """
    if not ACCESS_TOKEN or not USER_ID:
        print("[Threads] ACCESS_TOKEN 또는 USER_ID 미설정 — 발행 건너뜀")
        return False

    report = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "image" if image_url else "text",
        "ok": False,
        "post_id": None,
    }

    try:
        text = _build_text(script_data)
        if image_url:
            print(f"[Threads] 이미지 포스트 발행 시도...")
            post_id = _publish_image(image_url, text)
        else:
            print(f"[Threads] 텍스트 포스트 발행 시도...")
            post_id = _publish_text(text)

        if post_id:
            print(f"✅ [Threads] 발행 성공 (post_id: {post_id})")
            report["ok"] = True
            report["post_id"] = post_id
            _write_report(report)
            return True
        else:
            print("⚠️ [Threads] 발행 실패 (post_id 없음)")
            _write_report(report)
            return False

    except Exception as e:
        print(f"⚠️ [Threads] 예외 발생: {e}")
        report["error"] = str(e)
        _write_report(report)
        return False
