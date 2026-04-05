#!/bin/bash
# Hook: PostToolUseFailure — tool execution failed
# Receives JSON on stdin: {tool_name, tool_input, error, ...}

INPUT=$(cat)
INFO=$(echo "$INPUT" | python3 -c '
import sys,json
d=json.load(sys.stdin)
tool=d.get("tool_name","?")
err=str(d.get("error",d.get("tool_output","")))[:200]
print(f"{tool}: {err}")
' 2>/dev/null || echo "未知错误")

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/notify.sh" "error" "工具报错 ${INFO}" "high"
exit 0
