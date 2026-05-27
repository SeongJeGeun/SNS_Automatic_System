import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID = os.getenv("THREADS_USER_ID", "")
API_VERSION = "v1.0"
BASE_URL = f"https://graph.threads.net/{API_VERSION}"
POST_INSIGHT_METRICS = (
    "views",
    "likes",
    "replies",
    "reposts",
    "quotes",
)


def get_threads_post_ids(limit=10):
    """Threads API에서 최근 포스트 ID 목록을 가져온다."""
    if not is_token_configured():
        print("[Warning] 유효한 Threads ACCESS_TOKEN이 설정되지 않았습니다.")
        return []

    threads_url = f"{BASE_URL}/me/threads"
    params = {
        "fields": "id",
        "limit": limit,
        "access_token": ACCESS_TOKEN,
    }

    try:
        res = requests.get(threads_url, params=params, timeout=10)
        res_data = res.json()
        if res.status_code == 200 and "data" in res_data:
            return [item["id"] for item in res_data["data"] if item.get("id")]
        print(f"[Warning] Threads 포스트 목록 조회 실패: {res_data}")
    except Exception as e:
        print(f"[Warning] Threads 포스트 목록 API 호출 중 예외: {e}")
    return []


def get_threads_metrics(post_id):
    """Threads 포스트별 조회, 반응, 답글율을 가져온다."""
    metrics = {
        "post_id": str(post_id),
        "views": 0,
        "likes": 0,
        "replies": 0,
        "reposts": 0,
        "quotes": 0,
        "reply_rate": 0.0,
    }

    if not is_token_configured():
        print("[Warning] 유효한 Threads ACCESS_TOKEN이 설정되지 않았습니다.")
        return metrics

    insights_url = f"{BASE_URL}/{post_id}/insights"
    params = {
        "metric": ",".join(POST_INSIGHT_METRICS),
        "access_token": ACCESS_TOKEN,
    }

    try:
        res = requests.get(insights_url, params=params, timeout=10)
        res_data = res.json()
        if res.status_code == 200 and "data" in res_data:
            for item in res_data["data"]:
                metric_name = item.get("name")
                if metric_name in metrics:
                    metrics[metric_name] = extract_metric_value(item)
        else:
            print(f"[Warning] Threads 포스트 인사이트 조회 실패 ({post_id}): {res_data}")
    except Exception as e:
        print(f"[Warning] Threads 포스트 인사이트 API 호출 중 예외 ({post_id}): {e}")

    metrics["reply_rate"] = safe_rate(metrics["replies"], metrics["views"])
    return metrics


def get_threads_account_insights():
    """Threads 계정 팔로워 수와 최근 7일 프로필 방문수를 가져온다."""
    insights = {
        "user_id": THREADS_USER_ID,
        "followers_count": 0,
        "profile_visits_7d": 0,
    }

    if not is_token_configured():
        print("[Warning] 유효한 Threads ACCESS_TOKEN이 설정되지 않았습니다.")
        return insights

    profile_url = f"{BASE_URL}/me"
    profile_params = {
        "fields": "followers_count",
        "access_token": ACCESS_TOKEN,
    }

    try:
        res = requests.get(profile_url, params=profile_params, timeout=10)
        res_data = res.json()
        if res.status_code == 200:
            insights["user_id"] = str(res_data.get("id") or THREADS_USER_ID)
            insights["followers_count"] = to_int(res_data.get("followers_count", 0))
        else:
            print(f"[Warning] Threads 계정 기본 정보 조회 실패: {res_data}")
    except Exception as e:
        print(f"[Warning] Threads 계정 기본 정보 API 호출 중 예외: {e}")

    insights["profile_visits_7d"] = fetch_profile_visits_7d()
    return insights


def fetch_profile_visits_7d():
    insights_url = f"{BASE_URL}/me/threads_insights"
    until = int(time.time())
    since = until - (7 * 24 * 60 * 60)
    params = {
        "metric": "views",
        "period": "day",
        "since": since,
        "until": until,
        "access_token": ACCESS_TOKEN,
    }

    try:
        res = requests.get(insights_url, params=params, timeout=10)
        res_data = res.json()
        if res.status_code == 200 and "data" in res_data:
            return sum_metric_values(res_data["data"])
        print(f"[Warning] Threads 계정 인사이트 조회 실패: {res_data}")
    except Exception as e:
        print(f"[Warning] Threads 계정 인사이트 API 호출 중 예외: {e}")
    return 0


def sum_metric_values(items):
    total = 0
    for item in items:
        if item.get("values"):
            total += sum(to_int(value.get("value", 0)) for value in item["values"])
        else:
            total += extract_metric_value(item)
    return total


def extract_metric_value(item):
    if item.get("values"):
        return to_int(item["values"][0].get("value", 0))
    return to_int(item.get("value", 0))


def is_token_configured():
    return bool(ACCESS_TOKEN and not ACCESS_TOKEN.startswith("YOUR_"))


def to_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def safe_rate(numerator, denominator):
    denominator = to_int(denominator)
    if denominator <= 0:
        return 0.0
    return float(numerator) / denominator
