import os

import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
API_VERSION = os.getenv("INSTAGRAM_API_VERSION", "v19.0")


def get_instagram_metrics(media_id):
    """Instagram Graph API에서 조회수, 댓글수, 저장수를 가져온다."""
    if not ACCESS_TOKEN or ACCESS_TOKEN.startswith("YOUR_"):
        print("[Warning] 유효한 인스타그램 ACCESS_TOKEN이 설정되지 않았습니다.")
        return 0, 0, 0

    comments_count = fetch_comments_count(media_id)
    impressions, saved = fetch_insights(media_id)
    return impressions, comments_count, saved


def fetch_comments_count(media_id):
    media_url = f"https://graph.facebook.com/{API_VERSION}/{media_id}"
    media_params = {
        "fields": "comments_count",
        "access_token": ACCESS_TOKEN,
    }

    try:
        res = requests.get(media_url, params=media_params, timeout=10)
        res_data = res.json()
        if res.status_code == 200:
            return res_data.get("comments_count", 0)
        print(f"[Warning] 미디어 기본 정보 조회 실패 ({media_id}): {res_data}")
    except Exception as e:
        print(f"[Warning] 미디어 기본 정보 API 호출 중 예외 ({media_id}): {e}")
    return 0


def fetch_insights(media_id):
    insights_url = f"https://graph.facebook.com/{API_VERSION}/{media_id}/insights"
    insights_params = {
        "metric": "impressions,saved",
        "access_token": ACCESS_TOKEN,
    }

    impressions = 0
    saved = 0
    try:
        res = requests.get(insights_url, params=insights_params, timeout=10)
        res_data = res.json()
        if res.status_code == 200 and "data" in res_data:
            for item in res_data["data"]:
                metric_name = item.get("name")
                metric_value = 0
                if item.get("values"):
                    metric_value = item["values"][0].get("value", 0)

                if metric_name == "impressions":
                    impressions = metric_value
                elif metric_name == "saved":
                    saved = metric_value
        else:
            print(f"[Warning] 미디어 인사이트 조회 실패 ({media_id}): {res_data}")
    except Exception as e:
        print(f"[Warning] 미디어 인사이트 API 호출 중 예외 ({media_id}): {e}")

    return impressions, saved
