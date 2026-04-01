#!/bin/bash
# Hook: Claude Code task encountered an error

ERROR_INFO=""
if [ ! -t 0 ]; then
  ERROR_INFO=$(cat)
fi

MESSAGE="Claude Code 任务报错"
if [ -n "$ERROR_INFO" ]; then
  # Truncate to 500 chars to avoid oversized payloads
  ERROR_INFO=$(echo "$ERROR_INFO" | head -c 500)
  MESSAGE="Claude Code 报错: ${ERROR_INFO}"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/notify.sh" "error" "$MESSAGE" "high"
