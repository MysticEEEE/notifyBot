#!/usr/bin/env python3
"""
MS To Do Token 自动刷新脚本

用 refresh_token 换取新的 access_token + refresh_token。
每次刷新后 refresh_token 的 90 天有效期重置，实现永久续期。

用法:
  # 方式一：环境变量
  export MS_TODO_CLIENT_SECRET='你的密钥'
  python3 scripts/ms-todo-refresh.py

  # 方式二：命令行参数
  python3 scripts/ms-todo-refresh.py --secret '你的密钥'

  # cron 定时（每 50 分钟刷新一次）:
  */50 * * * * cd /home/mystice/Project/plans/notifyBot && MS_TODO_CLIENT_SECRET='...' python3 scripts/ms-todo-refresh.py >> /tmp/ms-todo-refresh.log 2>&1
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

CLIENT_ID = "d4568fde-6ea9-4c17-a090-8c10d3127780"
TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
SCOPES = "Tasks.ReadWrite User.Read offline_access"
TOKENS_FILE = Path(__file__).parent / ".ms-todo-tokens.json"


def get_client_secret():
    parser = argparse.ArgumentParser(description="MS To Do Token 刷新")
    parser.add_argument("--secret", help="Azure 应用的 Client Secret")
    args = parser.parse_args()
    secret = os.environ.get("MS_TODO_CLIENT_SECRET") or args.secret
    if not secret:
        print(f"[{datetime.now().isoformat()}] [错误] 未提供 Client Secret", file=sys.stderr)
        sys.exit(1)
    return secret


def load_tokens():
    if not TOKENS_FILE.exists():
        print(f"[{datetime.now().isoformat()}] [错误] Token 文件不存在: {TOKENS_FILE}", file=sys.stderr)
        print("请先运行 ms-todo-oauth.py 完成初始授权", file=sys.stderr)
        sys.exit(1)
    with open(TOKENS_FILE) as f:
        return json.load(f)


def refresh_tokens(refresh_token, client_secret):
    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "scope": SCOPES,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "client_secret": client_secret,
    }).encode()

    req = urllib.request.Request(
        TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"[{datetime.now().isoformat()}] [错误] 刷新失败 (HTTP {e.code})", file=sys.stderr)
        try:
            err = json.loads(error_body)
            print(f"  {err.get('error', 'unknown')}: {err.get('error_description', 'N/A')}", file=sys.stderr)
        except json.JSONDecodeError:
            print(f"  {error_body[:200]}", file=sys.stderr)
        sys.exit(1)


def save_tokens(token_response):
    now = datetime.now()
    expires_in = token_response.get("expires_in", 3600)
    expires_at = now + timedelta(seconds=expires_in)

    tokens = {
        "access_token": token_response["access_token"],
        "refresh_token": token_response.get("refresh_token", ""),
        "token_type": token_response.get("token_type", "Bearer"),
        "scope": token_response.get("scope", ""),
        "expires_in": expires_in,
        "expires_at": expires_at.isoformat(),
        "obtained_at": now.isoformat(),
    }

    # 原子写入：先写临时文件，再 rename
    tmp_file = TOKENS_FILE.with_suffix(".tmp")
    with open(tmp_file, "w") as f:
        json.dump(tokens, f, indent=2, ensure_ascii=False)
    os.chmod(tmp_file, 0o600)
    os.replace(tmp_file, TOKENS_FILE)

    return tokens


def main():
    client_secret = get_client_secret()
    current = load_tokens()

    refresh_token = current.get("refresh_token")
    if not refresh_token:
        print(f"[{datetime.now().isoformat()}] [错误] Token 文件中没有 refresh_token", file=sys.stderr)
        sys.exit(1)

    # 检查是否还在有效期内（留 5 分钟缓冲）
    expires_at = current.get("expires_at", "")
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at)
            remaining = (exp - datetime.now()).total_seconds()
            if remaining > 300:  # 还有 5 分钟以上
                print(f"[{datetime.now().isoformat()}] Token 仍有效（剩余 {int(remaining/60)} 分钟），跳过刷新")
                return
        except ValueError:
            pass

    print(f"[{datetime.now().isoformat()}] 正在刷新 token...")
    token_response = refresh_tokens(refresh_token, client_secret)
    tokens = save_tokens(token_response)

    expires_in = tokens["expires_in"]
    print(f"[{datetime.now().isoformat()}] 刷新成功！新 token 有效期 {expires_in // 60} 分钟，过期时间 {tokens['expires_at']}")

    if tokens["refresh_token"]:
        print(f"[{datetime.now().isoformat()}] Refresh token 已更新（90 天有效期重置）")


if __name__ == "__main__":
    main()
