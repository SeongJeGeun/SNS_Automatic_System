# instagram_token_manager.py
import os
import re
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

STATUS_JSON = os.path.join("agent_runs", "agent_status.json")

def load_instagram_token():
    load_dotenv()
    return {
        "access_token": os.getenv("INSTAGRAM_ACCESS_TOKEN", ""),
        "account_id": os.getenv("INSTAGRAM_ACCOUNT_ID", ""),
        "api_version": os.getenv("INSTAGRAM_API_VERSION", "v19.0"),
        "app_id": os.getenv("INSTAGRAM_APP_ID", ""),
        "app_secret": os.getenv("INSTAGRAM_APP_SECRET", ""),
        "expires_at": os.getenv("INSTAGRAM_TOKEN_EXPIRES_AT", ""),
        "short_lived_token": os.getenv("SHORT_LIVED_INSTAGRAM_ACCESS_TOKEN", "")
    }

def mask_token(token):
    if not token:
        return "미설정 (NULL)"
    if len(token) <= 12:
        return "**********"
    return token[:6] + "****************" + token[-6:]

def save_token_securely(new_token, expires_at=None):
    env_path = ".env"
    bak_path = ".env.bak"

    # 1. 기존 .env 백업 생성
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                env_content = f.read()
            with open(bak_path, "w", encoding="utf-8") as f:
                f.write(env_content)
        except Exception as e:
            print(f"[Warning] .env 백업 생성 중 오류 발생: {e}")

    # 2. .env 파일 파싱 및 갱신
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    token_updated = False
    expires_updated = False

    new_lines = []
    for line in lines:
        if line.strip().startswith("INSTAGRAM_ACCESS_TOKEN="):
            new_lines.append(f"INSTAGRAM_ACCESS_TOKEN={new_token}\n")
            token_updated = True
        elif expires_at and line.strip().startswith("INSTAGRAM_TOKEN_EXPIRES_AT="):
            new_lines.append(f"INSTAGRAM_TOKEN_EXPIRES_AT={expires_at}\n")
            expires_updated = True
        else:
            new_lines.append(line)

    if not token_updated:
        new_lines.append(f"INSTAGRAM_ACCESS_TOKEN={new_token}\n")
    if expires_at and not expires_updated:
        new_lines.append(f"INSTAGRAM_TOKEN_EXPIRES_AT={expires_at}\n")

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        os.environ["INSTAGRAM_ACCESS_TOKEN"] = new_token
        if expires_at:
            os.environ["INSTAGRAM_TOKEN_EXPIRES_AT"] = expires_at
        print("✅ .env 내 Instagram 액세스 토큰 정보 갱신 완료")
        return True
    except Exception as e:
        print(f"[Error] .env 토큰 쓰기 실패: {e}")
        return False

def validate_token():
    creds = load_instagram_token()
    token = creds["access_token"]
    account_id = creds["account_id"]
    version = creds["api_version"]

    if not token:
        return False, "INSTAGRAM_ACCESS_TOKEN이 .env에 설정되지 않았습니다."

    # 1단계: 사용자 기본 정보 조회로 검증 시도
    url = f"https://graph.facebook.com/{version}/me"
    params = {
        "fields": "id,name",
        "access_token": token
    }

    try:
        res = requests.get(url, params=params, timeout=10)
        res_data = res.json()

        if res.status_code == 200:
            # 2단계: 매칭되는 인스타 계정이 있는 경우 교차 검증
            if account_id:
                test_url = f"https://graph.facebook.com/{version}/{account_id}"
                test_params = {
                    "fields": "username,name",
                    "access_token": token
                }
                test_res = requests.get(test_url, params=test_params, timeout=10)
                if test_res.status_code != 200:
                    return False, f"인스타그램 계정 정보({account_id})에 대한 읽기 권한이 없거나 계정 ID 불일치: {test_res.text}"
            return True, "유효함"
        else:
            err_msg = res_data.get("error", {}).get("message", "알 수 없는 API 에러")
            code = res_data.get("error", {}).get("code", 0)
            return False, f"API Error {code}: {err_msg}"

    except Exception as e:
        return False, f"네트워크/요청 예외: {str(e)}"

def get_token_expiry_status():
    creds = load_instagram_token()
    expires_at_str = creds["expires_at"]

    if not expires_at_str:
        return "warning", "만료일 미기록", None

    try:
        # ISO 또는 YYYY-MM-DD 포맷 파싱 시도
        if "T" in expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str.split("+")[0]) # timezone 단순화
        else:
            expires_at = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")

        now = datetime.now()
        delta = expires_at - now
        days_left = delta.days

        if days_left <= 0:
            return "error", f"토큰 만료됨 (D-{abs(days_left)})", days_left
        elif days_left <= 10:
            return "warning", f"D-{days_left} (만료 임박)", days_left
        else:
            return "ok", f"D-{days_left} (유효함)", days_left

    except Exception as e:
        return "warning", f"만료일 포맷 오류: {str(e)}", None

def refresh_long_lived_token():
    creds = load_instagram_token()
    token = creds["access_token"]
    app_id = creds["app_id"]
    app_secret = creds["app_secret"]

    if not token:
        return False, "갱신할 토큰이 없습니다."

    # 만약 Graph API (Facebook) 장기 토큰 리프레시 스펙인 경우:
    # GET /oauth/access_token?grant_type=fb_exchange_token&client_id={app_id}&client_secret={app_secret}&fb_exchange_token={token}
    if app_id and app_secret:
        url = "https://graph.facebook.com/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": token
        }
    else:
        # Instagram Basic Display API의 리프레시 스펙인 경우:
        # GET https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token={token}
        url = "https://graph.instagram.com/refresh_access_token"
        params = {
            "grant_type": "ig_refresh_token",
            "access_token": token
        }

    try:
        res = requests.get(url, params=params, timeout=10)
        res_data = res.json()

        if res.status_code == 200:
            new_token = res_data.get("access_token")
            expires_in = res_data.get("expires_in", 5184000) # 디폴트 60일

            # 새 만료일 계산
            new_expiry = (datetime.now() + timedelta(seconds=expires_in)).strftime("%Y-%m-%d %H:%M:%S")

            if new_token:
                save_token_securely(new_token, new_expiry)
                return True, "토큰 리프레시 성공"
            return False, "응답에 access_token이 누락되었습니다."
        else:
            err = res_data.get("error", {}).get("message", "갱신 실패")
            return False, f"API Error: {err}"
    except Exception as e:
        return False, f"네트워크 요청 실패: {str(e)}"

def exchange_short_lived_to_long_lived():
    creds = load_instagram_token()
    short_token = creds["short_lived_token"]
    app_secret = creds["app_secret"]
    app_id = creds["app_id"]

    if not short_token:
        return False, "교환할 short_lived_token이 .env에 정의되어 있지 않습니다."

    # Facebook Graph API를 사용하는 장기 토큰 교환 스키마:
    # GET /oauth/access_token?grant_type=fb_exchange_token&client_id={app_id}&client_secret={app_secret}&fb_exchange_token={short_token}
    if app_id and app_secret:
        url = "https://graph.facebook.com/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token
        }
    else:
        # Instagram Basic Display API의 경우
        url = "https://graph.instagram.com/access_token"
        params = {
            "grant_type": "ig_exchange_token",
            "client_secret": app_secret,
            "access_token": short_token
        }

    try:
        res = requests.get(url, params=params, timeout=10)
        res_data = res.json()

        if res.status_code == 200:
            long_token = res_data.get("access_token")
            expires_in = res_data.get("expires_in", 5184000)
            new_expiry = (datetime.now() + timedelta(seconds=expires_in)).strftime("%Y-%m-%d %H:%M:%S")
            if long_token:
                save_token_securely(long_token, new_expiry)
                return True, "장기 토큰 교환 성공"
            return False, "장기 토큰 데이터 누락"
        else:
            err = res_data.get("error", {}).get("message", "교환 실패")
            return False, f"API Error: {err}"
    except Exception as e:
        return False, f"네트워크 요청 예외: {str(e)}"

def perform_daily_health_check_and_refresh():
    """매일 1회 또는 실행 전 호출되어 토큰 상태를 검사하고 만료 10일 전일 경우 자동 갱신합니다."""
    print("[Instagram Token health check] 가동...")
    ok, message = validate_token()
    if not ok:
        print(f"⚠️ [Token Alert] Instagram 토큰 검증 실패: {message}")
        # 텔레그램 경보 전송 시도
        try:
            from telegram_agent import send_telegram_message
            send_telegram_message(f"🚨 [인스타 연동 경고] 토큰 검증에 실패했습니다: {message}\n재인증이 필요합니다.")
        except Exception:
            pass
        return "error", message

    status, exp_msg, days_left = get_token_expiry_status()
    print(f"  - 토큰 정보: {exp_msg}")

    if status == "error":
        return "error", f"토큰 만료됨: {exp_msg}"

    if days_left is not None and days_left <= 10:
        print("⚡ [Auto Refresh] 토큰 만료가 10일 이하로 남아 자동 갱신을 실행합니다...")
        success, refresh_msg = refresh_long_lived_token()
        if success:
            print(f"✅ 자동 갱신 성공: {refresh_msg}")
            try:
                from telegram_agent import send_telegram_message
                send_telegram_message(f"ℹ️ [인스타 연동] 만료 예정인 토큰을 자동 리프레시 및 연장했습니다.")
            except Exception:
                pass
            return "ok", "자동 갱신 완료"
        else:
            print(f"❌ 자동 갱신 실패: {refresh_msg}")
            try:
                from telegram_agent import send_telegram_message
                send_telegram_message(f"⚠️ [인스타 연동] 만료 임박 토큰 자동 리프레시 실패: {refresh_msg}\n수동 확인이 필요합니다.")
            except Exception:
                pass
            return "warning", f"자동 갱신 실패: {refresh_msg}"

    return status, exp_msg

if __name__ == "__main__":
    status, msg = perform_daily_health_check_and_refresh()
    print(f"최종 상태: {status} ({msg})")
