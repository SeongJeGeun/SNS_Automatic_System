import hashlib
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from constants import OBSIDIAN_VAULT_PATH


SYNC_FOLDER = os.path.join(OBSIDIAN_VAULT_PATH, "SNS_Automatic", "publish_logs")
SYNC_INDEX_FILE = os.path.join(SYNC_FOLDER, "publish_sync_index.json")
SYNC_SCHEMA_VERSION = "2026-05-28.2"

BRAIN_HUBS = {
    "SNS_발행_로그": """# SNS 발행 로그

Threads와 Instagram 발행 결과가 자동으로 모이는 운영 기억 허브입니다.

## 연결

[[MindFactory_Core]]
[[성과_분석]]
[[다음_실험]]
[[Threads_성과]]
[[Instagram_성과]]
[[발행_자가발전_루프]]
[[API_제한_오류]]

## 최근 동기화 노트

#SNS발행 #운영기억 #자동동기화
""",
    "Threads_성과": """# Threads 성과

Threads의 훅, 댓글 반응, 리포스트, 대화성 데이터를 모아 Instagram 카드뉴스 후보로 확장하기 위한 허브입니다.

[[SNS_발행_로그]]
[[성과_분석]]
[[콘텐츠_전략]]
[[다음_실험]]

#Threads #성과분석 #대화형훅
""",
    "Instagram_성과": """# Instagram 성과

Instagram 카드뉴스의 저장, 공유, 도달, 발행 실패 데이터를 모아 다음 콘텐츠 구조를 개선하기 위한 허브입니다.

[[SNS_발행_로그]]
[[성과_분석]]
[[저장률_높은_문장]]
[[첫_장_후킹]]
[[다음_실험]]

#Instagram #저장률 #카드뉴스
""",
    "발행_자가발전_루프": """# 발행 자가발전 루프

발행 결과가 다음 주제, 훅, 이미지, 업로드 간격에 되먹임되는 구조를 관리하는 허브입니다.

[[SNS_발행_로그]]
[[성과_분석]]
[[다음_실험]]
[[실패_원인]]
[[콘텐츠_전략]]

#자가발전 #피드백루프 #콘텐츠개선
""",
    "API_제한_오류": """# API 제한 오류

Instagram/Threads API 제한, 토큰 문제, 발행 차단, 재시도 정책을 모으는 장애 지식 허브입니다.

[[SNS_발행_로그]]
[[실패_원인]]
[[다음_실험]]

#API오류 #발행제한 #쿨다운
""",
}

REPORT_SOURCES = [
    ("threads", os.path.join("agent_runs", "threads_last_upload_report.json")),
    ("instagram", os.path.join("agent_runs", "instagram_last_upload_report.json")),
    ("instagram", os.path.join("agent_runs", "instagram_upload_check_report.json")),
]


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _ensure_brain_hubs() -> None:
    os.makedirs(OBSIDIAN_VAULT_PATH, exist_ok=True)
    for name, content in BRAIN_HUBS.items():
        path = os.path.join(OBSIDIAN_VAULT_PATH, f"{name}.md")
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

    core_path = os.path.join(OBSIDIAN_VAULT_PATH, "MindFactory_Core.md")
    if os.path.exists(core_path):
        with open(core_path, "r", encoding="utf-8") as f:
            core = f.read()
    else:
        core = "# MindFactory Core\n\n"

    additions = ["[[SNS_발행_로그]]", "[[발행_자가발전_루프]]", "[[Threads_성과]]", "[[Instagram_성과]]"]
    missing = [link for link in additions if link not in core]
    if missing:
        block = "\n\n## SNS 발행 두뇌 연결\n\n" + "\n".join(missing) + "\n"
        with open(core_path, "w", encoding="utf-8") as f:
            f.write(core.rstrip() + block)


def _slug(value: str, fallback: str = "publish") -> str:
    cleaned = re.sub(r"[^0-9A-Za-z가-힣_-]+", "_", value).strip("_")
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned[:80] or fallback


def _fingerprint(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_index() -> Dict[str, Any]:
    index = _load_json(SYNC_INDEX_FILE)
    if not index:
        return {"items": {}}
    index.setdefault("items", {})
    return index


def _source_key(platform: str, source_path: str, report: Dict[str, Any]) -> str:
    if platform == "threads":
        identity = report.get("post_id") or report.get("permalink") or "latest"
    else:
        identity = (
            report.get("published_id")
            or report.get("parent_container_id")
            or report.get("failed_step")
            or report.get("error_stage")
            or "latest"
        )
    return f"{platform}:{source_path}:{identity}"


def _status_text(report: Dict[str, Any]) -> str:
    if report.get("ok") is True:
        return "published"
    if report.get("ok") is False:
        return "failed"
    return "recorded"


def _report_time(report: Dict[str, Any]) -> str:
    return (
        report.get("finished_at")
        or report.get("checked_at")
        or report.get("started_at")
        or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


def _format_error(report: Dict[str, Any]) -> List[str]:
    error = report.get("error") or report.get("first_publish_error") or report.get("subsequent_publish_error")
    if not isinstance(error, dict):
        return []

    lines = ["## 오류 / 제한 정보", ""]
    for key in ["message", "type", "code", "subcode", "user_title", "user_message", "fbtrace_id"]:
        if error.get(key) not in (None, ""):
            lines.append(f"- **{key}**: {error.get(key)}")
    lines.append("")
    return lines


def _brain_links(platform: str, report: Dict[str, Any]) -> List[str]:
    status = _status_text(report)
    links = ["MindFactory_Core", "SNS_발행_로그", "성과_분석", "발행_자가발전_루프"]

    if platform == "threads":
        links.extend(["Threads_성과", "콘텐츠_전략", "다음_실험"])
    else:
        links.extend(["Instagram_성과", "저장률_높은_문장", "첫_장_후킹"])

    if status == "failed":
        links.extend(["실패_원인", "API_제한_오류", "다음_실험"])
    else:
        links.append("다음_실험")

    return list(dict.fromkeys(links))


def _build_markdown(platform: str, source_path: str, report: Dict[str, Any]) -> str:
    status = _status_text(report)
    synced_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_time = _report_time(report)
    title_id = report.get("post_id") or report.get("published_id") or report.get("parent_container_id") or report.get("failed_step") or "latest"
    title = f"{platform.capitalize()} Publish Log - {title_id}"

    lines = [
        "---",
        f"platform: {platform}",
        f"status: {status}",
        f"source_file: {source_path}",
        f"synced_at: {synced_at}",
        f"reported_at: {report_time}",
        "tags:",
        "  - sns/publish",
        f"  - sns/{platform}",
        f"  - sns/status/{status}",
        "---",
        "",
        f"# {title}",
        "",
        "## 발행 요약",
        "",
        f"- **플랫폼**: {platform}",
        f"- **상태**: {status}",
        f"- **보고 시각**: {report_time}",
        f"- **원본 파일**: `{source_path}`",
    ]

    if platform == "threads":
        lines.extend([
            f"- **Threads Post ID**: {report.get('post_id', '미기록')}",
            f"- **Permalink**: {report.get('permalink', '미기록')}",
            f"- **Detail**: {report.get('detail', '미기록')}",
        ])
    else:
        lines.extend([
            f"- **Instagram Published ID**: {report.get('published_id') or '미발행'}",
            f"- **Parent Container ID**: {report.get('parent_container_id', '미기록')}",
            f"- **Image Count**: {report.get('image_count', '미기록')}",
            f"- **Error Stage**: {report.get('error_stage') or report.get('failed_step') or '없음'}",
        ])
        child_ids = report.get("child_container_ids")
        if isinstance(child_ids, list) and child_ids:
            lines.append(f"- **Child Containers**: {', '.join(str(v) for v in child_ids)}")

    lines.extend(["", "## 자가발전 메모", ""])
    if status == "published":
        lines.extend([
            "- 발행 성공 데이터입니다. 24시간/72시간 성과 수집 시 이 노트에 후속 지표를 연결하세요.",
            "- 성과가 기준치를 넘으면 `recycle_candidate` 후보로 검토합니다.",
        ])
    else:
        lines.extend([
            "- 발행 실패 또는 제한 데이터입니다. 다음 실행 전 원인과 대기 시간을 확인해야 합니다.",
            "- 동일 오류가 반복되면 업로드 간격과 프롬프트/이미지 생성 단계를 보수적으로 조정합니다.",
        ])

    lines.extend(["", "## 두뇌 연결", ""])
    for link in _brain_links(platform, report):
        lines.append(f"[[{link}]]")

    lines.extend(["", *(_format_error(report))])
    lines.extend([
        "## 원본 JSON",
        "",
        "```json",
        json.dumps(report, ensure_ascii=False, indent=2),
        "```",
        "",
    ])
    return "\n".join(lines)


def _append_publish_index(note_filename: str, platform: str, report: Dict[str, Any]) -> None:
    path = os.path.join(OBSIDIAN_VAULT_PATH, "SNS_발행_로그.md")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    note_name = os.path.splitext(note_filename)[0]
    status = _status_text(report)
    report_time = _report_time(report)
    entry = f"- {report_time} · {platform} · {status} · [[{note_name}]]"
    if entry in content:
        return

    marker = "## 최근 동기화 노트"
    if marker in content:
        content = content.replace(marker, f"{marker}\n\n{entry}", 1)
    else:
        content = content.rstrip() + f"\n\n{marker}\n\n{entry}\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def sync_publish_report(platform: str, source_path: str) -> Optional[Dict[str, Any]]:
    report = _load_json(source_path)
    if not report:
        return None

    _ensure_brain_hubs()
    os.makedirs(SYNC_FOLDER, exist_ok=True)
    index = _load_index()
    key = _source_key(platform, source_path, report)
    fp = _fingerprint(report)
    existing = index["items"].get(key, {})

    filename_seed = key.split(":", 2)[-1]
    filename = existing.get("file") or f"{datetime.now().strftime('%Y%m%d')}_{platform}_{_slug(str(filename_seed))}.md"
    note_path = os.path.join(SYNC_FOLDER, filename)

    if (
        existing.get("fingerprint") == fp
        and existing.get("schema_version") == SYNC_SCHEMA_VERSION
        and os.path.exists(note_path)
    ):
        return {
            "platform": platform,
            "source_file": source_path,
            "note_path": note_path,
            "status": "unchanged",
        }

    with open(note_path, "w", encoding="utf-8") as f:
        f.write(_build_markdown(platform, source_path, report))
    _append_publish_index(filename, platform, report)

    index["items"][key] = {
        "platform": platform,
        "source_file": source_path,
        "file": filename,
        "fingerprint": fp,
        "schema_version": SYNC_SCHEMA_VERSION,
        "last_synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "publish_status": _status_text(report),
    }
    _write_json(SYNC_INDEX_FILE, index)

    return {
        "platform": platform,
        "source_file": source_path,
        "note_path": note_path,
        "status": "synced",
    }


def sync_all_publish_reports() -> List[Dict[str, Any]]:
    results = []
    for platform, source_path in REPORT_SOURCES:
        result = sync_publish_report(platform, source_path)
        if result:
            results.append(result)
    return results


if __name__ == "__main__":
    for item in sync_all_publish_reports():
        print(f"{item['status']}: {item['platform']} -> {item['note_path']}")
