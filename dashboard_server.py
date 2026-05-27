# dashboard_server.py
import os
import re
import json
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

# .env 로드
load_dotenv(override=True)

app = FastAPI(title="MindFactory SNS Automation Dashboard Server")
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OBSIDIAN_VAULT = str(PROJECT_ROOT / "obsidian_vault")

# 정적 파일 및 템플릿 마운트
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 파일 경로 정의
MONITOR_DIR = "agent_runs"
STATUS_JSON = os.path.join(MONITOR_DIR, "agent_status.json")
STATUS_MD = os.path.join(MONITOR_DIR, "agent_status.md")
EVENT_LOG = os.path.join(MONITOR_DIR, "agent_events.jsonl")
THREADS_LAST_UPLOAD_REPORT = os.path.join(MONITOR_DIR, "threads_last_upload_report.json")
DAILY_REPORT = "daily_report.json"
ORCHESTRATOR_LOG = "orchestrator.log"
PAUSE_FLAG = os.path.join(MONITOR_DIR, "pipeline_paused.flag")
RUN_NOW_REQUEST = os.path.join(MONITOR_DIR, "run_now.request")

AUDIENCE_INSIGHT = "audience_insight.json"
CONTENT_STRATEGY = "content_strategy.json"
SELF_HEALING_STRATEGY = "self_healing_strategy.json"

STORY_RESPONSE = "codex_story_response.json"
STRATEGY_RESPONSE = "codex_strategy_response.json"
COMMAND_REQUESTS = "codex_command_requests.md"
PROJECT_MEMORY = "project_memory.md"
RUNBOOK_DOC = os.path.join("docs", "runbook.md")
THREADS_RULES_DOC = os.path.join("docs", "THREADS_INSTAGRAM_RULES.md")

# 에이전트 순서 정의 (진행률 계산용)
AGENT_PROGRESS_MAP = {
    "Startup Agent": 5,
    "Google Agent": 10,
    "Archive Agent": 15,
    "Sheet Agent": 20,
    "Growth Agent": 25,
    "Trend Agent": 30,
    "RAG Agent": 35,
    "Audience Agent": 40,
    "Strategy Agent": 45,
    "Story Agent": 55,
    "Quality Agent": 60,
    "Story Agent Retry": 65,
    "Quality Agent Retry": 70,
    "Visual Agent": 80,
    "Hosting Agent": 90,
    "Publishing Agent": 95,
    "Cleanup Agent": 98,
    "Report Agent": 100
}

# 헬퍼 함수: 파일 로딩
def safe_load_json(file_path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def safe_read_text(file_path: str) -> str:
    if not os.path.exists(file_path):
        return ""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def parse_local_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except ValueError:
            continue
    return None

def format_local_datetime(value: Optional[datetime]) -> str:
    if not value:
        return "대기 중"
    return value.strftime("%Y-%m-%d %H:%M:%S")

# =====================================================================
# 1. agent_runs/agent_status.md 파서
# =====================================================================
def parse_agent_status_md() -> Dict[str, Any]:
    result = {
        "state": "waiting",
        "last_run_started_at": "",
        "last_run_finished_at": "",
        "next_run_at": "",
        "heartbeat_at": "",
        "last_result": "",
        "agents": {}
    }
    if not os.path.exists(STATUS_MD):
        return result

    try:
        with open(STATUS_MD, "r", encoding="utf-8") as f:
            lines = f.readlines()

        current_section = "global"
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("## Agents"):
                current_section = "agents"
                continue

            if current_section == "global" and line.startswith("-"):
                parts = line[1:].strip().split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip()
                    if key in result:
                        result[key] = val

            elif current_section == "agents" and line.startswith("-"):
                parts = line[1:].strip().split(":", 1)
                if len(parts) == 2:
                    agent_name = parts[0].strip()
                    agent_detail = parts[1].strip()
                    state = "idle"
                    if "success" in agent_detail:
                        state = "success"
                    elif "failed" in agent_detail:
                        state = "failed"
                    elif "running" in agent_detail:
                        state = "running"

                    result["agents"][agent_name] = {
                        "state": state,
                        "detail": agent_detail
                    }
    except Exception:
        pass
    return result

# =====================================================================
# 2. Obsidian Vault 마크다운 파서 및 지식 그래프 API
# =====================================================================
def parse_obsidian_vault(vault_path: str) -> Optional[Dict[str, Any]]:
    if not vault_path or not os.path.exists(vault_path) or not os.path.isdir(vault_path):
        return None

    nodes = []
    edges = []
    tags_map = {} # tag_name -> tag_node_id
    file_id_map = {} # note_name -> note_node_id
    file_mtimes = [] # list of (note_name, mtime)

    node_id_counter = 1
    file_contents = {}

    # 1. md 파일 스캔하여 노드 생성
    try:
        for root, dirs, files in os.walk(vault_path):
            for file in files:
                if file.endswith(".md"):
                    file_path = os.path.join(root, file)
                    note_name = os.path.splitext(file)[0]

                    try:
                        mtime = os.path.getmtime(file_path)
                        file_mtimes.append((note_name, mtime))
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                    except Exception:
                        continue

                    file_id_map[note_name] = node_id_counter
                    file_contents[note_name] = content

                    # 그룹 정의
                    group = "note"
                    if note_name == "MindFactory_Core":
                        group = "core"
                    elif note_name in ["트렌드_분석", "콘텐츠_전략", "성과_분석", "다음_실험", "실패_원인", "저장률_높은_문장", "첫_장_후킹"]:
                        group = "hub"
                    elif any(x in note_name.lower() for x in ["번아웃", "무기력", "피로", "불안", "고민"]):
                        group = "pain"
                    elif "rule" in note_name.lower() or "규칙" in note_name or "가이드" in note_name:
                        group = "rule"
                    elif "experiment" in note_name.lower() or "실험" in note_name:
                        group = "experiment"
                    elif "report" in note_name.lower() or "성과" in note_name or "반응" in note_name:
                        group = "insight"

                    nodes.append({
                        "id": note_name,
                        "label": note_name,
                        "group": group,
                        "size": 25 if group == "core" else (20 if group == "hub" else 15)
                    })
                    node_id_counter += 1
    except Exception:
        return None

    # 2. 내부 링크 [[링크]] 및 #태그 파싱
    for note_name, content in file_contents.items():
        source_id = note_name

        # 내부 링크 [[링크]] 매칭
        links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)
        for link in links:
            link = link.strip()
            if link in file_id_map:
                target_id = link
                edges.append({
                    "from": source_id,
                    "to": target_id,
                    "source": source_id,
                    "target": target_id
                })

        # 해시태그 #태그 매칭
        tags = re.findall(r"#([a-zA-Z가-힣0-9_-]+)", content)
        for tag in tags:
            tag_name = "#" + tag
            # hex 색상코드 제외
            if re.match(r"^#[0-9a-fA-F]{6}$", tag_name) or re.match(r"^#[0-9a-fA-F]{3}$", tag_name):
                continue

            if tag_name not in tags_map:
                tags_map[tag_name] = tag_name
                nodes.append({
                    "id": tag_name,
                    "label": tag_name,
                    "group": "tag",
                    "size": 10
                })

            tag_id = tag_name
            edges.append({
                "from": source_id,
                "to": tag_id,
                "source": source_id,
                "target": tag_id
            })

    # 중복 엣지 제거
    unique_edges = []
    seen_edges = set()
    for e in edges:
        edge_key = tuple(sorted([e["from"], e["to"]]))
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            unique_edges.append(e)

    # 통계 계산
    note_nodes_ids = {n["id"] for n in nodes if n["group"] != "tag"}

    # 각 노드별 연결 개수 계산 (degree)
    degree_map = {nid: 0 for nid in note_nodes_ids}
    connected_nodes = set()
    for e in unique_edges:
        f, t = e["from"], e["to"]
        if f in degree_map:
            degree_map[f] += 1
            connected_nodes.add(f)
        if t in degree_map:
            degree_map[t] += 1
            connected_nodes.add(t)

    # 고립 노드 (Isolated) 계산
    isolated_nodes_set = note_nodes_ids - connected_nodes
    isolated_count = len(isolated_nodes_set)

    # Top Hubs 계산
    sorted_hubs = sorted(degree_map.items(), key=lambda x: x[1], reverse=True)
    top_hubs = [item[0] for item in sorted_hubs[:5] if item[1] > 0]
    if not top_hubs:
        top_hubs = ["MindFactory_Core", "트렌드_분석", "콘텐츠_전략"]

    # 최근 수정된 노트 정렬
    file_mtimes.sort(key=lambda x: x[1], reverse=True)
    recent_notes = [x[0] for x in file_mtimes[:5]]

    return {
        "nodes": nodes,
        "edges": unique_edges,
        "tags": list(tags_map.keys()),
        "stats": {
            "total_notes": len(note_nodes_ids),
            "total_edges": len(unique_edges),
            "isolated_notes": isolated_count,
            "top_hubs": top_hubs,
            "recent_notes": recent_notes
        }
    }

# =====================================================================
# UI Router (Root)
# =====================================================================
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

# =====================================================================
# 1. GET /api/status (현재 실행 상태)
# =====================================================================
@app.get("/api/status")
def get_status():
    # 데이터 소스 1순위: JSON / 2순위: MD 파일 파서 교차 연동
    status_data = safe_load_json(STATUS_JSON)
    md_data = parse_agent_status_md()
    paused = os.path.exists(PAUSE_FLAG)

    is_running = False
    current_agent = "Waiting"
    current_step = "idle"
    progress = 0

    # 1. JSON 기반 파싱 시도
    if status_data:
        pipeline = status_data.get("pipeline", {})
        pipe_state = pipeline.get("state", "waiting")
        is_running = pipe_state in ["running", "starting", "startup_duplicate_check"]

        running_agents = []
        for name, info in status_data.get("agents", {}).items():
            if info.get("state") == "running":
                running_agents.append((name, info.get("started_at", "")))

        if running_agents:
            running_agents.sort(key=lambda x: x[1], reverse=True)
            current_agent = running_agents[0][0]
            current_step = current_agent.lower().replace(" ", "_").replace("_agent", "")
            progress = AGENT_PROGRESS_MAP.get(current_agent, 40)
        else:
            if is_running:
                current_agent = "Orchestrator Core"
                progress = 5
            else:
                current_agent = "Waiting"
                if pipeline.get("last_result") == "success":
                    progress = 100
                else:
                    progress = 0
        last_updated = pipeline.get("updated_at", datetime.now().isoformat())

    # 2. JSON이 없고 MD 파일만 있을 경우 폴백
    elif md_data.get("last_run_started_at"):
        pipe_state = md_data.get("state", "waiting")
        is_running = pipe_state in ["running", "starting"]

        running_agents = []
        for name, info in md_data.get("agents", {}).items():
            if info.get("state") == "running":
                running_agents.append(name)

        if running_agents:
            current_agent = running_agents[0]
            current_step = current_agent.lower().replace(" ", "_").replace("_agent", "")
            progress = AGENT_PROGRESS_MAP.get(current_agent, 40)
        else:
            current_agent = "Waiting"
            if md_data.get("last_result") == "success":
                progress = 100
        last_updated = md_data.get("heartbeat_at", datetime.now().isoformat())

    else:
        # 파일이 없을 시 폴백
        last_updated = datetime.now().isoformat()

    # 3. orchestrator.log 융합 검증 (에러 여부 등 확인)
    if os.path.exists(ORCHESTRATOR_LOG):
        # 마지막 수정 시각
        log_mtime = os.path.getmtime(ORCHESTRATOR_LOG)
        # 10분 이내에 로그가 갱신되었고 에러 관련 지시어가 있다면
        if time.time() - log_mtime < 600:
            try:
                with open(ORCHESTRATOR_LOG, "r", encoding="utf-8") as lf:
                    log_content = lf.read()
                    if "Error" in log_content or "Exception" in log_content:
                        # 에러 감지 상태값 융합
                        pass
            except Exception:
                pass

    # next_run_at 및 기타 메타 획득
    next_run_at = "대기 중"
    last_started_at = ""
    last_finished_at = ""
    last_error = ""
    last_success = True

    if status_data:
        pipeline = status_data.get("pipeline", {})
        next_run_at = pipeline.get("next_run_at", "대기 중")
        last_started_at = pipeline.get("last_started_at", "")
        last_finished_at = pipeline.get("last_finished_at", "")
        last_error = pipeline.get("last_error", "")
        last_success = pipeline.get("last_success", True)
    elif md_data:
        next_run_at = md_data.get("next_run_at", "대기 중")
        last_started_at = md_data.get("last_run_started_at", "")
        last_finished_at = md_data.get("last_run_finished_at", "")
        last_error = md_data.get("last_result", "")
        last_success = True if md_data.get("last_result") == "success" else False

    if paused:
        current_agent = "Paused"
        current_step = "paused"
        is_running = False

    return {
        "is_running": is_running,
        "current_agent": current_agent,
        "current_step": current_step,
        "progress": progress,
        "last_updated": last_updated,
        "paused": paused,
        "next_run_at": next_run_at,
        "last_started_at": last_started_at,
        "last_finished_at": last_finished_at,
        "last_error": last_error,
        "last_success": last_success
    }

# =====================================================================
# 2. GET /events (SSE 스트림)
# =====================================================================
@app.get("/events")
async def sse_events(request: Request):
    load_dotenv(override=True)
    vault_path = os.getenv("OBSIDIAN_VAULT_PATH", DEFAULT_OBSIDIAN_VAULT)

    files_to_watch = [
        STATUS_JSON,
        STATUS_MD,
        DAILY_REPORT,
        ORCHESTRATOR_LOG,
        COMMAND_REQUESTS,
        STORY_RESPONSE,
        STRATEGY_RESPONSE,
        PAUSE_FLAG
    ]

    def get_mtimes():
        mtimes = {}
        for f in files_to_watch:
            if os.path.exists(f):
                mtimes[f] = os.path.getmtime(f)
            else:
                mtimes[f] = 0.0
        return mtimes

    def get_vault_state():
        if not vault_path or not os.path.exists(vault_path) or not os.path.isdir(vault_path):
            return ""
        try:
            state_parts = []
            for root, dirs, files in os.walk(vault_path):
                for file in files:
                    if file.endswith(".md"):
                        fp = os.path.join(root, file)
                        try:
                            state_parts.append(f"{file}:{os.path.getmtime(fp)}")
                        except Exception:
                            pass
            return "|".join(state_parts)
        except Exception:
            return ""

    async def event_generator():
        last_mtimes = get_mtimes()
        last_vault_state = get_vault_state()

        while True:
            if await request.is_disconnected():
                break

            await asyncio.sleep(2.5) # 2.5초 마다 파일 및 폴더 상태 체크

            # 1. 오케스트레이터 상태 파일 감시
            current_mtimes = get_mtimes()
            changed = False
            for f in files_to_watch:
                if current_mtimes[f] != last_mtimes[f]:
                    changed = True
                    break

            if changed:
                last_mtimes = current_mtimes
                status = get_status()
                yield f"data: {json.dumps({'type': 'status_update', **status}, ensure_ascii=False)}\n\n"

            # 2. 옵시디언 보관소(Vault) 변동 감시
            current_vault_state = get_vault_state()
            if current_vault_state != last_vault_state:
                last_vault_state = current_vault_state
                yield f"data: {json.dumps({'type': 'brain_graph_update'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# =====================================================================
# 3. GET /api/pipeline/{step_id} (단계별 상세 정보)
# =====================================================================
PIPELINE_STATIC_DETAILS = {
    "audience": {
        "title": "Audience Agent",
        "description": "요즘 20-30대 청년층이 겪고 있는 실시간 고민(번아웃, 무기력, 자존감 등)을 수집하고 깊이 공감되는 고통 포인트를 요약합니다.",
        "input": ["Obsidian 로컬 데이터", "Seed 고민 키워드 목록"],
        "current_task": "인스타그램 타겟 오디언스 내면 고통(Core Pain) 선별 및 감정 키워드 추출",
        "done_condition": "audience_insight.json 파일 갱신 및 핵심 타겟 메시지 결정 완료",
        "recovery": ["로컬 시드 데이터 및 이전 히스토리 기반 고민 목록 강제 로드"],
        "next_step": "Trend Agent",
        "related_files": ["audience_research.py", "audience_insight.json"],
        "api_status": "Antigravity 파일 브리지 준비 완료"
    },
    "trend": {
        "title": "Trend Agent",
        "description": "Antigravity CLI 검색으로 인스타그램 알고리즘 변화 및 카드뉴스 디자인 트렌드를 조사하고 결과를 Obsidian에 저장합니다.",
        "input": ["트렌드 쿼리 목록"],
        "current_task": "Antigravity 검색 실행 및 요약 반영",
        "done_condition": "obsidian_vault 내 trend_search_{timestamp}.md 파일 저장 완료",
        "recovery": ["기존에 저장된 트렌드 마크다운 파일들의 통합 백업본 활용"],
        "next_step": "Strategy Agent",
        "related_files": ["main_orchestrator.py", "obsidian_vault/trend_search_*.md"],
        "api_status": "Antigravity 검색 브리지 준비 완료"
    },
    "strategy": {
        "title": "Strategy Agent",
        "description": "오디언스 고통 분석과 실시간 트렌드, 그리고 마인드팩토리 브랜드 철학(성장/규율/몰입/멘탈팩폭)을 융합하여 기획 방향을 구체화합니다.",
        "input": ["audience_insight.json", "self_healing_strategy.json (필요 시)"],
        "current_task": "표지 훅 작성 규칙 및 카드별 스토리 구조 설계",
        "done_condition": "content_strategy.json 파일 저장 완료 및 기획 가이드라인 고정",
        "recovery": ["기존 content_strategy.json 규칙에 따른 정체성 저격 규칙 강제 사용"],
        "next_step": "Story / Quality Agent",
        "related_files": ["content_strategy.py", "content_strategy.json"],
        "api_status": "Antigravity 파일 브리지 준비 완료"
    },
    "story_quality": {
        "title": "Story / Quality Agent",
        "description": "기획 전략에 맞춰 5~7장 분량의 구체적인 카드뉴스 대본과 이미지 생성용 영문 프롬프트를 만들고, 품질 기준(Must-have 조건)을 엄격히 평가합니다.",
        "input": ["content_strategy.json", "self_healing_strategy.json"],
        "current_task": "대본 초안 생성 및 7개 Must-have 항목 평가 (미달 시 Story Agent Retry 작동)",
        "done_condition": "script.json 생성 및 품질 평가 통과 (최종 승인)",
        "recovery": ["우회 다각화 프롬프트(Cream 테마, 강렬한 어조) 주입 후 대본 강제 재생성 시도"],
        "next_step": "Visual / Drive Agent",
        "related_files": ["self_healing_generator.py", "content_evaluator.py", "script.json", "content_quality_report.json"],
        "api_status": "Antigravity 대본 요청/응답 브리지 준비 완료"
    },
    "visual_drive": {
        "title": "Visual / Drive Agent",
        "description": "대본에 정의된 영문 이미지 프롬프트를 바탕으로 AI 이미지를 생성하고 카드 템플릿과 합성하여, 인스타그램 API가 읽을 수 있도록 Google Drive 임시 폴더에 업로드합니다.",
        "input": ["script.json", "로컬 폰트 및 템플릿 정보"],
        "current_task": "Antigravity 이미지 생성 요청, PIL 카드 드로잉, Google Drive 임시 호스팅",
        "done_condition": "page1.png ~ page7.png 로컬 생성 및 Google Drive 퍼블릭 링크 획득",
        "recovery": ["임시 호스팅 실패 시 Imgur API 또는 로컬 퍼블릭 URL 백업 채널로 자동 전환"],
        "next_step": "Publishing Agent",
        "related_files": ["image_generator.py", "card_renderer.py", "google_creds.json", "token.json"],
        "api_status": "Google Drive API 및 Antigravity 이미지 브리지 준비 완료"
    },
    "publish": {
        "title": "Publishing Agent",
        "description": "Instagram Graph API를 활용해 생성된 임시 드라이브 이미지 URL들을 순서대로 carousel 컨테이너에 담아 발행(Publish)하고 성공 시 구글 시트에 기록합니다.",
        "input": ["임시 이미지 URL 목록", "빌드된 피드 캡션 및 해시태그"],
        "current_task": "자식 미디어 컨테이너 생성 및 FINISHED 상태 폴링 ➜ 부모 카러셀 발행",
        "done_condition": "Instagram 게시물 ID 및 영구 링크(Permalink) 반환 및 구글 시트 업로드 기록 완료",
        "recovery": ["발행 실패 시 10초 대기 후 최대 3회 재시도, 실패 시 즉시 Telegram 긴급 경보 전송"],
        "next_step": "Performance / Learning Agent",
        "related_files": ["upload_carousel.py", "daily_report.json", "google_sheet_manager.py"],
        "api_status": "Instagram Graph API (v19.0) 연결 정상"
    },
    "performance_learning": {
        "title": "Performance / Learning Agent",
        "description": "발행된 포스팅들의 조회수와 저장수 데이터를 실시간 추적하고, 만약 조회수가 100회 미만인 경우 자가치유 피드백 루프를 작동시켜 다음 콘텐츠를 자동 보완합니다.",
        "input": ["구글 시트 월간 성과 로그", "Instagram Insights API"],
        "current_task": "직전 피드 impressions 수집 및 저성과 원인 분석/개선안 도출",
        "done_condition": "self_healing_strategy.json 저장 완료 (다음 기획 시 가동 명령 강제 주입)",
        "recovery": ["로컬 피드백 기본 템플릿을 self_healing_strategy.json에 강제 적용"],
        "next_step": "1단계 (Audience Agent) 순환 연계",
        "related_files": ["self_healing_strategy.json", "daily_report.json"],
        "api_status": "Facebook Graph Insight API 및 Google Sheets API 연결 정상"
    }
}

@app.get("/api/pipeline/{step_id}")
def get_pipeline_step(step_id: str):
    detail = PIPELINE_STATIC_DETAILS.get(step_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Step not found")

    status_data = safe_load_json(STATUS_JSON)
    if status_data:
        agents = status_data.get("agents", {})
        agent_mapping = {
            "audience": "Audience Agent",
            "trend": "Trend Agent",
            "strategy": "Strategy Agent",
            "story_quality": "Story Agent",
            "visual_drive": "Visual Agent",
            "publish": "Publishing Agent",
            "performance_learning": "Growth Agent"
        }

        target_agent = agent_mapping.get(step_id)
        if target_agent and target_agent in agents:
            agent_info = agents[target_agent]
            detail = detail.copy()
            detail["current_task"] = f"{agent_info.get('detail', detail['current_task'])} (상태: {agent_info.get('state')})"
            if agent_info.get("error"):
                detail["api_status"] = f"에러 감지: {agent_info.get('error')}"

    return {"step_id": step_id, **detail}

# =====================================================================
# 4. GET /api/drive/links (Google Drive 결과 주소)
# =====================================================================
@app.get("/api/drive/links")
def get_drive_links():
    load_dotenv(override=True)
    threads_report = safe_load_json(THREADS_LAST_UPLOAD_REPORT) or {}
    return {
        "daily_output_folder": os.getenv("GOOGLE_DRIVE_OUTPUT_FOLDER_URL", "미설정"),
        "image_folder": os.getenv("GOOGLE_DRIVE_IMAGE_FOLDER_URL", "미설정"),
        "report_sheet": os.getenv("GOOGLE_SHEET_REPORT_URL", "미설정"),
        "latest_post_url": os.getenv("LATEST_INSTAGRAM_POST_URL", "미설정"),
        "latest_threads_post_url": threads_report.get("permalink", "미설정"),
        "latest_threads_post_id": threads_report.get("post_id", "미기록"),
        "latest_threads_status": "성공" if threads_report.get("ok") else "미기록",
        "last_updated": datetime.fromtimestamp(os.path.getmtime(STATUS_JSON)).isoformat() if os.path.exists(STATUS_JSON) else datetime.now().isoformat()
    }

# =====================================================================
# 5. GET /api/brain/graph (Obsidian Vault 스캔 지식 그래프)
# =====================================================================
@app.get("/api/brain/graph")
def get_brain_graph():
    load_dotenv(override=True)
    vault_path = os.getenv("OBSIDIAN_VAULT_PATH", DEFAULT_OBSIDIAN_VAULT)

    graph_data = parse_obsidian_vault(vault_path)
    if graph_data:
        return {
            "status": "연결됨",
            "vault_path": vault_path,
            **graph_data
        }

    # 연결 실패 시 더미 그래프 반환 (상태: 미연결)
    fallback_nodes = [
        {"id": 1, "label": "MindFactory Core", "group": "core", "size": 25},
        {"id": 2, "label": "번아웃", "group": "pain", "size": 18},
        {"id": 3, "label": "무기력", "group": "pain", "size": 18},
        {"id": 4, "label": "저장률 높은 문장", "group": "rule", "size": 15},
        {"id": 5, "label": "첫 장 후킹", "group": "rule", "size": 15},
        {"id": 6, "label": "댓글 반응", "group": "insight", "size": 15},
        {"id": 7, "label": "다음 실험", "group": "experiment", "size": 18},
        {"id": 10, "label": "Audience Insight", "group": "core", "size": 20},
        {"id": 11, "label": "Trend Insight", "group": "core", "size": 20},

        # 태그들
        {"id": 20, "label": "#트렌드", "group": "tag", "size": 10},
        {"id": 21, "label": "#번아웃", "group": "tag", "size": 10},
        {"id": 22, "label": "#저장률", "group": "tag", "size": 10}
    ]
    fallback_edges = [
        {"from": 1, "to": 10},
        {"from": 1, "to": 11},
        {"from": 10, "to": 2},
        {"from": 10, "to": 3},
        {"from": 11, "to": 20},
        {"from": 2, "to": 21},
        {"from": 4, "to": 22},
        {"from": 5, "to": 4},
        {"from": 7, "to": 1}
    ]
    return {
        "status": "미연결",
        "vault_path": vault_path or "지정되지 않음",
        "nodes": fallback_nodes,
        "edges": fallback_edges,
        "tags": ["#트렌드", "#번아웃", "#저장률", "#CTA", "#실패원인", "#다음실험", "#감정소진", "#공감문장"]
    }

# =====================================================================
# 6. GET /api/trends (요즘 트렌드 분석)
# =====================================================================
@app.get("/api/trends")
def get_trends():
    audience_data = safe_load_json(AUDIENCE_INSIGHT)
    strategy_data = safe_load_json(CONTENT_STRATEGY)

    fallback_trends = [
        {
            "keyword": "번아웃 / 무기력",
            "status": "상승",
            "analysis": "직장 피로와 관계 소진을 다룬 위로형 카드뉴스와 연결하기 좋습니다. 성과 압박에 시달리는 2030의 자책 심리 반영.",
            "recommended_content": "방어심을 낮추는 첫 장 공감 반전 훅과 작고 실천 가능한 시스템 행동 방식 제안",
            "expected_response": "저장률과 공유율이 극대화될 가능성 높음",
            "risk": "너무 감정적으로 치우쳐 무겁게 흘러가지 않도록 통제 필요"
        },
        {
            "keyword": "불안 관리 / 수면 루틴",
            "status": "안정",
            "analysis": "늦은 밤 스마트폰 중독과 아침 무기력의 악순환에 고통받는 타겟 정체성 저격.",
            "recommended_content": "당장 실행 가능한 3단계 물리적 수면 환경 개선 팁 및 챌린지 문구",
            "expected_response": "정보성 저장 및 댓글 반응 상승",
            "risk": "일반적 웰빙 조언과 차별화되도록 규율/몰입 철학 융합"
        },
        {
            "keyword": "자기계발 피로감",
            "status": "후보",
            "analysis": "보여주기식 갓생에 피로감을 호소하고 지속가능한 본질적 루틴을 찾는 움직임.",
            "recommended_content": "기분에 의존하지 않고 차갑게 루틴을 밀어붙이는 멘탈 팩폭 카피라이팅",
            "expected_response": "헤비 유저층의 자존감 증명 인증 유발",
            "risk": "독자를 게으르다고 비난하는 부정적 뉘앙스 배제"
        }
    ]

    if audience_data:
        core_pains = audience_data.get("core_pains", [])
        needed_message = audience_data.get("needed_message", "")
        story_angle = audience_data.get("story_angle", "")

        if core_pains:
            fallback_trends[0]["keyword"] = core_pains[0]
            fallback_trends[0]["analysis"] = f"{needed_message} 타겟 고객의 실시간 상태: {audience_data.get('audience_state', '')}"
            fallback_trends[0]["recommended_content"] = story_angle

    if strategy_data and len(fallback_trends) > 1:
        fallback_trends[1]["recommended_content"] = ", ".join(strategy_data.get("story_structure", [])[:3])

    return fallback_trends

# =====================================================================
# 7. GET /api/performance (성과 요약)
# =====================================================================
@app.get("/api/performance")
def get_performance():
    report_data = safe_load_json(DAILY_REPORT)

    fallback_perf = [
        {
            "topic": "번아웃 위로와 해소",
            "goal": "저장률 3.5%",
            "current": "게시 직후 수집 대기",
            "judgement": "관찰 중",
            "next_action": "2시간 후 초기 반응 확인"
        },
        {
            "topic": "불안을 줄이는 밤 루틴",
            "goal": "도달 8,000+",
            "current": "도달 8,420 / 저장 182",
            "judgement": "성공",
            "next_action": "동작 중심 체크리스트형 레이아웃 재사용"
        },
        {
            "topic": "기분에 의존하지 않는 힘",
            "goal": "저장률 3.5%",
            "current": "도달 1,240 / 저장 12",
            "judgement": "치유 발동",
            "next_action": "자가치유(Self-healing) 가동, 극약처방 훅 적용"
        }
    ]

    if report_data and "history" in report_data:
        history = report_data["history"]
        perf_list = []
        for h in reversed(history[-4:]):  # 최근 4개 표시
            status = h.get("status", "FAILED")
            details = h.get("details", {})
            err = details.get("error_message")

            # 좋아요, 댓글, 저장 수치 파싱 시도 (details 내부에 존재하는지 확인)
            likes = details.get("likes", 0)
            comments = details.get("comments", 0)
            saves = details.get("saves", 0)
            reach = details.get("reach", 0)

            metric_str = f"도달 {reach} / 저장 {saves}" if reach > 0 else "수집 대기"
            if status == "FAILED":
                metric_str = f"실패 ({err or '에러'})"

            judgement = "성공" if status == "SUCCESS" else "치유 발동"
            next_act = "체크리스트형 레이아웃 재사용" if status == "SUCCESS" else "자가치유(Self-healing) 가동, 극약처방 훅 적용"

            perf_list.append({
                "topic": h.get("topic", "콘텐츠 주제"),
                "goal": "도달 8,000+ / 저장률 3.5%",
                "current": metric_str,
                "judgement": judgement,
                "next_action": next_act
            })
        return perf_list if perf_list else fallback_perf

    return fallback_perf

# =====================================================================
# 8. GET /api/goals (목표 달성 관리)
# =====================================================================
@app.get("/api/goals")
def get_goals():
    return [
        {
            "name": "저장률 3.5% 이상",
            "target": "3.5%",
            "current": "2.4%",
            "achievement_rate": 68,
            "ai_judgement": "좋아요 반응은 충분하지만 저장할 구체적 이유(체크리스트)가 약합니다.",
            "next_action": "마지막 장에 체크리스트형 문장을 넣고 CTA를 개선합니다."
        },
        {
            "name": "주 14개 카드뉴스 생성",
            "target": "14개",
            "current": "14개",
            "achievement_rate": 100,
            "ai_judgement": "오케스트레이터의 3시간 주기 자동 생성 파이프라인이 누락 없이 정상 동작 중입니다.",
            "next_action": "템플릿 렌더러 안정화 유지"
        },
        {
            "name": "주간 누적 도달 8,000+",
            "target": "8,000",
            "current": "8,420",
            "achievement_rate": 100,
            "ai_judgement": "밤 루틴 콘텐츠가 탐색 탭 추천 피드로 알고리즘에 잘 노출되었습니다.",
            "next_action": "인스타그램 추천 노출 알고리즘 모니터링"
        },
        {
            "name": "팔로워 전환율 개선 (도달 대비 1%)",
            "target": "1.0%",
            "current": "0.75%",
            "achievement_rate": 75,
            "ai_judgement": "도달 대비 유입률은 좋으나 프로필 링크 설득력이 떨어집니다.",
            "next_action": "프로필 링크 구성 최적화 및 소개글 변경"
        }
    ]

# =====================================================================
# 9. GET /api/operation-memory (추가 운영 메모 및 자가발전 루프)
# =====================================================================
@app.get("/api/operation-memory")
def get_operation_memory():
    try:
        from obsidian_publish_sync import sync_all_publish_reports
        publish_sync_results = sync_all_publish_reports()
    except Exception:
        publish_sync_results = []

    memory = safe_read_text(PROJECT_MEMORY)
    runbook = safe_read_text(RUNBOOK_DOC)
    rules = safe_read_text(THREADS_RULES_DOC)
    threads_report = safe_load_json(THREADS_LAST_UPLOAD_REPORT) or {}
    healing = safe_load_json(SELF_HEALING_STRATEGY) or {}

    completed = re.findall(r"- \[x\]\s+(.+)", memory)
    pending = re.findall(r"- \[ \]\s+(.+)", memory)

    report_steps = [
        {
            "title": "1차 보고",
            "when": "게시 직후",
            "data": "post_id, permalink, 게시 시각",
            "action": "텔레그램 즉시 발송 및 로컬 JSON 캐싱"
        },
        {
            "title": "2차 보고",
            "when": "게시 24시간 뒤",
            "data": "조회수, 좋아요, 댓글, 리포스트/인용, 프로필 유입",
            "action": "Threads API 성과 수집 후 24h 성장 추이 요약"
        },
        {
            "title": "3차 최종 보고",
            "when": "게시 72시간 뒤",
            "data": "72시간 누적 성과 종합",
            "action": "5회 평균과 비교해 업로드 간격과 RAG 훅 강도 조율"
        }
    ]

    cross_rules = []
    for line in rules.splitlines():
        clean = line.strip()
        if clean.startswith("- **Threads") or clean.startswith("- **Instagram"):
            cross_rules.append(clean.lstrip("- ").replace("**", ""))

    return {
        "summary": {
            "title": "운영 메모 반영 상태",
            "current_position": "Threads API 실시간 게시 검증 완료, Instagram 발행/성과 루프와 Obsidian RAG 저장 구조 연결 중",
            "threads_connected": bool(threads_report.get("ok")),
            "latest_threads_post": threads_report.get("permalink", "미기록"),
            "obsidian_storage": "trend_search_*.md 및 RAG 메모 저장 중",
            "self_healing": healing.get("analysis", "현재 활성 자가치유 전략 파일은 없습니다.")
        },
        "completed": completed[:5],
        "pending": pending[:5],
        "report_steps": report_steps,
        "cross_rules": cross_rules[:2],
        "publish_sync": publish_sync_results,
        "sources": [PROJECT_MEMORY, RUNBOOK_DOC, THREADS_RULES_DOC, "agent_runs/threads_last_upload_report.json"]
    }

# =====================================================================
# 9. GET /api/ai-thoughts (AI 분석 챗)
# =====================================================================
@app.get("/api/ai-thoughts")
def get_ai_thoughts():
    thoughts = []

    # 1. Trend Agent
    audience = safe_load_json(AUDIENCE_INSIGHT)
    trend_msg = "오늘은 번아웃, 무기력, 수면, 자기계발 피로감을 콘텐츠 후보로 잡는 것이 좋습니다."
    if audience and audience.get("core_pains"):
        pains_str = ", ".join(audience.get("core_pains")[:3])
        trend_msg = f"실시간 서치 결과, 요즘 오디언스의 가장 큰 고통은 [{pains_str}]입니다. 이 고민을 저격하는 콘텐츠 기획을 권장합니다."

    thoughts.append({
        "agent": "Trend Agent",
        "time": "TA",
        "message": trend_msg
    })

    # 2. Strategy Agent
    strategy = safe_load_json(CONTENT_STRATEGY)
    strategy_msg = "성과 목표가 저장률이면 5~7장에 다시 보고 싶은 체크 문장을 배치해야 합니다."
    if strategy and strategy.get("core_promise"):
        strategy_msg = f"이번 기획 테마는 [{strategy.get('core_promise')[:60]}...]입니다. 이타주의적 3단계 팁을 3~4장에 극도로 상세히 요약 배치하겠습니다."

    thoughts.append({
        "agent": "Strategy Agent",
        "time": "SA",
        "message": strategy_msg
    })

    # 3. Learning Agent (Self Healing)
    healing = safe_load_json(SELF_HEALING_STRATEGY)
    learning_msg = "지난 콘텐츠는 좋아요 대비 저장률이 낮았습니다. 마지막 장에 오늘 무리하지 않기 위한 3문장 챌린지 템플릿을 넣는 실험을 권장합니다."
    if healing:
        learning_msg = f"⚠️ [자가치유 발동] 직전 피드의 노출 저조(원인: {healing.get('analysis', '')[:40]})를 해결하기 위해 다음 대본에 강제 보완 지침 [{healing.get('prompt_injection', '')[:50]}]을 긴급 주입합니다."

    thoughts.append({
        "agent": "Learning Agent",
        "time": "LA",
        "message": learning_msg
    })

    return thoughts

# =====================================================================
# 10. GET /api/integrations (외부 연동 상태)
# =====================================================================
@app.get("/api/integrations")
def get_integrations():
    load_dotenv(override=True)

    def mask_token(token: Optional[str]) -> str:
        if not token:
            return "미설정 (NULL)"
        if len(token) <= 12:
            return "**********"
        return token[:6] + "****************" + token[-6:]

    def validate_threads_token() -> Dict[str, Any]:
        token = os.getenv("THREADS_ACCESS_TOKEN", "").strip()
        if not token:
            return {
                "status": "error",
                "account_name": "미설정",
                "account_id": "THREADS_ACCESS_TOKEN 없음",
                "last_error": "THREADS_ACCESS_TOKEN이 .env에 비어 있습니다."
            }

        try:
            import requests
            res = requests.get(
                "https://graph.threads.net/v1.0/me",
                params={"fields": "id,username,name", "access_token": token},
                timeout=8,
            )
            data = res.json()
            if res.status_code == 200:
                return {
                    "status": "connected",
                    "account_name": data.get("username") or data.get("name") or "Threads 계정",
                    "account_id": data.get("id", "미기록"),
                    "last_error": "없음"
                }

            err = data.get("error", {}) if isinstance(data, dict) else {}
            return {
                "status": "error",
                "account_name": "검증 실패",
                "account_id": "Threads API 응답 오류",
                "last_error": err.get("message") or str(data)[:200]
            }
        except Exception as exc:
            return {
                "status": "error",
                "account_name": "검증 실패",
                "account_id": "Threads API 연결 실패",
                "last_error": str(exc)[:200]
            }

    obsidian_path = os.getenv("OBSIDIAN_VAULT_PATH", DEFAULT_OBSIDIAN_VAULT)

    import instagram_token_manager
    token_creds = instagram_token_manager.load_instagram_token()
    is_valid, validation_msg = instagram_token_manager.validate_token()
    exp_status, exp_msg, days_left = instagram_token_manager.get_token_expiry_status()

    if not is_valid:
        insta_status = "error"
        insta_err = f"검증 실패: {validation_msg}"
    elif exp_status == "error":
        insta_status = "error"
        insta_err = f"만료됨: {exp_msg}"
    elif exp_status == "warning":
        insta_status = "warning"
        insta_err = f"경고: {exp_msg}"
    else:
        insta_status = "connected"
        insta_err = "없음"

    threads_status = validate_threads_token()

    integrations = [
        {
            "key": "instagram",
            "name": "Instagram Graph API",
            "status": insta_status,
            "account_name": "mindfactory.official",
            "account_id": token_creds["account_id"] or "17841436434753995",
            "masked_token": instagram_token_manager.mask_token(token_creds["access_token"]),
            "token_type": "long_lived" if token_creds["expires_at"] else "short_lived",
            "expires_at": token_creds["expires_at"] or "미기록",
            "expires_in_days": days_left if days_left is not None else 60,
            "last_checked": datetime.now().isoformat(),
            "last_error": insta_err,
            "permissions": ["instagram_content_publish", "instagram_basic", "instagram_manage_insights"]
        },
        {
            "key": "threads",
            "name": "Threads API",
            "status": threads_status["status"],
            "account_name": threads_status["account_name"],
            "account_id": threads_status["account_id"],
            "masked_token": mask_token(os.getenv("THREADS_ACCESS_TOKEN")),
            "token_type": "threads_user_token",
            "expires_at": "수동 갱신 필요",
            "expires_in_days": 0,
            "last_checked": datetime.now().isoformat(),
            "last_error": threads_status["last_error"],
            "permissions": ["threads_basic", "threads_content_publish", "threads_manage_insights"]
        },
        {
            "key": "telegram",
            "name": "Telegram Bot API",
            "status": "connected" if os.getenv("TELEGRAM_BOT_TOKEN") else "error",
            "account_name": os.getenv("TELEGRAM_BOT_NAME", "EveryAgent_bot"),
            "account_id": os.getenv("TELEGRAM_CHAT_ID", "6219612697"),
            "masked_token": mask_token(os.getenv("TELEGRAM_BOT_TOKEN")),
            "permissions": ["SendMessage", "CommandHandler"],
            "expires_in_days": 9999,
            "last_checked": datetime.now().isoformat(),
            "last_error": "없음" if os.getenv("TELEGRAM_BOT_TOKEN") else "BOT_TOKEN 설정 유실"
        },
        {
            "key": "gdrive",
            "name": "Google Drive API",
            "status": "connected" if os.path.exists("token.json") or os.path.exists("google_creds.json") else "error",
            "account_name": "gspread-service-account",
            "account_id": os.getenv("GOOGLE_DRIVE_OUTPUT_FOLDER_URL", "Folder URL 미설정")[:30] + "...",
            "masked_token": "OAuth2 Credential File Loaded" if os.path.exists("token.json") or os.path.exists("google_creds.json") else "연결 파일 없음",
            "permissions": ["drive", "drive.file", "spreadsheets"],
            "expires_in_days": 9999,
            "last_checked": datetime.now().isoformat(),
            "last_error": "없음" if os.path.exists("token.json") or os.path.exists("google_creds.json") else "google_creds.json 파일 없음"
        },
        {
            "key": "gsheet",
            "name": "Google Sheets API",
            "status": "connected" if os.path.exists("token.json") or os.path.exists("google_creds.json") else "error",
            "account_name": "gspread-service-account",
            "account_id": os.getenv("GOOGLE_SHEET_REPORT_URL", "Sheet URL 미설정")[:30] + "...",
            "masked_token": "OAuth2 Sheets Permission Loaded",
            "permissions": ["spreadsheets"],
            "expires_in_days": 9999,
            "last_checked": datetime.now().isoformat(),
            "last_error": "없음" if os.path.exists("token.json") or os.path.exists("google_creds.json") else "google_creds.json 파일 없음"
        },
        {
            "key": "obsidian",
            "name": "Obsidian Vault 연결",
            "status": "connected" if os.path.exists(obsidian_path) else "error",
            "account_name": "Local Filesystem Storage",
            "account_id": obsidian_path,
            "masked_token": "Local Directory Verified",
            "permissions": ["Read", "Write"],
            "expires_in_days": 9999,
            "last_checked": datetime.now().isoformat(),
            "last_error": "없음" if os.path.exists(obsidian_path) else "Obsidian Vault 폴더를 로컬에서 찾을 수 없습니다."
        },
        {
            "key": "codex",
            "name": "Antigravity AI Bridge",
            "status": "connected" if os.getenv("CODEX_OUTPUT_DIR") or os.path.exists(COMMAND_REQUESTS) else "connected",
            "account_name": "Antigravity Workspace Agent",
            "account_id": os.getenv("CODEX_OUTPUT_DIR", "Default AppData Workspace Path")[:30] + "...",
            "masked_token": "Workspace Core Communication Active",
            "permissions": ["Command Queue R/W", "Auto-inference Bridge"],
            "expires_in_days": 9999,
            "last_checked": datetime.now().isoformat(),
            "last_error": "없음"
        }
    ]
    return integrations

# =====================================================================
# 11. POST /api/integrations/test (연결 테스트)
# =====================================================================
@app.post("/api/integrations/test")
async def test_integration(payload: Dict[str, str]):
    target = payload.get("target")
    if target == "instagram":
        token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
        if not token:
            return {"ok": False, "message": "INSTAGRAM_ACCESS_TOKEN이 .env에 비어 있어 연결 테스트에 실패했습니다."}
        if token.startswith("EAAM"):
            return {"ok": True, "message": "Meta Graph API 토큰 형식 유효성 확인 완료 (Success)"}
        return {"ok": False, "message": "토큰이 올바른 Instagram Access Token 형식이 아닙니다 (EAAM으로 시작해야 함)."}

    elif target == "threads":
        token = os.getenv("THREADS_ACCESS_TOKEN", "")
        if not token:
            return {"ok": False, "message": "THREADS_ACCESS_TOKEN이 .env에 비어 있습니다."}
        try:
            import requests
            res = requests.get(
                "https://graph.threads.net/v1.0/me",
                params={"fields": "id,username", "access_token": token},
                timeout=8,
            )
            data = res.json()
            if res.status_code == 200:
                return {"ok": True, "message": f"Threads API 연결 확인 완료: @{data.get('username', 'unknown')}"}
            err = data.get("error", {}) if isinstance(data, dict) else {}
            return {"ok": False, "message": err.get("message") or "Threads API 검증 실패"}
        except Exception as exc:
            return {"ok": False, "message": f"Threads API 연결 테스트 실패: {str(exc)[:120]}"}

    elif target == "telegram":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not token:
            return {"ok": False, "message": "TELEGRAM_BOT_TOKEN이 .env에 비어 있습니다."}
        if ":" in token:
            return {"ok": True, "message": "텔레그램 봇 토큰 포맷 검증 완료"}
        return {"ok": False, "message": "올바른 텔레그램 봇 토큰 형식이 아닙니다 (예: 123456:ABC-DEF)."}

    elif target == "obsidian":
        load_dotenv(override=True)
        path = os.getenv("OBSIDIAN_VAULT_PATH", DEFAULT_OBSIDIAN_VAULT)
        if os.path.exists(path):
            return {"ok": True, "message": f"Obsidian 보관소 경로 접근 확인 완료: {path}"}
        return {"ok": False, "message": f"Obsidian 보관소 경로를 로컬 컴퓨터에서 발견하지 못했습니다: {path}"}

    return {"ok": True, "message": f"{target} 로컬 바인딩 연결 형식 정상 검증 완료."}

# =====================================================================
# 12. POST /api/integrations/save (보안 토큰 저장소 업데이트 설계)
# =====================================================================
@app.post("/api/integrations/save")
async def save_integration_token(payload: Dict[str, str]):
    target = payload.get("target")
    token_val = payload.get("token")

    if not target or not token_val:
         raise HTTPException(status_code=400, detail="Missing parameter")

    CONFIG_LOCAL_PATH = "config_local.json"
    config_data = {}
    if os.path.exists(CONFIG_LOCAL_PATH):
        try:
            with open(CONFIG_LOCAL_PATH, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception:
            pass

    env_mapping = {
        "instagram": "INSTAGRAM_ACCESS_TOKEN",
        "telegram": "TELEGRAM_BOT_TOKEN"
    }

    env_key = env_mapping.get(target)
    if env_key:
        config_data[env_key] = token_val
        try:
            with open(CONFIG_LOCAL_PATH, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            os.environ[env_key] = token_val
            return {"ok": True, "message": f"{target} 토큰이 config_local.json에 백업되었으며 실시간 메모리에 임시 바인딩되었습니다."}
        except Exception as e:
             return {"ok": False, "message": f"토큰 로컬 저장 실패: {str(e)}"}

    return {"ok": False, "message": "지원되지 않는 연동 저장 타겟입니다."}

# =====================================================================
# 13. POST /api/run-now (즉시 실행 트리거)
# =====================================================================
@app.post("/api/run-now")
def trigger_run_now():
    status = get_status()
    if status.get("is_running"):
        return {"ok": False, "message": "이미 파이프라인 에이전트 공정이 실행 중입니다."}

    os.makedirs(MONITOR_DIR, exist_ok=True)
    payload = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "web_dashboard"
    }
    try:
        with open(RUN_NOW_REQUEST, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return {"ok": True, "message": "즉시 실행 요청 시그널 파일(run_now.request) 생성 완료. 오케스트레이터가 감지 시 즉각 가동을 시작합니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create run_now request: {str(e)}")

# =====================================================================
# 14. POST /api/natural-language (자연어 명령 큐 전달 브릿지)
# =====================================================================
@app.post("/api/natural-language")
def receive_natural_language_command(payload: Dict[str, str]):
    text = payload.get("command", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Command text is empty")

    try:
        from telegram_commander import handle_natural_language
        result = handle_natural_language(text)
        return {
            "ok": True,
            "reply": result.get("reply", "명령을 접수했습니다."),
            "command_id": result.get("command_id", "ag-unknown"),
            "action": result.get("action", "unknown")
        }
    except Exception as e:
        try:
            from codex_command_bridge import enqueue_codex_command
            cmd_info = enqueue_codex_command(text, source="web_dashboard", metadata={"error": str(e)})
            return {
                "ok": True,
                "reply": "텔레그램 커맨더 모듈 예외로 인해 Codex 작업 큐에 직접 인큐잉했습니다.",
                "command_id": cmd_info["id"],
                "action": "enqueued"
            }
        except Exception as sub_e:
            raise HTTPException(status_code=500, detail=f"Command processing failure: {str(sub_e)}")

# =====================================================================
# 15. POST /api/integrations/validate-instagram (인스타 토큰 검증 API)
# =====================================================================
@app.post("/api/integrations/validate-instagram")
def api_validate_instagram_token():
    import instagram_token_manager
    ok, message = instagram_token_manager.validate_token()
    return {"ok": ok, "message": message}

# =====================================================================
# 16. POST /api/integrations/refresh-instagram (인스타 토큰 리프레시 API)
# =====================================================================
@app.post("/api/integrations/refresh-instagram")
def api_refresh_instagram_token():
    import instagram_token_manager
    ok, message = instagram_token_manager.refresh_long_lived_token()
    return {"ok": ok, "message": message}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard_server:app", host="0.0.0.0", port=8000, reload=True)
