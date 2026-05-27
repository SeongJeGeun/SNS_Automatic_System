import json
import os
from collections import defaultdict
from datetime import datetime, timedelta

PERFORMANCE_LOG = os.path.join("shared", "performance_log.json")
OPTIMAL_TIMING_FILE = os.path.join("shared", "optimal_timing.json")
WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def calculate_optimal_timing(
    performance_log_path=PERFORMANCE_LOG,
    output_path=OPTIMAL_TIMING_FILE,
    now=None,
):
    now = now or datetime.now()
    rows = load_json(performance_log_path, default=[])
    matrix = build_weekday_hour_matrix(rows)
    best_posting_times = top_posting_times(matrix, limit=3)
    recommended_next_post_time = next_recommended_time(best_posting_times, now)

    result = {
        "best_posting_times": best_posting_times,
        "recommended_next_post_time": (
            recommended_next_post_time.isoformat(timespec="seconds")
            if recommended_next_post_time
            else None
        ),
    }

    save_json(output_path, result)
    return result


def get_recommended_sleep_seconds(now=None):
    now = now or datetime.now()
    timing = calculate_optimal_timing(now=now)
    next_time = parse_datetime(timing.get("recommended_next_post_time"))
    if not next_time:
        return None
    return max(0, int((next_time - now).total_seconds()))


def build_weekday_hour_matrix(rows):
    buckets = defaultdict(list)
    for row in rows if isinstance(rows, list) else []:
        published_at = parse_published_at(row)
        if not published_at:
            continue
        weekday = WEEKDAYS[published_at.weekday()]
        hour = published_at.hour
        buckets[(weekday, hour)].append(to_float(row.get("save_rate", 0)))

    matrix = {}
    for weekday in WEEKDAYS:
        matrix[weekday] = {}
        for hour in range(24):
            values = buckets.get((weekday, hour), [])
            matrix[weekday][hour] = sum(values) / len(values) if values else 0.0
    return matrix


def top_posting_times(matrix, limit=3):
    candidates = []
    for weekday, hours in matrix.items():
        for hour, avg_save_rate in hours.items():
            if avg_save_rate <= 0:
                continue
            candidates.append({
                "weekday": weekday,
                "hour": int(hour),
                "avg_save_rate": round(float(avg_save_rate), 6),
            })

    candidates.sort(key=lambda item: item["avg_save_rate"], reverse=True)
    return candidates[:limit]


def next_recommended_time(best_posting_times, now):
    if not best_posting_times:
        return None

    candidates = []
    for slot in best_posting_times:
        target_weekday = WEEKDAYS.index(slot["weekday"])
        target_hour = int(slot["hour"])
        days_ahead = (target_weekday - now.weekday()) % 7
        candidate = (now + timedelta(days=days_ahead)).replace(
            hour=target_hour,
            minute=0,
            second=0,
            microsecond=0,
        )
        if candidate <= now:
            candidate += timedelta(days=7)
        candidates.append(candidate)

    return min(candidates)


def parse_published_at(row):
    for key in ("published_at", "날짜", "created_at", "timestamp"):
        value = row.get(key)
        parsed = parse_datetime(value)
        if parsed:
            return parsed
    return None


def parse_datetime(value):
    if not value:
        return None

    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def load_json(path, default=None):
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Warning] JSON 로드 실패 ({path}): {e}")
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def to_float(value):
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    print(json.dumps(calculate_optimal_timing(), ensure_ascii=False, indent=2))
