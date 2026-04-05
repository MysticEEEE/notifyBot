#!/bin/bash
# Hook: PermissionRequest — Claude Code needs user approval
# Receives JSON on stdin: {tool_name, tool_input, session_id, ...}

INPUT=$(cat)
INFO=$(echo "$INPUT" | python3 -c '
import sys, json
d = json.load(sys.stdin)
tool = d.get("tool_name", "未知工具")
session = d.get("session_id", "")[:8] if d.get("session_id") else ""
# Extract meaningful tool input summary
tool_input = d.get("tool_input", {})
if isinstance(tool_input, dict):
    # For Bash: show command
    cmd = tool_input.get("command", "")
    if cmd:
        summary = cmd[:120]
    # For Edit/Write: show file path
    elif tool_input.get("file_path"):
        summary = tool_input["file_path"]
    # For WebFetch: show URL
    elif tool_input.get("url"):
        summary = tool_input["url"][:120]
    else:
        summary = str(tool_input)[:120]
else:
    summary = str(tool_input)[:120]
print(f"需要审批 {tool}: {summary}")
' 2>/dev/null || echo "需要审批操作")

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/notify.sh" "approval_needed" "$INFO" "high"
exit 0
