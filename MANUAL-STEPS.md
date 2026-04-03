# notifyBot 手动操作清单

> 生成日期：2026-04-01
> 所有需要你亲手完成的操作，按优先级排序

---

## 0. 本地 DNS（前置条件）

Windows hosts 文件中缺少新服务的条目。WSL hosts 已由 Claude Code 添加。

**操作**：在 Windows 终端（管理员）执行以下 PowerShell 命令：

```powershell
Add-Content -Path "C:\Windows\System32\drivers\etc\hosts" -Value "`n127.0.0.1 astrbot.home`n127.0.0.1 astrbot-api.home`n127.0.0.1 obsidian-sync.home`n127.0.0.1 openclaw.home"
```

> 如果 WSL hosts 未自动同步，在 WSL 终端执行：
> ```bash
> echo '127.0.0.1 astrbot.home
> 127.0.0.1 astrbot-api.home
> 127.0.0.1 obsidian-sync.home
> 127.0.0.1 openclaw.home' | sudo tee -a /etc/hosts
> ```

**验证**（浏览器或 PowerShell）：
- `http://astrbot.home:18080` → AstrBot WebUI 登录页
- `http://openclaw.home:18080` → OpenClaw Dashboard
- `http://obsidian-sync.home:18080` → CouchDB 欢迎页（JSON）

---

## 1. OpenClaw 配置 LLM

当前状态：OpenClaw 运行正常但无 LLM 配置，所有请求都报错 "No API key found for provider anthropic"。

### 1A：配置 Ollama 作为 LLM Provider

```bash
docker exec -it openclaw openclaw onboard \
  --non-interactive \
  --auth-choice ollama \
  --accept-risk
```

如果非交互模式有问题，使用交互模式：
```bash
docker exec -it openclaw openclaw onboard --wizard
```
交互向导中选择：
- Auth: `ollama`
- Ollama 地址会自动检测（同 Docker 网络 `http://ollama:11434`）
- 如果要求选模型，选 `qwen3.5:9b` 或 `frob/qwen3.5-instruct:9b`

### 1B：验证 LLM 可用

```bash
# TUI 模式测试对话
docker exec -it openclaw openclaw tui --message "你好，测试一下"

# 或查看模型状态
docker exec openclaw openclaw models status
```

### 1C：访问 OpenClaw Dashboard（Web UI）

Dashboard 需要 secure context（HTTPS 或 localhost），已配置端口直接映射。

**浏览器打开**：`http://localhost:18789`

> Gateway Token（如需认证）：`2a89be0c4330a11c276a16bc1cd4cac40d59c57aebc1a1e1`

### 1D：（可选）后续添加其他 LLM

等你决定好用 GLM / DeepSeek / 阿里百炼后：
```bash
# DeepSeek
docker exec -it openclaw openclaw onboard --auth-choice deepseek-api-key --deepseek-api-key <KEY>

# 阿里百炼（Model Studio China）
docker exec -it openclaw openclaw onboard --auth-choice modelstudio-api-key-cn --modelstudio-api-key-cn <KEY>

# 也可以通过 Dashboard 配置
```

---

## 2. AstrBot 配置

当前状态：运行正常，WebUI 在 6185 端口，默认账密 `astrbot/astrbot`。

### 2A：访问 WebUI

浏览器打开：`http://astrbot.home:18080`

### 2B：修改默认密码

登录后进入「系统设置」→ 修改管理员密码。

### 2C：配置 LLM Provider

进入「Provider 管理」→ 添加 Provider：
- 类型：`OpenAI Compatible` 或直接选 `Ollama`
- API Base URL：`http://ollama:11434`（容器内网地址）
- 模型：`qwen3.5:9b` 或 `frob/qwen3.5-instruct:9b`
- 设为默认 Provider

### 2D：配置微信接入

AstrBot 支持的微信相关适配器：
| 适配器 | 说明 | 适合场景 |
|--------|------|----------|
| `weixin_oc` | 微信个人号（开放云/协议） | 微信小号日常使用 |
| `weixin_official_account` | 微信公众号 | 需要公众号资质 |
| `wecom` | 企业微信 | 需要企业微信账号 |

**操作**：在 WebUI「平台管理」中添加微信适配器，按提示操作。个人号可能需要扫码登录。

### 2E：验证

- 微信发一条消息 → AstrBot 用 Ollama 回复
- 如果成功，说明 AstrBot 微信链路通了

---

## 3. Cloudflare Tunnel 路由

当前状态：cloudflared 使用 Tunnel Token 模式，路由在 Cloudflare Zero Trust Dashboard 中配置。

### 3A：添加 obsidian-sync 路由

1. 登录 [Cloudflare Zero Trust](https://one.dash.cloudflare.com/)
2. 进入 Networks → Tunnels → 选择你的 tunnel
3. 点击 Configure → Public Hostname
4. 添加新路由：

| 字段 | 值 |
|------|-----|
| Subdomain | `obsidian-sync` |
| Domain | `mysticee.online` |
| Type | `HTTP` |
| URL | `nginx:80` |

> 因为 cloudflared 和 nginx 在同一个 Docker proxy 网络中，所以 origin 填 `nginx:80`

### 3B：Cloudflare Access（CouchDB）

**推荐做法**：不加 Cloudflare Access。原因：
- Obsidian LiveSync 插件无法走 OTP 认证流程
- CouchDB 自身有用户名密码认证（`obsidian` / 已配密码），足够安全

如果担心安全，可以在 Cloudflare Tunnel 的 Public Hostname 设置中勾选 **"Additional application settings → Access → Protect with Access"**，但需要给 LiveSync 配 Service Token bypass。

---

## 4. Obsidian LiveSync 配置

### 4A：电脑端（Windows / Mac）

1. Obsidian → Settings → Community plugins → 搜索 `Self-hosted LiveSync`
2. 安装并启用
3. 配置连接：
   - URI: `https://obsidian-sync.mysticee.online`
   - Username: `obsidian`
   - Password: `8e8b77f1d72f8fefe0205c7f87346aa4`
   - Database name: `obsidiandb`
4. 选择同步模式：`LiveSync`（实时）或 `Periodic`（定时）
5. 首次选择「Setup as the first device」初始化远端数据库结构

> 后续设备选 "Setup as a secondary or subsequent device"

### 4B：手机端（iPhone / Android）

同上操作。Obsidian 移动端同样支持社区插件。

### 4C：华为平板（HarmonyOS）

1. 通过卓易通安装 Android 版 Obsidian
2. 同上配置 LiveSync 插件

### 4D：Vault 目录结构（已创建）

```
/mnt/f/Obsidian/vault/
├── 00-Inbox/       ← OpenClaw 写入此处
├── 01-Daily/       ← 每日笔记
├── 02-Projects/    ← 项目笔记
├── 03-Areas/       ← 持续关注领域
├── 04-Resources/   ← 参考资料
├── 05-Archive/     ← 归档
├── 07-Templates/   ← 模板
└── Attachments/    ← 附件
```

### 4E：验证

在一台设备创建笔记 → 其他设备应在数秒内看到同步。

---

## 5. MS To Do — Azure 应用注册

这是 Phase 4（待办联动）的前置准备，可以提前做。

### 5A：注册 Azure 应用

1. 登录 [Azure Portal](https://portal.azure.com/)
2. 进入 Microsoft Entra ID（原 Azure AD）→ App registrations → New registration
3. 填写：
   - Name: `notifyBot-todo`
   - Supported account types: `Accounts in any organizational directory and personal Microsoft accounts`（个人账户选这个）
   - Redirect URI: 类型选 `Web` → `http://localhost:8400/callback`
4. 点击 Register

### 5B：配置 API 权限

1. 进入刚创建的应用 → API permissions → Add a permission
2. 选择 Microsoft Graph → Delegated permissions
3. 添加以下权限：
   - `Tasks.ReadWrite` — 读写待办
   - `User.Read` — 读取用户信息
4. 点击 Grant admin consent（如果是个人账户，授权时会自动同意）

### 5C：创建客户端密钥

1. 进入 Certificates & secrets → New client secret
2. Description: `notifyBot`
3. Expires: 选 24 months
4. **立即复制 secret value**（只显示一次）

### 5D：记录关键信息

你需要保存以下 4 个值（建议存入 Vaultwarden）：

| 项目 | 位置 |
|------|------|
| Application (client) ID | 应用概览页 |
| Directory (tenant) ID | 应用概览页 |
| Client Secret | 5C 中复制的值 |
| Redirect URI | `http://localhost:8400/callback` |

### 5E：完成 OAuth 授权获取 Refresh Token

这一步需要 OpenClaw 的 MS Graph Tool/Skill 来完成，属于 Phase 4 的实施内容。提前注册好应用即可。

授权流程概要：
1. 浏览器打开：
   ```
   https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize?client_id={client_id}&response_type=code&redirect_uri=http://localhost:8400/callback&scope=Tasks.ReadWrite+User.Read+offline_access
   ```
2. 登录微软账号并同意授权
3. 获取回调 URL 中的 `code` 参数
4. 用 code 换取 access_token + refresh_token
5. 将 refresh_token 持久化存储（Vaultwarden 或 OpenClaw secrets）

---

## 操作顺序建议

```
步骤 0（hosts）      ← 5 分钟，一条 PowerShell 命令
  ↓
步骤 1A~1C（OpenClaw）← 配置 Ollama + 验证 Dashboard
  ↓
步骤 2A~2E（AstrBot） ← 可与步骤 1 并行
  ↓
步骤 3A（Tunnel）     ← 可与上面并行
  ↓
步骤 4A~4E（Obsidian） ← 需要步骤 3A 完成
  ↓
步骤 5A~5D（Azure）   ← 独立，随时可做
```

**最小可用路径**：0 → 1A → 2A~2E，完成这三步后微信就能用了。

---

## 当前各服务状态快照

| 服务 | 容器 | 状态 | 备注 |
|------|------|------|------|
| OpenClaw | openclaw | ✅ Running (healthy) | 缺 LLM 配置，Dashboard：`http://localhost:18789` |
| AstrBot | astrbot | ✅ Running | 默认账密未改，LLM 未配 |
| MemOS API | memos-api | ✅ Running | 待 OpenClaw 集成 |
| Neo4j | memos-neo4j | ✅ Running (healthy) | — |
| Qdrant | memos-qdrant | ✅ Running | — |
| CouchDB | obsidian-couchdb | ✅ Running | obsidiandb 已创建 |
| Nginx | nginx | ✅ Running | astrbot.conf + obsidian-sync.conf + openclaw.conf |
| Cloudflared | cloudflared | ✅ Running | 需添加 obsidian-sync 路由 |
| Ollama | ollama | ✅ Running | qwen3.5:9b 等 14 个模型已就绪 |
| AnythingLLM | anythingllm | ✅ Running (healthy) | — |
| Vaultwarden | vaultwarden | ✅ Running (healthy) | — |

---

## Phase 4-6 依赖关系

| Phase | 前置条件 | 可以独立开始吗 |
|-------|---------|:---:|
| Phase 4（待办联动） | OpenClaw LLM 可用 + Azure 应用注册完成 | 5A~5D 可提前做 |
| Phase 5（Claude Code 监控） | AstrBot 微信通了 | ✅ Hooks 脚本已写好 |
| Phase 6（系统管理） | OpenClaw LLM 可用 + 微信通了 | 白名单脚本已部署 |

不需要全部完成才开始下一阶段。**最大阻塞项是 OpenClaw 的 LLM 配置（步骤 1A）。**
