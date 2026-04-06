#!/bin/bash
# Claude Code notification hook
# Sends to QQ (reliable, always works) + WeChat (works after user sends a message)
# Exit 0 always — never block Claude Code

set -euo pipefail

EVENT_TYPE="${1:-unknown}"
MESSAGE="${2:-No message}"
PRIORITY="${3:-low}"

TIMESTAMP=$(date '+%H:%M:%S')
CWD=$(basename "$(pwd)")
SESSION_NAME="${CLAUDE_SESSION_NAME:-${CWD}}"

case "$EVENT_TYPE" in
  approval_needed) ICON="🔔" ;;
  task_complete)   ICON="✅" ;;
  timeout)         ICON="⏰" ;;
  *)               ICON="📋" ;;
esac

NOTIFY_TEXT="${ICON} [Claude Code] ${MESSAGE}
📂 ${SESSION_NAME} | ⏱ ${TIMESTAMP}"

OPENCLAW_CONTAINER="openclaw"

# --- QQ Bot (reliable proactive push) ---
QQ_TARGET="6addb7a17f1b0ebd467cc91076e3fac9"
docker exec "$OPENCLAW_CONTAINER" openclaw message send \
  --channel qqbot \
  --target "$QQ_TARGET" \
  -m "$NOTIFY_TEXT" >/dev/null 2>&1 || true

# --- WeChat ClawBot (works when contextToken is fresh) ---
WEIXIN_TARGET="o9cq802hP0yPsg3rHerWNi-PUwvY@im.wechat"
docker exec "$OPENCLAW_CONTAINER" openclaw message send \
  --channel openclaw-weixin \
  --target "$WEIXIN_TARGET" \
  -m "$NOTIFY_TEXT" >/dev/null 2>&1 || true

exit 0
