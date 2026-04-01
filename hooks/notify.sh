#!/bin/bash
# Claude Code notification hook - sends events to AstrBot
# Usage: notify.sh <event_type> <message> [priority]
# Exit 0 always — never block Claude Code

set -euo pipefail

EVENT_TYPE="${1:-unknown}"
MESSAGE="${2:-No message}"
PRIORITY="${3:-low}"
TIMEOUT=5

ASTRBOT_URL="http://127.0.0.1:18080"
ASTRBOT_HOST="astrbot-api.home"

TIMESTAMP=$(date -Iseconds)
HOSTNAME=$(hostname)
CWD=$(pwd)

PAYLOAD=$(cat <<EOF
{
  "event": "claude_code",
  "type": "${EVENT_TYPE}",
  "message": $(printf '%s' "$MESSAGE" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))'),
  "priority": "${PRIORITY}",
  "timestamp": "${TIMESTAMP}",
  "hostname": "${HOSTNAME}",
  "cwd": "${CWD}"
}
EOF
)

# Send notification, fail silently
no_proxy=127.0.0.1 curl -s -m "$TIMEOUT" \
  -X POST \
  -H "Host: ${ASTRBOT_HOST}" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  "${ASTRBOT_URL}/webhook/claude-code" >/dev/null 2>&1 || true

exit 0
