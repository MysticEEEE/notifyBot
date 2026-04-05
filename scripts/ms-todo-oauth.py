#!/usr/bin/env python3
"""
MS To Do OAuth 2.0 授权流程脚本

用法:
  1. 设置环境变量: export MS_TODO_CLIENT_SECRET='你的密钥'
  2. 运行: python3 scripts/ms-todo-oauth.py
  或者通过命令行参数传入:
     python3 scripts/ms-todo-oauth.py --secret '你的密钥'
"""

import argparse
import http.server
import json
import os
import sys
import threading
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# ── Azure 应用配置 ──────────────────────────────────────────────
CLIENT_ID = "d4568fde-6ea9-4c17-a090-8c10d3127780"
TENANT_ID = "778d9d0b-412a-4067-9454-6e2648cbe051"
REDIRECT_URI = "http://localhost:8400/callback"
SCOPES = "Tasks.ReadWrite User.Read offline_access"

# 个人 Microsoft 账户必须使用 /consumers 端点
AUTHORIZE_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"

TOKENS_FILE = Path(__file__).parent / ".ms-todo-tokens.json"

# ── 全局状态 ──────────────────────────────────────────────────
auth_code_received = threading.Event()
auth_code = None
auth_error = None


def get_client_secret():
    """从环境变量或命令行参数获取 Client Secret"""
    parser = argparse.ArgumentParser(description="MS To Do OAuth 授权")
    parser.add_argument("--secret", help="Azure 应用的 Client Secret")
    args = parser.parse_args()

    secret = os.environ.get("MS_TODO_CLIENT_SECRET") or args.secret

    if not secret:
        print("\n[错误] 未提供 Client Secret。请通过以下方式之一传入：")
        print("  方式一: export MS_TODO_CLIENT_SECRET='你的密钥'")
        print("  方式二: python3 scripts/ms-todo-oauth.py --secret '你的密钥'")
        sys.exit(1)

    return secret


def build_auth_url():
    """生成 OAuth 授权 URL"""
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "response_mode": "query",
        "scope": SCOPES,
        "prompt": "consent",
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    """处理 OAuth 回调的 HTTP 请求处理器"""

    def do_GET(self):
        global auth_code, auth_error

        parsed = urllib.parse.urlparse(self.path)

        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        params = urllib.parse.parse_qs(parsed.query)

        if "error" in params:
            auth_error = params.get("error_description", params["error"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                f"<html><body><h2>授权失败</h2><p>{auth_error}</p></body></html>".encode()
            )
            auth_code_received.set()
            return

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                "<html><body>"
                "<h2>授权成功！</h2>"
                "<p>已收到授权码，正在换取 token...</p>"
                "<p>你可以关闭此页面。</p>"
                "</body></html>".encode()
            )
            auth_code_received.set()
            return

        self.send_response(400)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("<html><body><h2>未收到授权码</h2></body></html>".encode())

    def log_message(self, format, *args):
        """静默 HTTP 日志"""
        pass


def exchange_code_for_tokens(code, client_secret):
    """用授权码换取 access_token 和 refresh_token"""
    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "scope": SCOPES,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
        "client_secret": client_secret,
    }).encode()

    req = urllib.request.Request(
        TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"\n[错误] Token 请求失败 (HTTP {e.code})")
        try:
            err = json.loads(error_body)
            print(f"  错误: {err.get('error', 'unknown')}")
            print(f"  描述: {err.get('error_description', 'N/A')}")
        except json.JSONDecodeError:
            print(f"  响应: {error_body}")
        sys.exit(1)


def save_tokens(token_response):
    """保存 tokens 到 JSON 文件"""
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

    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2, ensure_ascii=False)

    # 设置文件权限为仅当前用户可读写
    os.chmod(TOKENS_FILE, 0o600)

    return tokens


def main():
    client_secret = get_client_secret()

    auth_url = build_auth_url()

    print("=" * 60)
    print("  MS To Do OAuth 2.0 授权")
    print("=" * 60)
    print()
    print("[步骤 1] 请在浏览器中打开以下链接进行授权：")
    print()
    print(auth_url)
    print()
    print("[步骤 2] 登录 Microsoft 账号并同意授权")
    print("[步骤 3] 授权后浏览器会自动跳转，脚本将自动完成后续操作")
    print()
    print(f"正在 localhost:8400 等待回调...")
    print()

    # 启动本地 HTTP 服务器
    server = http.server.HTTPServer(("127.0.0.1", 8400), CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        # 等待授权回调
        auth_code_received.wait()
    except KeyboardInterrupt:
        print("\n\n已取消授权流程。")
        server.shutdown()
        sys.exit(0)

    server.shutdown()

    if auth_error:
        print(f"\n[错误] 授权失败: {auth_error}")
        sys.exit(1)

    if not auth_code:
        print("\n[错误] 未收到授权码")
        sys.exit(1)

    print("[进度] 已收到授权码，正在换取 tokens...")

    # 换取 tokens
    token_response = exchange_code_for_tokens(auth_code, client_secret)
    tokens = save_tokens(token_response)

    expires_in = tokens["expires_in"]
    hours = expires_in // 3600
    minutes = (expires_in % 3600) // 60

    print()
    print("=" * 60)
    print("  授权成功！")
    print("=" * 60)
    print()
    print(f"  Access Token 有效期: {hours} 小时 {minutes} 分钟")
    print(f"  Token 过期时间: {tokens['expires_at']}")
    print(f"  Refresh Token: {'已获取' if tokens['refresh_token'] else '未获取'}")
    print(f"  授权范围: {tokens['scope']}")
    print()
    print(f"  Tokens 已保存至: {TOKENS_FILE}")
    print()
    print("提示: Access Token 过期后可使用 Refresh Token 自动续期。")
    print()


if __name__ == "__main__":
    main()
