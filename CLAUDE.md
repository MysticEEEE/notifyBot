# notifyBot 项目规范

## 配置文件双向同步

本项目在 git 仓库中维护所有配置文件的副本。修改任何 Docker compose、nginx 或 executor 配置时，**必须同时更新两个位置**：

| 类型 | 部署位置（实际生效） | 仓库位置（git 管理） |
|------|---------------------|---------------------|
| Compose 文件 | `/mnt/f/Docker/compose/<服务名>/docker-compose.yml` | `compose/<服务名>/docker-compose.yml` |
| Nginx 配置 | `/mnt/f/Docker/nginx/conf.d/<服务名>.conf` | `nginx/<服务名>.conf` |
| Executor 脚本 | `/mnt/f/Docker/executor/` | `executor/` |
| Claude Code Hooks | `~/.claude/hooks/` | `hooks/` |
| MCP Server 脚本 | `/mnt/f/Docker/openclaw/config/mcp-servers/` | `mcp-servers/` |
| OpenClaw 插件 | Docker named volume `openclaw-extensions` | 不同步（通过 npm 安装） |

**规则**：
1. 先修改部署位置的文件，验证生效后，再同步到仓库位置
2. `.env` 文件包含密钥，**不同步**到仓库。仓库中只保留 `.env.example` 模板
3. `openclaw.json` 等运行时配置不纳入仓库（含 token）
4. OpenClaw 插件通过 `openclaw plugins install` 安装到 named volume，不在仓库中管理

## OpenClaw Dashboard 访问

OpenClaw Dashboard 需要 secure context，通过 `localhost` 直接访问：
- 地址：`http://localhost:18789`
- 端口映射：`127.0.0.1:18789:18789`（仅本机可访问）
- nginx 的 `openclaw.conf` 保留用于容器间内网通信

## MemOS 集成

OpenClaw 通过 MCP server 连接 MemOS API，提供以下工具：
- `memos_search` — 语义记忆检索
- `memos_add` — 添加记忆（文本或聊天消息）
- `memos_get_all` / `memos_get_memory` — 获取记忆列表
- `memos_delete` — 删除记忆
- `memos_feedback` — 记忆反馈（like/dislike）
- `memos_chat` — 基于记忆的增强对话

配置位于 `openclaw.json` 的 `mcp.servers.memos` 节点。MCP server 脚本：`mcp-servers/memos-mcp-server.js`。
默认 user_id: `openclaw`，API 地址: `http://memos-api:8000`（Docker 内网）。

## OpenClaw 通道配置

- **微信**：`@tencent-weixin/openclaw-weixin` 插件，QR 扫码登录
- **QQ Bot**：`@tencent-connect/openclaw-qqbot` 插件，AppID + AppSecret
- **Claude Code Hooks**：通过 `openclaw message send --channel openclaw-weixin` 推送通知到微信
