#!/bin/bash
# Claude Code notification hook - sends events to WeChat (via AstrBot) + QQ (via OpenClaw)
# Usage: notify.sh <event_type> <message> [priority]
# Exit 0 always — never block Claude Code

set -euo pipefail

EVENT_TYPE="${1:-unknown}"
MESSAGE="${2:-No message}"
PRIORITY="${3:-low}"

TIMESTAMP=$(date '+%H:%M:%S')
CWD=$(basename "$(pwd)")
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

# --- Channel 1: WeChat via AstrBot API (supports proactive push) ---
ASTRBOT_URL="http://127.0.0.1:18080"
ASTRBOT_HOST="astrbot.home"
ASTRBOT_API_KEY="abk_6Jz0DYYXfD9qU9TfYkef0MFAKWQoooVIveJCGmr-CgM"
WECHAT_UMO="MytsicE-wechat:FriendMessage:o9cq802hP0yPsg3rHerWNi-PUwvY@im.wechat"

ESCAPED_MSG=$(printf '%s' "$NOTIFY_TEXT" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')

no_proxy=127.0.0.1 curl -s -m 5 \
  -X POST \
  -H "Host: ${ASTRBOT_HOST}" \
  -H "Authorization: Bearer ${ASTRBOT_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"umo\":\"${WECHAT_UMO}\",\"message\":${ESCAPED_MSG}}" \
  "${ASTRBOT_URL}/api/v1/im/message" >/dev/null 2>&1 || true

# --- Channel 2: QQ via OpenClaw message send (supports proactive push) ---
OPENCLAW_CONTAINER="openclaw"
QQ_TARGET="6addb7a17f1b0ebd467cc91076e3fac9"

docker exec "$OPENCLAW_CONTAINER" openclaw message send \
  --channel qqbot \
  --target "$QQ_TARGET" \
  -m "$NOTIFY_TEXT" >/dev/null 2>&1 || true

exit 0
