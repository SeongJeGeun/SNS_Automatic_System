#!/bin/bash
# MindFactory SNS Automation QA Gates Check Script
cd "$(dirname "$0")/.."

echo "========================================="
echo "       MindFactory QA Gates Checking     "
echo "========================================="

# 1. 파일 크기 이상치 점검 (1000 라인 초과 검사)
echo "[Step 1] Checking for file size anomalies (> 1000 lines)..."
OVERSIZED_FILES=$(find . -maxdepth 1 -name "*.py" | while read -r file; do
    lines=$(wc -l < "$file")
    if [ "$lines" -gt 1000 ]; then
        echo "⚠️  Oversized File: $file ($lines lines)"
    fi
done)

if [ -n "$OVERSIZED_FILES" ]; then
    echo "$OVERSIZED_FILES"
else
    echo "✅ No single Python file exceeds 1000 lines (except dashboard_server.py)."
fi

# 2. 미사용 임시 JSON 파일 확인
echo "[Step 2] Checking for un-archived JSON files at root..."
ROOT_JSON=$(find . -maxdepth 1 -name "*.json" | while read -r file; do
    if ! git check-ignore -q "$file"; then
        echo "$file"
    fi
done)
if [ -n "$ROOT_JSON" ]; then
    echo "⚠️  Stale JSON files found at root:"
    echo "$ROOT_JSON"
else
    echo "✅ Root is clean from temporary output JSONs."
fi

# 3. E2E 테스트 검증 실행
echo "[Step 3] Running End-to-End flow verification test..."
python3 codex_e2e_check.py
if [ $? -eq 0 ]; then
    echo "✅ E2E system flow successfully passed."
else
    echo "❌ E2E system flow check FAILED."
    exit 1
fi

echo "========================================="
echo "        QA Gates Check Completed         "
echo "========================================="
