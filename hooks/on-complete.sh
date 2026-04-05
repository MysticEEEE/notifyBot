#!/bin/bash
# Hook: Stop — Claude finished responding
# Receives JSON on stdin: {session_id, cwd, ...}

INPUT=$(cat)
DIR=$(echo "$INPUT" | python3 -c 'import sys,json,os; print(os.path.basename(json.load(sys.stdin).get("cwd","?")))' 2>/dev/null || echo "?")

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/notify.sh" "task_complete" "回复完成 (${DIR})" "low"
exit 0
