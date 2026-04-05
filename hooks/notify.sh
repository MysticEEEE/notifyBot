#!/bin/bash
# Claude Code notification hook - sends events via OpenClaw WeChat channel
# Usage: notify.sh <event_type> <message> [priority]
# Exit 0 always — never block Claude Code

set -euo pipefail

EVENT_TYPE="${1:-unknown}"
MESSAGE="${2:-No message}"
PRIORITY="${3:-low}"

OPENCLAW_CONTAINER="openclaw"
WEIXIN_CHANNEL="openclaw-weixin"
WEIXIN_TARGET="o9cq802hp0ypsg3rherwni-puwvy@im.wechat"

TIMESTAMP=$(date '+%H:%M:%S')
CWD=$(basename "$(pwd)")

# Get session name from CLAUDE_SESSION_NAME env or fallback
SESSION_NAME="${CLAUDE_SESSION_NAME:-${CWD}}"

# Format notification text
case "$EVENT_TYPE" in
  approval_needed) ICON="🔔" ;;
  task_complete)   ICON="✅" ;;
  timeout)         ICON="⏰" ;;
  *)               ICON="📋" ;;
esac

NOTIFY_TEXT="${ICON} [Claude Code] ${MESSAGE}
📂 ${SESSION_NAME} | ⏱ ${TIMESTAMP}"

# Send via OpenClaw message send
docker exec "$OPENCLAW_CONTAINER" openclaw message send \
  --channel "$WEIXIN_CHANNEL" \
  --target "$WEIXIN_TARGET" \
  -m "$NOTIFY_TEXT" >/dev/null 2>&1 || true

exit 0
