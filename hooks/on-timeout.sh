#!/bin/bash
# Hook: Claude Code has been idle/unresponsive
# Can be called by an external watchdog

MINUTES="${1:-5}"
MESSAGE="Claude Code 已超过 ${MINUTES} 分钟无响应"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/notify.sh" "timeout" "$MESSAGE" "medium"
