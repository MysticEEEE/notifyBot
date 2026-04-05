#!/bin/bash
# Hook: Notification — Claude is waiting/idle

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/notify.sh" "timeout" "等待中，需要你的操作" "medium"
exit 0
