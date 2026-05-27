import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from datetime import datetime
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()


def _truthy(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def antigravity_enabled() -> bool:
    if _truthy(os.getenv("ANTIGRAVITY_DISABLED")):
        return False
    if _truthy(os.getenv("ANTIGRAVITY_ENABLED")):
        return True
    return bool(_find_cli_command())


def _find_cli_command() -> Optional[str]:
    configured = os.getenv("ANTIGRAVITY_TEXT_COMMAND", "").strip()
    if configured:
        return configured

    for candidate in ("antigravity", "ag"):
        if shutil.which(candidate):
            return f"{candidate} run --stdin"
    return None


def _render_command(template: str, prompt_file: str, output_file: str, mode: str) -> str:
    return template.format(
        prompt_file=shlex.quote(prompt_file),
        output_file=shlex.quote(output_file),
        mode=shlex.quote(mode),
    )


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    stripped = text.strip()
    if not stripped:
        return None

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1)

    if not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            stripped = stripped[start:end + 1]

    try:
        data = json.loads(stripped)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def run_text_task(
    prompt: str,
    output_path: str,
    mode: str,
    expect_json: bool = False,
    request_path: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
) -> Optional[Any]:
    """Run Antigravity CLI and persist a validated text or JSON result.

    Configure the command with ANTIGRAVITY_TEXT_COMMAND. Supported placeholders:
    {prompt_file}, {output_file}, {mode}. If no placeholders are used, the
    prompt is sent through stdin and stdout is written to output_path.
    """
    if not antigravity_enabled():
        return None

    command_template = _find_cli_command()
    if not command_template:
        return None

    timeout = timeout_seconds or int(os.getenv("ANTIGRAVITY_TIMEOUT_SECONDS", "300"))
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="antigravity_bridge_") as tmp_dir:
        prompt_file = request_path or os.path.join(tmp_dir, f"{mode}_prompt.md")
        cli_output_file = os.path.join(tmp_dir, f"{mode}_output.txt")

        if not request_path:
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(prompt)

        has_placeholders = "{" in command_template and "}" in command_template
        command = (
            _render_command(command_template, prompt_file, cli_output_file, mode)
            if has_placeholders
            else command_template
        )

        try:
            result = subprocess.run(
                command,
                input=None if has_placeholders else prompt,
                text=True,
                shell=True,
                capture_output=True,
                timeout=timeout,
                cwd=os.getcwd(),
            )
        except Exception as exc:
            print(f"[Antigravity] CLI 실행 실패 ({mode}): {exc}")
            return None

        output_text = ""
        if os.path.exists(cli_output_file):
            with open(cli_output_file, "r", encoding="utf-8") as f:
                output_text = f.read()
        elif result.stdout:
            output_text = result.stdout

        if result.returncode != 0:
            print(f"[Antigravity] CLI 오류 ({mode}): {result.stderr.strip()[:500]}")
            return None

        if expect_json:
            parsed = _extract_json(output_text)
            if not parsed:
                print(f"[Antigravity] JSON 파싱 실패 ({mode}). 원문 일부: {output_text[:300]}")
                return None
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(parsed, f, ensure_ascii=False, indent=2)
            return parsed

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_text.strip() + "\n")
        return output_text


def run_json_task(prompt: str, output_path: str, mode: str, request_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    json_prompt = f"""
You are running inside Antigravity CLI for the MindFactory SNS automation project.
Return only valid JSON. Do not include markdown fences or explanatory text.

{prompt}
""".strip()
    return run_text_task(
        json_prompt,
        output_path=output_path,
        mode=mode,
        expect_json=True,
        request_path=request_path,
    )


def run_search_task(prompt: str, output_path: str, request_path: Optional[str] = None) -> Optional[str]:
    search_prompt = f"""
You are running inside Antigravity CLI for the MindFactory SNS automation project.
Research the requested topics using your available search/browsing capability.
Write a concise Korean markdown report with:
- 핵심 요약
- 발견한 패턴
- 콘텐츠 기획에 반영할 점
- 참고 출처 링크

{prompt}

Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
""".strip()
    return run_text_task(
        search_prompt,
        output_path=output_path,
        mode="search",
        expect_json=False,
        request_path=request_path,
    )


def run_image_task(prompt: str, output_path: str, request_path: Optional[str] = None) -> Optional[str]:
    command_template = os.getenv("ANTIGRAVITY_IMAGE_COMMAND", "").strip()
    if not command_template:
        return None

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    timeout = int(os.getenv("ANTIGRAVITY_IMAGE_TIMEOUT_SECONDS", os.getenv("ANTIGRAVITY_TIMEOUT_SECONDS", "300")))

    with tempfile.TemporaryDirectory(prefix="antigravity_image_") as tmp_dir:
        prompt_file = request_path or os.path.join(tmp_dir, "image_prompt.txt")
        if not request_path:
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(prompt)

        command = _render_command(command_template, prompt_file, output_path, "image")
        try:
            result = subprocess.run(
                command,
                shell=True,
                text=True,
                capture_output=True,
                timeout=timeout,
                cwd=os.getcwd(),
            )
        except Exception as exc:
            print(f"[Antigravity] 이미지 CLI 실행 실패: {exc}")
            return None

        if result.returncode != 0:
            print(f"[Antigravity] 이미지 CLI 오류: {result.stderr.strip()[:500]}")
            return None

        return output_path if os.path.exists(output_path) and os.path.getsize(output_path) > 0 else None
