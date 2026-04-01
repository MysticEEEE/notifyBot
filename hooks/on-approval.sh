#!/bin/bash
# Hook: Claude Code needs user approval
# Reads tool info from stdin if available

TOOL_INFO=""
if [ ! -t 0 ]; then
  TOOL_INFO=$(cat)
fi

MESSAGE="Claude Code 需要审批操作"
if [ -n "$TOOL_INFO" ]; then
  MESSAGE="Claude Code 需要审批: ${TOOL_INFO}"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/notify.sh" "approval_needed" "$MESSAGE" "high"
