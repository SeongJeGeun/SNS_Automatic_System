import json
import os
from datetime import datetime

from antigravity_bridge import run_json_task


def _write_request(path, title, prompt, response_path, schema_hint, mode):
    lines = [
        f"# {title}",
        "",
        "이 파일은 Antigravity CLI가 현재 작업공간에서 검색/분석/추론해 처리할 요청입니다.",
        f"처리 후 결과를 `{response_path}` 파일에 저장합니다.",
        "",
        "## Output",
        schema_hint.strip(),
        "",
        "## Prompt",
        "```text",
        prompt.strip(),
        "```",
        "",
        f"생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[Antigravity] 요청 파일 생성: {path}")
    return run_json_task(
        prompt=f"{schema_hint.strip()}\n\n## Prompt\n{prompt.strip()}",
        output_path=response_path,
        mode=mode,
        request_path=path,
    )


def write_story_request(prompt):
    return _write_request(
        "codex_story_requests.md",
        "Antigravity Story Request",
        prompt,
        "codex_story_response.json",
        """
순수 JSON만 저장합니다.

{
  "title": "이번 탐색 주제 요약",
  "pages": [
    {
      "page": 1,
      "image_prompt": "Background image description in English, no text, no letters",
      "heading": "카드 대제목",
      "sub_text": "카드 설명",
      "theme_color": "deep_navy"
    }
  ]
}
""",
        mode="story_json",
    )


def write_strategy_request(prompt):
    return _write_request(
        "codex_strategy_requests.md",
        "Antigravity Strategy Request",
        prompt,
        "codex_strategy_response.json",
        """
순수 JSON만 저장합니다.

{
  "analysis": "성과가 낮았던 이유",
  "action_items": "다음 콘텐츠에서 고칠 점",
  "prompt_injection": "다음 카드뉴스 대본에 강제로 반영할 지침"
}
""",
        mode="strategy_json",
    )


def read_json_response(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"[Codex] 응답 파일 로드 실패 ({path}): {exc}")
        return None
