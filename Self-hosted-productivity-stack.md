# 自托管生产力系统部署指南

> 本文档用于指导 Claude Code 完成整个自托管生产力系统的部署与集成。  
> 最后更新：2026-03-31

---

## 一、项目概述

### 1.1 目标

构建一套完整的自托管生产力系统，将个人知识管理、AI 研究、团队协作、待办管理打通为统一工作流。

### 1.2 核心原则

- 数据自主可控，优先本地存储和自托管服务
- 各工具各司其职，通过 AstrBot / OpenClaw 作为胶水层串联
- Docker Compose 分栈部署，每个功能域独立管理
- 所有外部访问通过 Nginx 反向代理 + Cloudflare Tunnel 暴露，统一 HTTPS

### 1.3 用户环境

- 平台：电脑（主力）、手机、华为平板（HarmonyOS 6，通过卓易通运行 Android 应用）
- 团队规模：3-5 人小团队
- 团队协作平台：飞书（免费版）

---

## 二、系统架构

### 2.1 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户触达层                                │
├──────────┬──────────┬──────────┬──────────┬─────────────────────┤
│  飞书     │  微信/QQ  │  Telegram │  WebUI   │  Obsidian 多端     │
└────┬─────┴────┬─────┴────┬─────┴────┬─────┴──────────┬──────────┘
     │          │          │          │                │
┌────▼──────────▼──────────▼──────────▼────┐   ┌──────▼──────────┐
│         Bot / Agent 层                    │   │    同步层        │
│  ┌─────────────┐  ┌──────────────────┐   │   │  ┌────────────┐ │
│  │   AstrBot   │  │    OpenClaw      │   │   │  │  CouchDB   │ │
│  │  (IM Bot)   │  │  (AI Agent)      │   │   │  │ (LiveSync) │ │
│  └──────┬──────┘  └───────┬──────────┘   │   │  └────────────┘ │
└─────────┼─────────────────┼──────────────┘   └─────────────────┘
          │                 │
┌─────────▼─────────────────▼──────────────────────────────────────┐
│                        AI / 知识层                                │
│  ┌──────────┐  ┌───────────────┐  ┌────────────────────────────┐ │
│  │  Ollama  │  │ AnythingLLM   │  │    Open Notebook           │ │
│  │ (本地LLM) │  │ (知识库/RAG)  │  │  (AI研究 + SurrealDB)     │ │
│  └──────────┘  └───────────────┘  └────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
          │
┌─────────▼────────────────────────────────────────────────────────┐
│                       存储 / 笔记层                               │
│  ┌──────────────┐  ┌───────────────┐  ┌────────────────────────┐ │
│  │   Obsidian   │  │ Microsoft Todo│  │    Vaultwarden         │ │
│  │  (知识中枢)   │  │  (待办管理)   │  │   (密码管理)            │ │
│  └──────────────┘  └───────────────┘  └────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
          │
┌─────────▼────────────────────────────────────────────────────────┐
│                       基础设施层                                   │
│  ┌──────────┐  ┌───────────────┐                                 │
│  │  Nginx   │  │  Cloudflared  │                                 │
│  │ (反代)    │  │  (隧道)       │                                 │
│  └──────────┘  └───────────────┘                                 │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流向

```
飞书会议/消息
  → AstrBot/OpenClaw (飞书机器人)
    → Obsidian vault (Markdown 笔记)
      → CouchDB LiveSync (跨设备同步)
        → 手机/平板/电脑 上的 Obsidian

日常想法/待办（通过 IM 发送）
  → AstrBot/OpenClaw
    ├→ "笔记类" → 写入 Obsidian vault
    └→ "待办类" → Microsoft Todo (Graph API)

深度研究
  → Open Notebook (上传资料 → AI分析)
  → AnythingLLM (RAG 知识库查询)
  → 研究结果 → 手动或自动存入 Obsidian
```

---

## 三、现有服务（已部署）

以下服务已在 Docker 中运行，不需要重新部署。

### 3.1 栈：ai

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| anythingllm | `mintplexlabs/anythingllm:latest` | 3001:3001 | RAG 知识库 |
| ollama | `ollama/ollama:latest` | (内部) | 本地 LLM 推理 |

### 3.2 栈：infrastructure

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| nginx | `nginx:alpine` | 18843:443 | 反向代理 |
| cloudflared | `cloudflare/cloudflared:latest` | - | Cloudflare Tunnel |

### 3.3 栈：vaultwarden

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| vaultwarden | `vaultwarden/server:latest` | (内部) | 密码管理 |

### 3.4 栈：notebook

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| surrealdb-1 | `surrealdb/surrealdb:v2` | (内部) | Open Notebook 数据库 |
| open_notebook-1 | `lfnovo/open_notebook:v1-latest` | (内部) | AI 研究平台 |

---

## 四、新增服务部署计划

按优先级顺序部署，每完成一步验证后再进行下一步。

### 4.1 第一步：栈 `sync` — Obsidian 跨设备同步

**目的：** 部署 CouchDB，配合 Obsidian Self-hosted LiveSync 插件实现跨设备笔记同步。

#### docker-compose.yml

```yaml
version: "3.8"

services:
  couchdb:
    image: couchdb:3.3.3
    container_name: obsidian-couchdb
    environment:
      - COUCHDB_USER=${COUCHDB_USER}
      - COUCHDB_PASSWORD=${COUCHDB_PASSWORD}
    volumes:
      - ./couchdb-data:/opt/couchdb/data
      - ./couchdb-etc:/opt/couchdb/etc/local.d
    ports:
      - "5984:5984"
    restart: unless-stopped

networks:
  default:
    external: true
    name: shared
```

#### .env

```env
COUCHDB_USER=obsidian
COUCHDB_PASSWORD=<生成强密码>
```

#### 部署后配置步骤

1. 访问 `http://<服务器IP>:5984/_utils`，使用 .env 中的凭据登录
2. 点击 "Setup" → "Configure as Single Node"
3. 在 "Databases" 中创建数据库，名称如 `obsidiandb`
4. 在 Nginx 配置中添加反向代理：
   ```nginx
   server {
       listen 443 ssl;
       server_name obsidian-sync.<你的域名>;

       location / {
           proxy_pass http://obsidian-couchdb:5984;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;

           # CORS for Obsidian
           add_header Access-Control-Allow-Origin "app://obsidian.md" always;
           add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
           add_header Access-Control-Allow-Headers "Content-Type, Authorization" always;
           add_header Access-Control-Allow-Credentials true always;
           add_header Access-Control-Max-Age 86400 always;

           if ($request_method = OPTIONS) {
               return 204;
           }
       }
   }
   ```
5. 在 Cloudflare Tunnel 中添加对应域名路由
6. 在 Obsidian（所有设备）中：
   - 安装 "Self-hosted LiveSync" 社区插件
   - 配置服务器地址：`https://obsidian-sync.<你的域名>`
   - 填入数据库名、用户名、密码
   - 可选：启用端到端加密
   - 选择 "LiveSync" 同步模式
   - 启用 "Customisation Sync" 以同步设置、主题、插件

#### 验证标准

- [ ] CouchDB Web UI 可正常访问
- [ ] 通过 HTTPS 域名可访问 CouchDB
- [ ] 电脑端 Obsidian LiveSync 连接成功
- [ ] 手机端 Obsidian LiveSync 连接成功
- [ ] 在一台设备新建笔记，另一台设备秒级同步
- [ ] 设置和插件通过 Customisation Sync 同步

---

### 4.2 第二步：栈 `bot` — AstrBot 聊天机器人

**目的：** 部署 AstrBot，接入飞书机器人，实现"发消息 → 记笔记 / 创建待办"的基础链路。

#### docker-compose.yml

```yaml
version: "3.8"

services:
  astrbot:
    image: astrbotdevs/astrbot:latest
    container_name: astrbot
    volumes:
      - ./astrbot-data:/AstrBot/data
    ports:
      - "6185:6185"   # WebUI
      - "6186:6186"   # API
    restart: unless-stopped

networks:
  default:
    external: true
    name: shared
```

#### 部署后配置步骤

1. 访问 AstrBot WebUI `http://<服务器IP>:6185` 完成初始化
2. 配置 LLM 提供商：
   - 类型：OpenAI Compatible
   - API 地址：`http://ollama:11434/v1`（如果在 shared 网络中）或 `http://<宿主IP>:11434/v1`
   - 选择模型（根据 Ollama 已拉取的模型）
3. 接入飞书：
   - 在飞书开放平台创建企业自建应用
   - 获取 App ID、App Secret
   - 配置事件订阅 URL：`https://astrbot.<你的域名>/feishu/callback`
   - 在 AstrBot WebUI 中配置飞书平台凭据
4. 在 Nginx 中添加 AstrBot 的反向代理配置
5. 在 Cloudflare Tunnel 中添加对应路由

#### 飞书机器人能力配置

在飞书开放平台为应用添加以下权限：
- 接收消息 (im:message)
- 发送消息 (im:message:send)
- 获取群信息 (im:chat:readonly)

#### AstrBot 插件安装

通过 WebUI 插件市场安装：
- MCP 支持插件（用于后续接入 Obsidian MCP Server）
- 其他按需安装

#### 验证标准

- [ ] AstrBot WebUI 可正常访问
- [ ] AstrBot 成功连接 Ollama 模型
- [ ] 飞书机器人在群内/私聊中可正常回复
- [ ] 基础 AI 对话功能正常

---

### 4.3 第三步：栈 `agent` — OpenClaw AI 智能体

**目的：** 部署 OpenClaw，实现更复杂的 Agent 自动化任务，如多步骤操作、文件读写、定时任务。

#### docker-compose.yml

```yaml
version: "3.8"

services:
  openclaw:
    image: openclaw/openclaw:latest
    container_name: openclaw
    volumes:
      - ./openclaw-data:/root/.openclaw
      - /path/to/obsidian-vault:/workspace/obsidian-vault  # 挂载 Obsidian vault
    ports:
      - "18789:18789"
    environment:
      - NODE_ENV=production
    restart: unless-stopped

networks:
  default:
    external: true
    name: shared
```

> **注意：** OpenClaw 的 Docker 部署可能需要参考最新官方文档或中文社区版 (jiulingyun/openclaw-cn) 的 Docker 配置，因为项目迭代很快。部署前请先检查：
> - 官方 Docker 镜像是否为最新
> - 是否需要使用中文社区版镜像以获得飞书/钉钉原生支持
> - openclaw-china 插件集合是否需要额外挂载

#### 部署后配置步骤

1. 进入容器执行初始化向导：
   ```bash
   docker exec -it openclaw openclaw onboard
   ```
2. 配置 LLM Provider：
   - 主模型：可选 Claude / GPT / 其他云端模型
   - Fallback 模型：本地 Ollama（`http://ollama:11434`）
3. 接入飞书渠道（通过 openclaw-china 插件或内置支持）
4. 配置 Skills：
   - 文件系统访问（读写 Obsidian vault）
   - Web 搜索
   - 代码执行（沙箱模式）
5. Nginx 反向代理 + Cloudflare Tunnel 暴露 Dashboard

#### 验证标准

- [ ] OpenClaw Dashboard 可访问
- [ ] 通过飞书/Telegram 可与 OpenClaw Agent 对话
- [ ] Agent 可成功读取挂载的 Obsidian vault 中的文件
- [ ] Agent 可成功在 vault 中创建新的 Markdown 笔记

---

### 4.4 第四步：集成与工作流打通

**目的：** 将所有服务串联起来，实现完整的自动化工作流。

#### 4.4.1 Obsidian MCP Server（连接 AstrBot → Obsidian）

在服务器上部署 Obsidian MCP Server：

```bash
# 在宿主机或单独容器中
npx obsidian-mcp-server
```

需要在 Obsidian 中安装并启用 "Local REST API" 插件，配置 API Key。

AstrBot 通过 MCP 协议连接此 Server，即可实现：
- 读取笔记内容
- 创建/更新笔记
- 搜索笔记
- 管理标签和 frontmatter

#### 4.4.2 Microsoft Todo 集成

通过 Microsoft Graph API 实现待办管理：

1. 在 Azure AD 注册应用，获取：
   - Client ID
   - Client Secret
   - Tenant ID
2. 授权范围：`Tasks.ReadWrite`
3. API 端点：`https://graph.microsoft.com/v1.0/me/todo/lists/{listId}/tasks`

可在 AstrBot 中编写自定义插件，或在 OpenClaw 中配置为 Skill/Tool：
- 创建待办：POST 请求
- 查询待办：GET 请求
- 完成待办：PATCH 请求

#### 4.4.3 飞书会议纪要 → Obsidian

通过飞书 Webhook / 事件订阅：
1. 飞书会议结束后触发事件
2. AstrBot/OpenClaw 接收事件，调用飞书 API 获取会议纪要
3. 格式化为 Markdown，写入 Obsidian vault 的 `会议记录/` 文件夹
4. CouchDB LiveSync 自动同步到所有设备

#### 4.4.4 消息路由逻辑

AstrBot/OpenClaw 接收消息后的处理逻辑：

```
收到消息
  │
  ├─ 包含 "待办"/"TODO"/"提醒" 关键词
  │   → 解析内容 → Microsoft Todo API → 创建待办
  │   → 同时在 Obsidian daily note 中记录
  │
  ├─ 包含 "记"/"笔记"/"记录" 关键词
  │   → 解析内容 → Obsidian MCP → 写入指定笔记或 inbox
  │
  ├─ 包含 "研究"/"分析" 关键词
  │   → 调用 Ollama 深度分析 → 结果写入 Obsidian
  │
  └─ 默认：AI 对话
      → Ollama 回复
```

---

## 五、Obsidian 配置

### 5.1 从 OneNote 迁移

使用 Obsidian 官方 Importer 插件：

1. 在 Obsidian 中安装 "Importer" 社区插件
2. 选择 "Microsoft OneNote" 作为来源
3. 登录 Microsoft 个人账号（注意：不支持工作/学校账号）
4. 选择要导入的笔记本和分区
5. 点击 Import

注意事项：
- 手绘内容会转换为 SVG 矢量图（质量很好）
- 大笔记本可能因 API 超时导致部分失败，建议逐个笔记本导入
- 导入后需要手动清理部分格式

### 5.2 推荐插件列表

| 插件 | 用途 |
|------|------|
| Self-hosted LiveSync | 跨设备同步（连接自部署 CouchDB） |
| Importer | OneNote 及其他来源笔记导入 |
| Tasks | 任务管理（截止日期、优先级、重复任务、查询过滤） |
| Excalidraw | 白板/手绘（iPad 上可配合手写笔使用） |
| Ink | 在段落间直接手写（手写笔支持） |
| Dataview | 数据库式查询笔记 |
| Kanban | 看板视图 |
| Local REST API | 提供 REST API 供外部工具（MCP Server）访问 vault |
| Templater | 高级模板引擎 |
| Calendar | 日历视图，配合 daily notes |
| Periodic Notes | 每日/每周/每月笔记管理 |

### 5.3 推荐 Vault 结构

```
obsidian-vault/
├── 00-Inbox/              # 快速收集，未整理的笔记
│   └── (AstrBot/OpenClaw 写入此处)
├── 01-Daily/              # 每日笔记
│   └── 2026-03-31.md
├── 02-Projects/           # 项目笔记
│   ├── Project-A/
│   └── Project-B/
├── 03-Areas/              # 持续关注的领域
│   ├── 工作/
│   ├── 学习/
│   └── 生活/
├── 04-Resources/          # 参考资料
│   ├── 从OneNote导入/
│   └── 研究/
├── 05-Archive/            # 归档
├── 06-Meetings/           # 会议记录（飞书纪要自动写入）
├── 07-Templates/          # 模板
│   ├── daily-note.md
│   ├── meeting-note.md
│   └── project-note.md
└── Attachments/           # 附件（图片、PDF 等）
```

### 5.4 华为平板（HarmonyOS 6）使用说明

- Obsidian 无鸿蒙原生版，需通过卓易通安装 Android 版
- 基础文字编辑和查看功能正常
- LiveSync 同步需要在系统设置中为卓易通/Obsidian 开启：
  - 自启动权限
  - 关联启动权限
  - 电池优化设为"不限制"
- 手写笔体验有限，建议：
  - 平板手写使用华为原生备忘录或其他鸿蒙原生应用
  - 手写内容导出 PDF 后放入 Obsidian vault 的 Attachments 文件夹
  - 通过 LiveSync 自动同步到其他设备
- 快速记录想法/待办：直接通过飞书/微信发给 AstrBot，完全绕过鸿蒙兼容性问题

---

## 六、飞书配置（团队协作）

### 6.1 为什么选飞书

- 文档协作体验最好，多维表格可做轻量项目管理
- 扁平化管理理念适合小团队
- 免费版对 3-5 人团队够用
- 会议支持 AI 纪要自动生成
- API 和 Webhook 开放度高，便于与 AstrBot/OpenClaw 集成

### 6.2 飞书免费版用于团队管理

- 即时沟通：群聊 + 话题，替代微信工作群
- 项目管理：多维表格创建项目看板/甘特图
- 文档协作：在线文档实时多人编辑
- 会议：视频会议 + AI 纪要
- 日历：团队日程管理，智能排期
- 审批：简单审批流程

### 6.3 飞书开放平台配置

为 AstrBot 和 OpenClaw 创建飞书应用：

1. 访问 https://open.feishu.cn 创建企业自建应用
2. 获取 App ID 和 App Secret
3. 配置权限：
   - `im:message` — 接收消息
   - `im:message:send` — 发送消息
   - `im:chat:readonly` — 读取群信息
   - `calendar:calendar:readonly` — 读取日历（可选）
   - `vc:meeting` — 会议相关（可选）
4. 配置事件订阅回调 URL
5. 发布应用并在团队中启用

---

## 七、Docker 网络配置

### 7.1 共享网络

创建一个共享的 Docker 外部网络，供需要互相通信的栈使用：

```bash
docker network create shared
```

### 7.2 各栈网络配置

需要加入 shared 网络的栈（需要访问 Ollama 或互相通信的服务）：

在对应的 docker-compose.yml 中添加：

```yaml
networks:
  default:
    external: true
    name: shared
```

需要加入 shared 网络的栈：
- `ai`（Ollama + AnythingLLM）— 提供 LLM 服务
- `bot`（AstrBot）— 需要调用 Ollama
- `agent`（OpenClaw）— 需要调用 Ollama
- `sync`（CouchDB）— 需要被 Nginx 代理访问

不需要加入 shared 网络的栈（保持独立即可）：
- `vaultwarden` — 独立密码管理
- `notebook` — 如果不需要被 AstrBot/OpenClaw 直接调用可保持独立

### 7.3 服务间访问地址

在 shared 网络中，各服务通过容器名互相访问：

| 源服务 | 目标服务 | 访问地址 |
|--------|----------|----------|
| AstrBot | Ollama | `http://ollama:11434` |
| OpenClaw | Ollama | `http://ollama:11434` |
| Nginx | CouchDB | `http://obsidian-couchdb:5984` |
| Nginx | AstrBot | `http://astrbot:6185` |
| Nginx | OpenClaw | `http://openclaw:18789` |

> **重要：** 修改已有栈的网络配置后需要重新创建容器（`docker compose down && docker compose up -d`），注意验证原有服务不受影响。

---

## 八、Nginx 反向代理配置

在现有 infrastructure 栈的 Nginx 配置中添加以下 server 块：

```nginx
# Obsidian LiveSync (CouchDB)
server {
    listen 443 ssl;
    server_name obsidian-sync.<域名>;
    
    # SSL 证书配置（根据现有配置调整）
    
    location / {
        proxy_pass http://obsidian-couchdb:5984;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS headers for Obsidian app
        add_header Access-Control-Allow-Origin "app://obsidian.md" always;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Content-Type, Authorization" always;
        add_header Access-Control-Allow-Credentials true always;
        add_header Access-Control-Max-Age 86400 always;
        
        if ($request_method = OPTIONS) {
            return 204;
        }
    }
}

# AstrBot WebUI
server {
    listen 443 ssl;
    server_name astrbot.<域名>;
    
    location / {
        proxy_pass http://astrbot:6185;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

# AstrBot API (飞书回调等)
server {
    listen 443 ssl;
    server_name astrbot-api.<域名>;
    
    location / {
        proxy_pass http://astrbot:6186;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# OpenClaw Dashboard
server {
    listen 443 ssl;
    server_name openclaw.<域名>;
    
    location / {
        proxy_pass http://openclaw:18789;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

同时在 Cloudflare Tunnel 配置中添加对应的域名路由。

---

## 九、Microsoft Todo 集成

### 9.1 Azure AD 应用注册

1. 访问 https://portal.azure.com → Azure Active Directory → App registrations
2. 新建注册：
   - 名称：`Self-Hosted-Assistant`
   - 支持的账户类型：个人 Microsoft 账户
   - 重定向 URI：`http://localhost:3000/callback`（用于初次授权）
3. 记录：
   - Application (client) ID
   - Directory (tenant) ID
4. 在 "Certificates & secrets" 中创建 Client Secret
5. 在 "API permissions" 中添加：
   - `Tasks.ReadWrite` — 读写 Todo 任务
   - `User.Read` — 基础用户信息

### 9.2 API 调用示例

```bash
# 创建待办
curl -X POST "https://graph.microsoft.com/v1.0/me/todo/lists/{listId}/tasks" \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "下周三交报告",
    "dueDateTime": {
      "dateTime": "2026-04-07T17:00:00",
      "timeZone": "Asia/Shanghai"
    }
  }'
```

### 9.3 与 AstrBot/OpenClaw 集成

- AstrBot：编写自定义插件调用 Graph API，或通过 MCP 工具
- OpenClaw：配置为 Agent Tool/Skill，Agent 可自主决定何时创建待办

---

## 十、部署检查清单

### 阶段一：基础同步

- [ ] 创建 shared Docker 网络
- [ ] 修改 ai 栈加入 shared 网络，验证 Ollama/AnythingLLM 正常
- [ ] 部署 sync 栈（CouchDB）
- [ ] 配置 CouchDB 单节点 + 创建数据库
- [ ] Nginx 添加 CouchDB 反向代理
- [ ] Cloudflare Tunnel 添加路由
- [ ] 电脑端 Obsidian 安装 LiveSync 并连接
- [ ] 手机端 Obsidian 安装 LiveSync 并连接
- [ ] 华为平板通过卓易通安装 Obsidian + LiveSync
- [ ] 验证多设备同步正常

### 阶段二：OneNote 迁移

- [ ] Obsidian 安装 Importer 插件
- [ ] 逐个笔记本从 OneNote 导入
- [ ] 检查手绘 SVG 转换质量
- [ ] 整理导入的笔记到 vault 目录结构
- [ ] 安装推荐插件（Tasks、Excalidraw、Dataview 等）

### 阶段三：AstrBot 部署

- [ ] 部署 bot 栈
- [ ] AstrBot 连接 Ollama
- [ ] 飞书开放平台创建应用
- [ ] AstrBot 接入飞书
- [ ] Nginx + Cloudflare Tunnel 配置
- [ ] 验证飞书消息收发正常

### 阶段四：OpenClaw 部署

- [ ] 部署 agent 栈
- [ ] OpenClaw 初始化配置
- [ ] 连接 LLM（云端 + Ollama fallback）
- [ ] 接入飞书渠道
- [ ] 挂载 Obsidian vault 并验证读写
- [ ] Nginx + Cloudflare Tunnel 配置

### 阶段五：工作流集成

- [ ] Obsidian 安装 Local REST API 插件
- [ ] 部署 Obsidian MCP Server
- [ ] AstrBot 通过 MCP 连接 Obsidian
- [ ] Azure AD 注册应用获取 Microsoft Todo API 凭据
- [ ] AstrBot/OpenClaw 集成 Microsoft Todo
- [ ] 配置消息路由逻辑（笔记/待办自动分类）
- [ ] 飞书会议纪要 → Obsidian 自动写入
- [ ] 端到端验证：飞书发消息 → 笔记/待办创建 → 多设备同步

### 阶段六：团队上线

- [ ] 飞书团队空间配置
- [ ] 多维表格创建项目管理看板
- [ ] 机器人添加到团队群
- [ ] 团队成员培训（飞书 + 机器人使用方法）
- [ ] 制定团队工作流规范

---

## 十一、安全注意事项

1. **所有外部暴露的服务必须通过 HTTPS**（已有 Nginx + Cloudflare Tunnel 保障）
2. **CouchDB 启用端到端加密**（LiveSync 插件内配置）
3. **API 密钥和密码统一存入 Vaultwarden**
4. **定期备份：**
   - Obsidian vault（本地文件 + CouchDB 数据）
   - AstrBot 数据目录
   - OpenClaw 配置和工作区
   - CouchDB 数据库
5. **Docker volume 备份脚本**建议写成 cron job
6. **OpenClaw 的 exec 权限需谨慎配置**，避免给 Agent 过大的系统权限
7. **Microsoft Graph API 的 Token 定期刷新**，注意 refresh token 有效期

---

## 十二、故障排查

| 问题 | 排查方向 |
|------|----------|
| LiveSync 同步失败 | 检查 CouchDB 容器日志、CORS 配置、HTTPS 证书 |
| 飞书机器人无响应 | 检查事件订阅 URL 是否可达、AstrBot 日志、飞书应用是否已发布 |
| OpenClaw Agent 无法写入 vault | 检查 volume 挂载路径和权限、Agent 的文件系统 Skill 配置 |
| Ollama 跨栈访问超时 | 检查 shared 网络是否正确加入、容器名解析是否正常 |
| 华为平板同步异常 | 检查卓易通中 Obsidian 的后台保活设置、电池优化是否关闭 |
| Microsoft Todo 创建失败 | 检查 OAuth token 是否过期、Graph API 权限是否正确 |

---

## 附录 A：参考链接

- Obsidian Self-hosted LiveSync: https://github.com/vrtmrz/obsidian-livesync
- AstrBot: https://github.com/AstrBotDevs/AstrBot
- OpenClaw: https://github.com/openclaw/openclaw
- OpenClaw 中文社区版: https://github.com/jiulingyun/openclaw-cn
- OpenClaw China 插件: https://github.com/BytePioneer-AI/openclaw-china
- Open Notebook: https://github.com/lfnovo/open-notebook
- Obsidian Importer: https://github.com/obsidianmd/obsidian-importer
- Obsidian MCP Server: https://github.com/cyanheads/obsidian-mcp-server
- Microsoft Graph API (Todo): https://learn.microsoft.com/en-us/graph/api/resources/todo-overview
- 飞书开放平台: https://open.feishu.cn

## 附录 B：端口分配表

| 端口 | 服务 | 栈 |
|------|------|-----|
| 3001 | AnythingLLM | ai |
| 11434 | Ollama (内部) | ai |
| 18843 | Nginx (HTTPS) | infrastructure |
| 5984 | CouchDB | sync |
| 6185 | AstrBot WebUI | bot |
| 6186 | AstrBot API | bot |
| 18789 | OpenClaw | agent |