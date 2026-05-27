import json
import os
from datetime import datetime

from google_sheet_manager import GoogleSheetManager
from instagram_metrics import get_instagram_metrics
from threads_metrics import get_threads_metrics, get_threads_post_ids

PERFORMANCE_LOG = os.path.join("shared", "performance_log.json")
HEADERS = [
    "날짜",
    "post_id",
    "platform",
    "impressions",
    "reach",
    "likes",
    "comments",
    "saved",
    "shares",
    "follows",
    "save_rate",
    "share_rate",
    "engagement_rate",
]


def main():
    print("=" * 60)
    print(" SNS Performance Insights Syncer (Real Data) ")
    print("=" * 60)

    try:
        gsm = GoogleSheetManager()
    except Exception as e:
        print(f"[Warning] 구글 시트 초기화 실패. 로컬 fallback 중심으로 진행합니다: {e}")
        gsm = None

    targets = collect_targets(gsm)
    if not targets:
        print("[Warning] 동기화할 Instagram/Threads post_id를 찾지 못했습니다.")
        return

    rows = []
    for target in targets:
        platform = target["platform"]
        post_id = target["post_id"]
        print(f"\n-> {platform} 최신 지표 수집 중: {post_id}")

        if platform == "instagram":
            row = build_instagram_row(post_id)
        elif platform == "threads":
            row = build_threads_row(post_id)
        else:
            print(f"   [Warning] 지원하지 않는 platform 값이라 건너뜁니다: {platform}")
            continue

        rows.append(row)
        print(
            "   수집 완료 -> impressions: {impressions}, reach: {reach}, "
            "comments: {comments}, engagement_rate: {engagement_rate:.4f}".format(**row)
        )

    if not rows:
        print("[Warning] 기록할 성과 데이터가 없습니다.")
        return

    # 구글 시트 기록 (실패해도 계속 진행)
    try:
        append_rows_to_sheet(gsm, rows)
        print(f"\n✅ 구글 시트에 {len(rows)}개 성과 row 기록 완료.")
    except Exception as e:
        print(f"\n[Warning] 구글 시트 기록 실패: {e}")

    # 항상 로컬 fallback에도 저장 (upsert)
    append_rows_to_fallback(rows)
    print(f"✅ 로컬 fallback 저장 완료 (upsert): {PERFORMANCE_LOG}")

    apply_performance_to_strategy()


def collect_targets(gsm):
    targets = []
    seen = set()

    if gsm and gsm.sheet:
        try:
            for record in gsm.sheet.get_all_records():
                for target in targets_from_sheet_record(record):
                    add_target(targets, seen, target["platform"], target["post_id"])
        except Exception as e:
            print(f"[Warning] 구글 시트 기존 기록 조회 실패: {e}")

    for platform, post_id in targets_from_local_reports():
        add_target(targets, seen, platform, post_id)

    if not any(target["platform"] == "threads" for target in targets):
        for post_id in get_threads_post_ids(limit=10):
            add_target(targets, seen, "threads", post_id)

    return targets


def targets_from_sheet_record(record):
    targets = []
    platform = normalize_platform(record.get("platform") or record.get("플랫폼"))
    post_id = (
        record.get("post_id")
        or record.get("미디어ID")
        or record.get("media_id")
        or record.get("MediaID")
    )

    if post_id:
        targets.append({
            "platform": platform or infer_platform(str(post_id)),
            "post_id": str(post_id),
        })

    instagram_id = record.get("instagram_post_id") or record.get("instagram_media_id")
    if instagram_id:
        targets.append({"platform": "instagram", "post_id": str(instagram_id)})

    threads_id = record.get("threads_post_id")
    if threads_id:
        targets.append({"platform": "threads", "post_id": str(threads_id)})

    return targets


def targets_from_local_reports():
    reports = [
        ("instagram", os.path.join("agent_runs", "instagram_last_upload_report.json"), "published_id"),
        ("threads", os.path.join("agent_runs", "threads_last_upload_report.json"), "post_id"),
    ]

    targets = []
    for platform, path, key in reports:
        data = load_json(path)
        post_id = data.get(key)
        if post_id:
            targets.append((platform, str(post_id)))
    return targets


def add_target(targets, seen, platform, post_id):
    platform = normalize_platform(platform)
    post_id = str(post_id).strip()
    if not platform or not post_id:
        return

    key = (platform, post_id)
    if key in seen:
        return

    seen.add(key)
    targets.append({"platform": platform, "post_id": post_id})


def build_instagram_row(post_id):
    metrics = get_instagram_metrics(post_id)
    return {
        "날짜": now_string(),
        "post_id": str(post_id),
        "platform": "instagram",
        "impressions": to_int(metrics.get("impressions", 0)),
        "reach": to_int(metrics.get("reach", 0)),
        "likes": to_int(metrics.get("likes", 0)),
        "comments": to_int(metrics.get("comments_count", 0)),
        "saved": to_int(metrics.get("saved", 0)),
        "shares": to_int(metrics.get("shares", 0)),
        "follows": to_int(metrics.get("follows", 0)),
        "save_rate": to_float(metrics.get("save_rate", 0.0)),
        "share_rate": to_float(metrics.get("share_rate", 0.0)),
        "engagement_rate": to_float(metrics.get("engagement_rate", 0.0)),
    }


def build_threads_row(post_id):
    metrics = get_threads_metrics(post_id)
    views = to_int(metrics.get("views", 0))
    likes = to_int(metrics.get("likes", 0))
    replies = to_int(metrics.get("replies", 0))
    reposts = to_int(metrics.get("reposts", 0))
    quotes = to_int(metrics.get("quotes", 0))
    shares = reposts + quotes

    return {
        "날짜": now_string(),
        "post_id": str(post_id),
        "platform": "threads",
        "impressions": views,
        "reach": views,
        "likes": likes,
        "comments": replies,
        "saved": 0,
        "shares": shares,
        "follows": 0,
        "save_rate": 0.0,
        "share_rate": safe_rate(shares, views),
        "engagement_rate": safe_rate(
            likes + replies + reposts + quotes,
            views,
        ),
    }


def append_rows_to_sheet(gsm, rows):
    if not gsm or not gsm.sheet:
        raise RuntimeError("구글 시트 연결이 없습니다.")

    ensure_headers(gsm.sheet)
    for row in rows:
        gsm.sheet.append_row([row[header] for header in HEADERS])


def append_rows_to_fallback(rows):
    """post_id 기준 upsert: 이미 있으면 덮어쓰고, 없으면 append."""
    os.makedirs(os.path.dirname(PERFORMANCE_LOG), exist_ok=True)
    existing = load_json(PERFORMANCE_LOG, default=[])
    if not isinstance(existing, list):
        existing = []

    # post_id → index 매핑 (마지막 항목 기준)
    index_map = {str(entry.get("post_id", "")): i for i, entry in enumerate(existing)}

    for row in rows:
        pid = str(row.get("post_id", ""))
        if pid and pid in index_map:
            existing[index_map[pid]] = row  # 덮어쓰기
        else:
            existing.append(row)            # 신규 추가
            if pid:
                index_map[pid] = len(existing) - 1

    with open(PERFORMANCE_LOG, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def ensure_headers(sheet):
    values = sheet.get_all_values()
    if values and values[0][:len(HEADERS)] == HEADERS:
        return

    if not values:
        sheet.append_row(HEADERS)
        return

    sheet.insert_row(HEADERS, 1)


def load_json(path, default=None):
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Warning] JSON 파일 로드 실패 ({path}): {e}")
        return default


def normalize_platform(value):
    normalized = str(value or "").strip().lower()
    if normalized in {"instagram", "ig", "인스타그램", "인스타"}:
        return "instagram"
    if normalized in {"threads", "thread", "쓰레드", "스레드"}:
        return "threads"
    return ""


def infer_platform(post_id):
    if "_" in post_id:
        return "instagram"
    return "instagram"


def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def to_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def to_float(value):
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def safe_rate(numerator, denominator):
    denominator = to_int(denominator)
    if denominator <= 0:
        return 0.0
    return float(numerator) / denominator


def apply_performance_to_strategy():
    try:
        from performance_to_strategy import update_strategy_from_performance
        result = update_strategy_from_performance()
        if result.get("updated"):
            print("[Strategy Sync] 성과 패턴을 content_strategy.json에 반영했습니다.")
        else:
            print(f"[Strategy Sync] 성과 패턴 반영 생략: {result.get('reason')}")
    except Exception as e:
        print(f"[Warning] 성과 기반 전략 반영 실패: {e}")


if __name__ == "__main__":
    main()
