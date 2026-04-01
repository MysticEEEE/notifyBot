#!/bin/bash
# Hook: Claude Code task completed

TASK_INFO="${1:-Task completed}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/notify.sh" "task_complete" "$TASK_INFO" "low"
