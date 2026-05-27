import os

import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
API_VERSION = os.getenv("INSTAGRAM_API_VERSION", "v19.0")
INSIGHT_METRICS = (
    "reach",
    "shares",
    "profile_activity",
    "follows",
    "impressions",
    "saved",
)


def get_instagram_metrics(media_id):
    """Instagram Graph API에서 주요 성과 지표를 가져온다."""
    if not ACCESS_TOKEN or ACCESS_TOKEN.startswith("YOUR_"):
        print("[Warning] 유효한 인스타그램 ACCESS_TOKEN이 설정되지 않았습니다.")
        return default_metrics()

    return fetch_insights(media_id)


def fetch_comments_count(media_id):
    comments_count, _likes = fetch_media_counts(media_id)
    return comments_count


def fetch_media_counts(media_id):
    media_url = f"https://graph.facebook.com/{API_VERSION}/{media_id}"
    media_params = {
        "fields": "comments_count,like_count",
        "access_token": ACCESS_TOKEN,
    }

    try:
        res = requests.get(media_url, params=media_params, timeout=10)
        res_data = res.json()
        if res.status_code == 200:
            return (
                to_int(res_data.get("comments_count", 0)),
                to_int(res_data.get("like_count", 0)),
            )
        print(f"[Warning] 미디어 기본 정보 조회 실패 ({media_id}): {res_data}")
    except Exception as e:
        print(f"[Warning] 미디어 기본 정보 API 호출 중 예외 ({media_id}): {e}")
    return 0, 0


def fetch_insights(media_id):
    insights_url = f"https://graph.facebook.com/{API_VERSION}/{media_id}/insights"
    insights_params = {
        "metric": ",".join(INSIGHT_METRICS),
        "access_token": ACCESS_TOKEN,
    }

    comments_count, likes = fetch_media_counts(media_id)
    metrics = {
        "impressions": 0,
        "reach": 0,
        "saved": 0,
        "shares": 0,
        "likes": likes,
        "comments_count": comments_count,
        "profile_activity": 0,
        "follows": 0,
    }

    try:
        res = requests.get(insights_url, params=insights_params, timeout=10)
        res_data = res.json()
        if res.status_code == 200 and "data" in res_data:
            for item in res_data["data"]:
                metric_name = item.get("name")
                if metric_name in metrics and item.get("values"):
                    metrics[metric_name] = to_int(item["values"][0].get("value", 0))
        else:
            print(f"[Warning] 미디어 인사이트 조회 실패 ({media_id}): {res_data}")
    except Exception as e:
        print(f"[Warning] 미디어 인사이트 API 호출 중 예외 ({media_id}): {e}")

    reach = metrics["reach"]
    metrics["save_rate"] = safe_rate(metrics["saved"], reach)
    metrics["share_rate"] = safe_rate(metrics["shares"], reach)
    metrics["engagement_rate"] = safe_rate(
        likes + metrics["comments_count"] + metrics["saved"] + metrics["shares"],
        reach,
    )

    return metrics


def default_metrics():
    return {
        "impressions": 0,
        "reach": 0,
        "saved": 0,
        "shares": 0,
        "likes": 0,
        "comments_count": 0,
        "profile_activity": 0,
        "follows": 0,
        "save_rate": 0.0,
        "share_rate": 0.0,
        "engagement_rate": 0.0,
    }


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
