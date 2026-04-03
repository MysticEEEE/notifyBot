# notifyBot 项目规范

## 配置文件双向同步

本项目在 git 仓库中维护所有配置文件的副本。修改任何 Docker compose、nginx 或 executor 配置时，**必须同时更新两个位置**：

| 类型 | 部署位置（实际生效） | 仓库位置（git 管理） |
|------|---------------------|---------------------|
| Compose 文件 | `/mnt/f/Docker/compose/<服务名>/docker-compose.yml` | `compose/<服务名>/docker-compose.yml` |
| Nginx 配置 | `/mnt/f/Docker/nginx/conf.d/<服务名>.conf` | `nginx/<服务名>.conf` |
| Executor 脚本 | `/mnt/f/Docker/executor/` | `executor/` |
| Claude Code Hooks | `~/.claude/hooks/` | `hooks/` |

**规则**：
1. 先修改部署位置的文件，验证生效后，再同步到仓库位置
2. `.env` 文件包含密钥，**不同步**到仓库。仓库中只保留 `.env.example` 模板
3. `openclaw.json` 等运行时配置不纳入仓库（含 token）

## OpenClaw Dashboard 访问

OpenClaw Dashboard 需要 secure context，通过 `localhost` 直接访问：
- 地址：`http://localhost:18789`
- 端口映射：`127.0.0.1:18789:18789`（仅本机可访问）
- nginx 的 `openclaw.conf` 保留用于容器间内网通信
