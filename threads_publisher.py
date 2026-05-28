"""
threads_publisher.py
====================
Threads 독립 발행 모듈.
- script.json 기반으로 텍스트 포스트 발행
- Threads는 기본적으로 텍스트 전용으로 발행한다.
- main_orchestrator.py에서 Instagram 발행과 완전 독립으로 호출
"""

import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN") or os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
USER_ID = os.getenv("THREADS_USER_ID") or os.getenv("THREADS_ACCOUNT_ID") or os.getenv("INSTAGRAM_ACCOUNT_ID", "")
API_BASE = "https://graph.threads.net/v1.0"
LAST_REPORT_FILE = os.path.join("agent_runs", "threads_last_upload_report.json")


def _write_report(report: dict):
    os.makedirs("agent_runs", exist_ok=True)
    with open(LAST_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def _masked(value: str) -> str:
    if not value:
        return "EMPTY"
    if len(value) <= 10:
        return f"set(length={len(value)})"
    return f"{value[:6]}...{value[-4:]}(length={len(value)})"


def debug_credentials():
    token_source = "THREADS_ACCESS_TOKEN" if os.getenv("THREADS_ACCESS_TOKEN") else "INSTAGRAM_ACCESS_TOKEN"
    user_source = "THREADS_USER_ID" if os.getenv("THREADS_USER_ID") else ("THREADS_ACCOUNT_ID" if os.getenv("THREADS_ACCOUNT_ID") else "INSTAGRAM_ACCOUNT_ID")
    print(f"[Threads] token_source={token_source}, token={_masked(ACCESS_TOKEN)}")
    print(f"[Threads] user_source={user_source}, user_id={_masked(USER_ID)}")


def build_text_from_script(script_data: dict) -> str:
    """script.json에서 Threads용 텍스트 포스트 생성."""
    title = script_data.get("title", "")
    pages = script_data.get("pages", [])
    caption = script_data.get("caption", "")

    text_parts = []
    if title:
        text_parts.append(f"💡 {title}")

    if pages:
        p1 = pages[0]
        heading = p1.get("heading", "").replace("\n", " ").strip()
        sub_text = p1.get("sub_text", "").replace("\n", " ").strip()
        if heading:
            text_parts.append(heading)
        if sub_text:
            text_parts.append(sub_text)

    if caption:
        short_caption = caption.strip()
        if len(short_caption) > 360:
            short_caption = short_caption[:357].rstrip() + "..."
        text_parts.append(short_caption)
    else:
        text_parts.append("오늘 딱 10분만 시작하세요. 저장해두고 무너지는 날 다시 꺼내 보세요.")

    return "\n\n".join(part for part in text_parts if part).strip()


def _build_text(script_data: dict) -> str:
    return build_text_from_script(script_data)


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


def publish_text_post(text: str) -> str | None:
    """외부 호출용 텍스트 전용 발행 함수."""
    if not ACCESS_TOKEN or not USER_ID:
        print("[Threads] ACCESS_TOKEN 또는 USER_ID 미설정 — 발행 건너뜀")
        debug_credentials()
        return None
    debug_credentials()
    return _publish_text(text)


def publish_image_post(image_url: str | None, text: str) -> str | None:
    """main_orchestrator 호환 함수.

    Threads는 현재 운영 정책상 이미지 없이 텍스트만 발행한다.
    image_url 인자는 호환성 유지를 위해 받지만 사용하지 않는다.
    """
    print("[Threads] 텍스트 전용 발행 모드 — image_url은 사용하지 않습니다.")
    return publish_text_post(text)


def main(script_data: dict, image_url: str = None) -> bool:
    """
    Threads 발행 진입점.
    - script_data: script.json 파싱된 dict
    - image_url: 호환성 인자. 현재는 무시하고 텍스트 전용 발행.
    - 반환값: 성공 True / 실패 False
    """
    if not ACCESS_TOKEN or not USER_ID:
        print("[Threads] ACCESS_TOKEN 또는 USER_ID 미설정 — 발행 건너뜀")
        debug_credentials()
        return False

    report = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "text",
        "ok": False,
        "post_id": None,
    }

    try:
        text = build_text_from_script(script_data)
        print("[Threads] 텍스트 포스트 발행 시도...")
        debug_credentials()
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
