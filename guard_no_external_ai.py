import os
import re
import sys


BLOCKED = [
    r"generativelanguage\.googleapis\.com",
    r"google\.genai",
    r"GoogleGenerativeAI",
    r"api\.openai\.com",
    r"anthropic\.com",
    r"GEMINI_API_KEY",
    r"OPENAI_API_KEY",
    r"ANTHROPIC_API_KEY",
    r"CLAUDE_API_KEY",
    r"TELEGRAM_USE_GEMINI",
    r"duckduckgo_search",
    r"urllib\.request\.urlopen",
]

SKIP_DIRS = {".git", "__pycache__", "agent_runs", "faiss_index", "generated_backgrounds"}
SKIP_FILES = {"guard_no_external_ai.py", "orchestrator.log"}
EXTENSIONS = {".py", ".md", ".env", ".example", ".txt", ".json", ".html", ".js"}


def should_scan(path):
    name = os.path.basename(path)
    if name in SKIP_FILES:
        return False
    _, ext = os.path.splitext(path)
    return ext in EXTENSIONS or name in {".env.example", "README.md"}


def main():
    pattern = re.compile("|".join(BLOCKED), re.IGNORECASE)
    violations = []
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            path = os.path.join(root, name)
            if not should_scan(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line_no, line in enumerate(f, start=1):
                        if pattern.search(line):
                            violations.append(f"{path}:{line_no}: {line.strip()}")
            except UnicodeDecodeError:
                continue

    if violations:
        print("외부 AI/API 또는 레거시 브리지 금지 패턴이 발견됐습니다.")
        print("\n".join(violations))
        return 1

    print("OK: 외부 AI/API 직접 호출 및 레거시 브리지 패턴 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
