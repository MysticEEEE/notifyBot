#!/usr/bin/env python3
"""
host-executor.py — Unix socket daemon that executes whitelisted commands on behalf of
OpenClaw (running in Docker). Runs on the WSL2 host (NOT inside Docker).

Protocol:
  Request  (JSON): {"action": "<command-name>", "token": "<auth-token>"}
  Response (JSON): {"status": "ok"|"error", ...}

Special action "ping" skips token validation and returns available commands.
"""

import json
import logging
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path("/mnt/f/Docker/executor")
CONFIG_FILE = BASE_DIR / "commands.yaml"
LOG_FILE = BASE_DIR / "executor.log"
SOCK_PATH = "/tmp/host-exec.sock"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("host-executor")

# ---------------------------------------------------------------------------
# Config loading — prefer PyYAML, fall back to JSON
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Load commands.yaml (or commands.json as fallback)."""
    # Try YAML first
    try:
        import yaml  # type: ignore
        with open(CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f)
        log.info("Config loaded from %s (yaml)", CONFIG_FILE)
        return config
    except ImportError:
        log.warning("PyYAML not available — trying JSON fallback")
    except FileNotFoundError:
        pass  # will also try JSON

    # JSON fallback
    json_file = BASE_DIR / "commands.json"
    if json_file.exists():
        with open(json_file, "r") as f:
            config = json.load(f)
        log.info("Config loaded from %s (json fallback)", json_file)
        return config

    raise RuntimeError(
        f"No config file found. Expected {CONFIG_FILE} (yaml) or {json_file} (json)."
    )

# ---------------------------------------------------------------------------
# Auth token resolution
# ---------------------------------------------------------------------------

def resolve_token(config: dict) -> str:
    """Token priority: env var EXECUTOR_TOKEN > config file auth_token."""
    env_token = os.environ.get("EXECUTOR_TOKEN", "").strip()
    if env_token:
        log.info("Auth token sourced from environment variable EXECUTOR_TOKEN")
        return env_token
    cfg_token = str(config.get("auth_token", "")).strip()
    if cfg_token:
        log.info("Auth token sourced from config file")
        return cfg_token
    raise RuntimeError("No auth token configured (set EXECUTOR_TOKEN env var or auth_token in config)")

# ---------------------------------------------------------------------------
# Command execution helpers
# ---------------------------------------------------------------------------

def run_docker_command(cmd_cfg: dict) -> dict:
    """Execute a docker-type command (docker <action> <container>)."""
    action = cmd_cfg.get("action", "restart")
    container = cmd_cfg["container"]
    args = ["docker", action, container]
    log.info("Executing docker command: %s", " ".join(args))
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return {
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "exit_code": result.returncode,
    }


def run_host_command(cmd_cfg: dict) -> dict:
    """Execute an arbitrary whitelisted shell command."""
    command = cmd_cfg["command"]
    log.info("Executing host command: %s", command)
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return {
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "exit_code": result.returncode,
    }

# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

def handle_request(raw: bytes, config: dict, auth_token: str) -> dict:
    """Parse a raw JSON request and return a response dict."""
    # --- Parse JSON ---
    try:
        req = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        log.warning("Malformed request: %s", exc)
        return {"status": "error", "error": "invalid JSON"}

    action = str(req.get("action", "")).strip()
    token = str(req.get("token", "")).strip()

    log.info("Received request: action=%r", action)

    # --- Health check (no auth required) ---
    if action == "ping":
        commands = config.get("commands", {})
        available = [
            name for name, cfg in commands.items()
            if cfg.get("type") != "internal"
        ]
        return {"status": "ok", "available_commands": available}

    # --- Auth validation ---
    if token != auth_token:
        log.warning("Auth failure for action=%r (bad token)", action)
        return {"status": "error", "error": "unauthorized"}

    # --- Whitelist lookup ---
    commands = config.get("commands", {})
    if action not in commands:
        log.warning("Unknown action requested: %r", action)
        return {"status": "error", "error": f"unknown command: {action!r}"}

    cmd_cfg = commands[action]
    cmd_type = cmd_cfg.get("type", "host")

    # --- Execute ---
    try:
        if cmd_type == "internal":
            # internal commands (like ping) are handled above; shouldn't reach here
            return {"status": "error", "error": "internal command not directly callable"}
        elif cmd_type == "docker":
            result = run_docker_command(cmd_cfg)
        elif cmd_type == "host":
            result = run_host_command(cmd_cfg)
        else:
            log.error("Unknown command type %r for action %r", cmd_type, action)
            return {"status": "error", "error": f"unknown command type: {cmd_type!r}"}

        success = result["exit_code"] == 0
        log.info(
            "Action %r completed: exit_code=%d stdout=%r stderr=%r",
            action,
            result["exit_code"],
            result["stdout"][:200],
            result["stderr"][:200],
        )
        return {
            "status": "ok" if success else "error",
            "action": action,
            **result,
        }

    except subprocess.TimeoutExpired:
        log.error("Action %r timed out", action)
        return {"status": "error", "action": action, "error": "command timed out"}
    except Exception as exc:  # pylint: disable=broad-except
        log.exception("Unexpected error executing action %r: %s", action, exc)
        return {"status": "error", "action": action, "error": str(exc)}

# ---------------------------------------------------------------------------
# Connection handler (runs in its own thread per client)
# ---------------------------------------------------------------------------

def handle_connection(conn: socket.socket, addr, config: dict, auth_token: str) -> None:
    try:
        chunks = []
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
            # Simple framing: stop when we have a complete JSON object
            # (works for single-request/response protocol)
            try:
                json.loads(b"".join(chunks))
                break  # successfully parsed — done reading
            except json.JSONDecodeError:
                continue  # keep reading

        raw = b"".join(chunks)
        if not raw:
            return

        response = handle_request(raw, config, auth_token)
        conn.sendall(json.dumps(response).encode("utf-8"))
    except Exception as exc:  # pylint: disable=broad-except
        log.exception("Error in connection handler: %s", exc)
        try:
            conn.sendall(json.dumps({"status": "error", "error": str(exc)}).encode("utf-8"))
        except Exception:
            pass
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# Main server loop
# ---------------------------------------------------------------------------

def run_server(config: dict, auth_token: str) -> None:
    # Remove stale socket file
    sock_path = SOCK_PATH
    if os.path.exists(sock_path):
        os.unlink(sock_path)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(sock_path)
    os.chmod(sock_path, 0o660)
    server.listen(8)

    log.info("host-executor listening on %s", sock_path)
    log.info(
        "Available commands: %s",
        ", ".join(k for k, v in config.get("commands", {}).items() if v.get("type") != "internal"),
    )

    try:
        while True:
            conn, addr = server.accept()
            t = threading.Thread(
                target=handle_connection,
                args=(conn, addr, config, auth_token),
                daemon=True,
            )
            t.start()
    except KeyboardInterrupt:
        log.info("Shutting down host-executor")
    finally:
        server.close()
        if os.path.exists(sock_path):
            os.unlink(sock_path)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        config = load_config()
        auth_token = resolve_token(config)
        run_server(config, auth_token)
    except Exception as exc:
        log.critical("Fatal startup error: %s", exc)
        sys.exit(1)
