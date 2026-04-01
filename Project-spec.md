# 第二大脑 + AI 助理系统 — 项目规格文档

> 最后更新：2026-03-31

---

## 项目目标

构建一个基于本地部署的个人 AI 助理系统，解决以下痛点：
- 记忆力下降，临时想法/灵感/知识/人际关系容易丢失
- 待办事项管理分散，缺乏统一入口和好的展示方式
- Claude Code 运行时无法及时感知状态（需要审批、报错等）
- 跨设备笔记同步不便，知识分散在多个工具中
- 无法远程查看/管理本地服务和应用状态

核心理念：**数据与接入层解耦**，通信渠道可随时更换，本地数据永不丢失。

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                        用户触达层                              │
├──────────┬──────────┬──────────┬──────────┬──────────────────┤
│ 微信小号  │  WebUI   │ Obsidian │  飞书(预留)│   Claude Code   │
│ (主入口)  │          │ (多端同步) │          │   (Hooks)       │
└────┬─────┴────┬─────┴──────────┴──────────┴───────┬─────────┘
     │          │                                    │
     ▼          ▼                                    │
  AstrBot ←──────────────────────────────────────────┘
  (轻量网关：Claude Code 通知 + OpenClaw 存活监控)
     │
     │  ← 日常交互直连 →
     │
     ▼
  OpenClaw（核心执行引擎，沙箱模式，不暴露外网）
     │
     ├─ MemOS ────────── 个人记忆（自动提取、知识图谱、版本追溯）
     ├─ AnythingLLM ──── 长文档 RAG（论文、资料语义检索）
     ├─ Obsidian vault ── 结构化笔记（跨设备同步、待办展示）
     ├─ MS To Do ──────── 待办管理（Graph API，双向同步 Obsidian）
     ├─ Ollama ────────── LLM 推理（qwen3.5-instruct:9b）
     ├─ docker.sock ──── 容器管理（查看状态、重启服务）
     └─ 宿主机脚本 ────── Windows 应用控制（白名单命令）

基础设施层：
  Nginx (:18080) → 各服务容器
  Cloudflare Tunnel → Nginx → 外网访问 (SSL by Cloudflare)
  CouchDB → Obsidian LiveSync 跨设备同步
```

### 数据流向

```
日常对话（微信发送）
  → OpenClaw（意图识别 + 执行）
    ├→ 自然语言自动提取 → MemOS（事实/关系/偏好）
    ├→ "记笔记" → Obsidian vault 00-Inbox/
    ├→ "加待办" → MS To Do + Obsidian Tasks 双写
    └→ 普通对话 → Ollama 回复

深度研究
  → Open Notebook（上传资料 → AI 分析）
  → AnythingLLM（RAG 知识库查询）

Claude Code 事件
  → Hooks POST → AstrBot → 微信推送通知
```

---

## 技术选型

| 模块 | 方案 | 备注 |
|------|------|------|
| 交互入口 | 微信小号（OpenClaw 原生支持） | 封号换号，数据不受影响 |
| 核心执行 | OpenClaw (ghcr.io/openclaw/openclaw) | AI Agent，沙箱模式，不暴露外网 |
| 通知网关 | AstrBot | 轻量保留：Claude Code 通知 + 存活监控 |
| LLM 主力 | Ollama qwen3.5-instruct:9b | 本地运行，隐私优先 |
| LLM 备用 | DeepSeek API | 本地超时 15s 自动切换 |
| Embedding | bge-m3 (via Ollama) | 中英文双语支持 |
| **个人记忆** | **MemOS** (MemTensor) | 自动提取、知识图谱、矛盾处理、版本追溯 |
| 知识库 RAG | AnythingLLM | 长文档语义检索 |
| 笔记同步 | Obsidian + CouchDB LiveSync | 跨设备实时同步，本地 Markdown |
| 笔记归纳 | Open Notebook | 定期整理结构化知识 |
| 待办管理 | MS To Do + Obsidian Tasks | 双向同步，MS To Do 输入，Obsidian 展示 |
| 开发监控 | Claude Code Hooks → AstrBot | 审批/报错/完成/超时告警 |
| 密码管理 | Vaultwarden | 已部署，API 密钥统一存储 |
| 部署环境 | 本地 Docker（WSL2） | 后期迁移至 NAS |

---

## 安全架构

### 分层权限模型

```
┌─────────────────────────────────────────────────────────────┐
│  AstrBot（网关层）                                            │
│  · 外网可达（微信回调、Claude Code Hooks POST）                 │
│  · 无文件系统权限、无 Docker socket                            │
├─────────────────────────────────────────────────────────────┤
│  OpenClaw（执行层，仅内网）                                     │
│  · docker.sock — 容器管理                                     │
│  · Obsidian vault — 唯一挂载的用户目录                          │
│  · 宿主机命令 — 仅通过白名单脚本                                │
│  · 沙箱模式 + 分级审批                                        │
├─────────────────────────────────────────────────────────────┤
│  宿主机白名单脚本（最后防线）                                    │
│  · 监听 Unix socket                                          │
│  · 只执行预定义命令，其他一律拒绝                                │
└─────────────────────────────────────────────────────────────┘
```

### 操作分级审批

| 风险等级 | 操作类型 | 审批方式 |
|---------|---------|---------|
| 自动执行 | 查看容器状态、系统资源、读笔记、查待办、语义检索、日常对话 | 直接执行 |
| 告知后执行 | 创建/修改笔记、创建/完成待办、存储记忆 | 执行后微信通知结果 |
| 人工确认 | 重启容器、重启宿主机应用、删除文件、执行宿主机命令 | 微信确认后才执行 |

---

## 现有基础设施

> 详见 `/home/mystice/Project/plans/0317/DOCKER-GUIDE.md`

| 服务 | 容器名 | 内部端口 | Compose 位置 | 状态 |
|------|--------|----------|-------------|------|
| Nginx | nginx | 80 | infrastructure/ | ✅ |
| Cloudflared | cloudflared | — | infrastructure/ | ✅ |
| Vaultwarden | vaultwarden | 80 | vaultwarden/ | ✅ |
| Open Notebook | (auto) | 8502, 5055 | notebook/ | ✅ |
| SurrealDB | (auto) | 8000 | notebook/ | ✅ |
| Ollama | ollama | 11434 | ai/ | ✅ |
| AnythingLLM | anythingllm | 3001 | ai/ | ✅ |

**部署规范**：
- Docker 网络：`proxy`（external: true）
- 数据路径：`/mnt/f/Docker/<服务名>/`
- Compose 路径：`/mnt/f/Docker/compose/<服务名>/docker-compose.yml`
- Nginx 配置：`/mnt/f/Docker/nginx/conf.d/<服务名>.conf`
- Nginx 规则：`resolver 127.0.0.11`，`set $upstream` 变量模式，`listen 80`

---

## 新增服务清单

| 服务 | 容器名 | 镜像 | 内部端口 | Compose 位置 | 阶段 |
|------|--------|------|----------|-------------|------|
| AstrBot | astrbot | soulter/astrbot:latest | 6185, 6186 | bot/ | 1 |
| OpenClaw | openclaw | ghcr.io/openclaw/openclaw:latest | 18789 | agent/ | 1 |
| MemOS API | memos-api | 源码构建 | 8000 | memory/ | 2 |
| Neo4j (MemOS) | memos-neo4j | neo4j:5.26.6 | 7474, 7687 | memory/ | 2 |
| Qdrant (MemOS) | memos-qdrant | qdrant/qdrant:v1.15.3 | 6333 | memory/ | 2 |
| CouchDB | obsidian-couchdb | couchdb:3.3.3 | 5984 | sync/ | 3 |

---

## 实施计划

### 阶段 1 — 核心骨架（第 1~2 周）

**目标**：部署 AstrBot + OpenClaw，跑通微信消息链路

#### 1A：OpenClaw 部署

```yaml
# /mnt/f/Docker/compose/agent/docker-compose.yml
services:
  openclaw:
    image: ghcr.io/openclaw/openclaw:latest
    container_name: openclaw
    restart: always
    volumes:
      - /mnt/f/Docker/openclaw/config:/home/node/.openclaw
      - /var/run/docker.sock:/var/run/docker.sock
      # Obsidian vault 在阶段 3 部署后再挂载
    environment:
      - OPENCLAW_GATEWAY_TOKEN=${OPENCLAW_TOKEN}
    env_file:
      - .env
    networks:
      - proxy

networks:
  proxy:
    external: true
```

- [ ] 创建数据目录 `/mnt/f/Docker/openclaw/config`，设置 uid 1000 权限
- [ ] 创建 `.env` 配置 Token 和 API Key
- [ ] `docker compose up -d` 启动
- [ ] 通过 SSH 隧道访问 Dashboard `localhost:18789` 完成初始化
- [ ] 配置 LLM：Ollama `http://ollama:11434`，模型 qwen3.5-instruct:9b
- [ ] 配置微信接入（OpenClaw 原生支持）
- [ ] 验证微信消息收发

#### 1B：AstrBot 部署（轻量通知网关）

```yaml
# /mnt/f/Docker/compose/bot/docker-compose.yml
services:
  astrbot:
    image: soulter/astrbot:latest
    container_name: astrbot
    restart: always
    volumes:
      - /mnt/f/Docker/bot/data:/AstrBot/data
    networks:
      - proxy

networks:
  proxy:
    external: true
```

Nginx 配置（仅 API 端口，供 Claude Code Hooks POST）：

```nginx
# /mnt/f/Docker/nginx/conf.d/astrbot.conf
server {
    listen 80;
    server_name astrbot.mysticee.online astrbot.home;

    resolver 127.0.0.11 valid=30s;

    location / {
        set $upstream http://astrbot:6185;
        proxy_pass $upstream;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

- [ ] 部署 AstrBot
- [ ] Cloudflare Tunnel + Access 保护 WebUI
- [ ] 配置 LLM 连接 Ollama
- [ ] 配置微信接入（备用通道，主要用于接收 Hooks 推送）

#### 1C：宿主机控制脚本

```bash
# /mnt/f/Docker/executor/host-executor.py
# 监听 Unix socket /tmp/host-exec.sock
# 白名单配置：/mnt/f/Docker/executor/commands.yaml
```

- [ ] 编写白名单执行脚本
- [ ] 配置为 systemd 用户服务或 WSL 启动项
- [ ] OpenClaw 挂载 socket：`/tmp/host-exec.sock:/tmp/host-exec.sock`
- [ ] 测试白名单内/外命令

**验收标准**：
- 微信发消息 → OpenClaw 收到并回复
- Claude Code Hooks POST → AstrBot → 微信收到通知
- OpenClaw 可查看 Docker 容器状态
- 宿主机白名单命令可执行，非白名单被拒绝

---

### 阶段 2 — 个人记忆系统（第 2~3 周）

**目标**：部署 MemOS，实现对话自动记忆提取和检索

```yaml
# /mnt/f/Docker/compose/memory/docker-compose.yml
services:
  memos-api:
    build:
      context: /mnt/f/Docker/memory/MemOS
      dockerfile: docker/Dockerfile
    container_name: memos-api
    restart: always
    volumes:
      - /mnt/f/Docker/memory/data:/app/data
    environment:
      - LLM_PROVIDER=ollama
      - LLM_MODEL=qwen3.5-instruct:9b
      - OLLAMA_API_BASE=http://ollama:11434
      - EMBEDDER_PROVIDER=ollama
      - EMBEDDER_MODEL=bge-m3
      - NEO4J_URL=bolt://memos-neo4j:7687
      - NEO4J_USERNAME=neo4j
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
      - QDRANT_HOST=memos-qdrant
      - QDRANT_PORT=6333
    depends_on:
      - memos-neo4j
      - memos-qdrant
    networks:
      - proxy

  memos-neo4j:
    image: neo4j:5.26.6
    container_name: memos-neo4j
    restart: always
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
      - NEO4J_PLUGINS=["apoc"]
    volumes:
      - /mnt/f/Docker/memory/neo4j:/data
    networks:
      - proxy

  memos-qdrant:
    image: qdrant/qdrant:v1.15.3
    container_name: memos-qdrant
    restart: always
    volumes:
      - /mnt/f/Docker/memory/qdrant:/qdrant/storage
    networks:
      - proxy

networks:
  proxy:
    external: true
```

- [ ] 克隆 MemOS 源码到 `/mnt/f/Docker/memory/MemOS`
- [ ] 创建数据目录和 `.env`
- [ ] `docker compose up -d` 启动三个容器
- [ ] 验证 MemOS API：`curl http://localhost:8000/docs`
- [ ] OpenClaw 配置 MemOS MCP Server 连接
- [ ] 测试自动记忆提取：
  - 发"今天和李宁吃饭，他说下周去郊游" → 自动提取事实
  - 发"李宁女朋友是谁" → 检索返回结果
- [ ] 测试矛盾处理：
  - 发"李宁和王曼曼分手了" → 旧关系归档，新事实生成
- [ ] 测试自然语言纠错：
  - 发"你记错了，不是王曼曼是王漫漫" → feedback 接口修正

**验收标准**：
- 正常聊天自动提取并存储记忆（无需"记一下"触发词）
- 能按语义检索过去的记忆
- 事实更新时旧版本保留可追溯
- 自然语言纠错生效

---

### 阶段 3 — 笔记同步（第 3~4 周）

**目标**：Obsidian 跨设备同步 + OpenClaw 笔记读写

```yaml
# /mnt/f/Docker/compose/sync/docker-compose.yml
services:
  couchdb:
    image: couchdb:3.3.3
    container_name: obsidian-couchdb
    restart: always
    environment:
      - COUCHDB_USER=${COUCHDB_USER}
      - COUCHDB_PASSWORD=${COUCHDB_PASSWORD}
    volumes:
      - /mnt/f/Docker/sync/couchdb-data:/opt/couchdb/data
      - /mnt/f/Docker/sync/couchdb-etc:/opt/couchdb/etc/local.d
    env_file:
      - .env
    networks:
      - proxy

networks:
  proxy:
    external: true
```

```nginx
# /mnt/f/Docker/nginx/conf.d/obsidian-sync.conf
server {
    listen 80;
    server_name obsidian-sync.mysticee.online obsidian-sync.home;

    resolver 127.0.0.11 valid=30s;
    client_max_body_size 100M;

    location / {
        set $upstream http://obsidian-couchdb:5984;
        proxy_pass $upstream;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

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

- [ ] 部署 CouchDB + Nginx 配置
- [ ] Cloudflare Tunnel + Access
- [ ] CouchDB 初始化（Single Node + 创建 obsidiandb）
- [ ] 创建 Obsidian vault 目录（参考下方结构）
- [ ] 电脑端 Obsidian 安装 Self-hosted LiveSync 连接
- [ ] 手机端 LiveSync 连接
- [ ] 华为平板通过卓易通安装 Obsidian + LiveSync
- [ ] OpenClaw 挂载 vault：更新 agent/docker-compose.yml 添加 volume
- [ ] 测试 OpenClaw 读写 vault 笔记
- [ ] （可选）OneNote 迁移：Obsidian Importer 插件

**Obsidian Vault 结构**：
```
obsidian-vault/
├── 00-Inbox/           # OpenClaw 写入此处
├── 01-Daily/           # 每日笔记
├── 02-Projects/        # 项目笔记
├── 03-Areas/           # 持续关注领域
├── 04-Resources/       # 参考资料
├── 05-Archive/         # 归档
├── 07-Templates/       # 模板
└── Attachments/        # 附件
```

**验收标准**：
- 多设备 Obsidian 秒级同步
- OpenClaw 可创建/读取 vault 中的笔记
- 微信说"记个笔记：XXX" → vault 中出现对应文件

---

### 阶段 4 — 待办联动（第 4~5 周）

**目标**：MS To Do + Obsidian Tasks 双向同步

#### 输入路径
1. 手机 MS To Do 直接添加
2. 微信 → OpenClaw → 同时写入 MS To Do + Obsidian
3. Obsidian 直接编辑

#### 同步机制
OpenClaw 定时任务（每 15~30 分钟）双向 diff 同步

任务清单：
- [ ] Azure Portal 注册应用（个人账户，`Tasks.ReadWrite` + `User.Read`）
- [ ] 完成 OAuth 授权，持久化 refresh_token（存入 Vaultwarden）
- [ ] OpenClaw 配置 MS Graph API Tool/Skill
- [ ] 实现自然语言待办操作：
  - "加个待办：明天交报告" → MS To Do + Obsidian
  - "今天有啥待办" → 查询并汇总
  - "完成 XXX" → 双端标记完成
- [ ] 配置定时同步任务：MS To Do ↔ Obsidian Tasks
- [ ] Obsidian 安装推荐插件：Tasks、Dataview、Calendar
- [ ] 配置每日早 8 点待办推送到微信
- [ ] 配置 Obsidian 中的周计划/日历视图（Dataview 查询）

**验收标准**：
- 微信说"加待办：明天买菜" → MS To Do + Obsidian 同时出现
- MS To Do 手动添加的任务 → 30 分钟内出现在 Obsidian
- 每天早上微信收到当日待办推送
- Obsidian 中可查看周计划、日历视图

---

### 阶段 5 — Claude Code 监控（第 5~6 周）

**目标**：Claude Code 状态实时通知到手机

| 事件类型 | 优先级 | 说明 |
|----------|--------|------|
| 需要审批/确认 | 高 | 附带操作内容摘要 |
| 任务执行报错 | 高 | 附带错误信息摘要 |
| 长时间无响应 | 中 | 超时阈值 5 分钟 |
| 任务完成通知 | 低 | 附带任务摘要 |

- [ ] 编写 Claude Code hooks 脚本（POST → AstrBot API）
- [ ] 设计结构化通知模板
- [ ] 配置 AstrBot 接收 Hooks → 推送到微信
- [ ] （进阶）双向审批：微信回复 → AstrBot → pipe/文件 → Claude Code

**验收标准**：
- Claude Code 等待审批时，微信收到通知
- 回复"同意"后 Claude Code 继续执行

---

### 阶段 6 — 系统管理（第 6~7 周）

**目标**：通过微信查看系统状态、重启服务和应用

- [ ] OpenClaw 配置 Docker 管理 Skill（通过 docker.sock）
- [ ] 宿主机白名单脚本配置常用命令：
  ```yaml
  # /mnt/f/Docker/executor/commands.yaml
  commands:
    restart-parsec:
      description: "重启 Parsec 远程桌面"
      command: 'powershell.exe -Command "Restart-Service Parsec"'
    restart-emulator:
      description: "重启模拟器"
      command: 'powershell.exe -Command "Stop-Process -Name LDPlayer -Force; Start-Process ..."'
    # 按需添加
  ```
- [ ] 分级审批规则配置到 OpenClaw
- [ ] 测试：
  - "系统状况怎么样" → 返回容器状态 + 资源占用
  - "重启 Ollama" → 微信确认 → 执行 → 返回结果
  - "重启 Parsec" → 微信确认 → 白名单脚本执行

**验收标准**：
- 微信可查看系统/容器状态
- 危险操作需确认后才执行
- 非白名单命令被拒绝

---

## 存储架构总结

| 存储 | 存什么 | 怎么存 | 怎么取 |
|------|--------|--------|--------|
| **MemOS** | 人物关系、事件、偏好、个人事实 | 对话自动提取，无需触发词 | 语义检索 + 知识图谱 + 版本追溯 |
| **AnythingLLM** | 长文档、论文、学习资料 | 上传文档 / API 写入 | RAG 向量检索 |
| **Obsidian** | 结构化笔记、周计划、日记 | 文件写入（OpenClaw / 手动） | 浏览 / Dataview / Calendar |
| **MS To Do** | 待办事项 | 自然语言 / 手动 / 定时同步 | App / 微信推送 / Obsidian 展示 |

---

## 域名规划

| 子域名 | 服务 | Cloudflare Access | 备注 |
|--------|------|:---:|------|
| vault.mysticee.online | Vaultwarden | ❌ | 客户端不兼容 |
| notebook.mysticee.online | Open Notebook | ✅ | |
| ai.mysticee.online | AnythingLLM | ✅ | |
| astrbot.mysticee.online | AstrBot WebUI | ✅ | |
| obsidian-sync.mysticee.online | CouchDB | ✅ | LiveSync 用 |
| — | OpenClaw | — | **不暴露外网**，SSH 隧道访问 |
| — | MemOS | — | **不暴露外网**，仅内网 |

---

## 核心原则

1. **数据与入口解耦**：通信渠道可随时更换，不影响任何数据
2. **工具复用优先**：MS To Do 保持现有习惯，只新增 AI 操控层
3. **本地优先**：隐私数据全部存储在本地
4. **纵深防御**：分级审批 + 宿主机白名单 + 沙箱
5. **渐进实施**：每个阶段独立可验收，组件可替换
6. **遵循部署规范**：所有服务遵循 DOCKER-GUIDE.md 标准流程

---

## 待确认事项

- [ ] OpenClaw 微信接入的具体协议和稳定性（部署后验证）
- [ ] MemOS 源码构建是否顺利（部署后验证）
- [ ] Claude Code 无响应告警超时阈值（暂定 5 分钟）
- [ ] NAS 迁移时间节点
- [ ] 是否从 OneNote 迁移现有笔记到 Obsidian
- [ ] 飞书团队协作是否纳入后续阶段

---

## 参考文档

- **部署规范**：`/home/mystice/Project/plans/0317/DOCKER-GUIDE.md`
- **变更记录**：`/home/mystice/Project/plans/0317/CHANGELOG.md`
- **完整生产力栈方案**：`./Self-hosted-productivity-stack.md`
- **MemOS**：https://github.com/MemTensor/MemOS
- **OpenClaw**：https://github.com/openclaw/openclaw
- **AstrBot**：https://github.com/AstrBotDevs/AstrBot
- **Obsidian LiveSync**：https://github.com/vrtmrz/obsidian-livesync

---

*文档更新时间：2026-03-31*
*下一步：开始阶段 1A，部署 OpenClaw*
