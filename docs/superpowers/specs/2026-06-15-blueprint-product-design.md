# Blueprint — 产品设计文档

> **版本:** 1.0
> **日期:** 2026-06-15
> **状态:** 设计完成，待实施

---

## 1. 产品定义

**Blueprint** 是面向 2-5 人小团队的 AI 全栈开发平台。一句话需求，生成完整可运行的 Web 项目——代码、测试、文档、部署配置一步到位。关键节点人工确认，质量优先。

### 核心价值主张

| 维度 | 定义 |
|------|------|
| 目标用户 | 2-5 人小团队（创业公司、工作室、内部小团队） |
| 核心价值 | 快速原型生成，一句话出完整项目 |
| 使用场景 | 从零生成 + 存量项目扩展 |
| 差异化 | 交付完整度 + 人机协作体验 + 存量项目兼容 |
| 技术范围 | 全栈 Web（前端 + 后端 + 数据库 + 部署） |
| 成功标准 | 质量优先——生成的代码改几行就能上线 |

---

## 2. 三模式架构

### 2.1 全栈工程师模式（默认主模式）

**一句话：** 小团队的 AI 全栈成员，说一句话出完整可运行项目

**使用场景：** 从零开始做一个新项目

**工作流程：**
```
用户输入需求
    ↓
PM → 需求分析 → 用户故事 + 功能清单
    ↓
Architect → 技术方案 → 架构图 + 接口定义
    ↓
🔴 人工确认：架构方案 OK 吗？
    ↓
Developer → 编码实现 → 写入磁盘 + 执行验证 + 自动修复
    ↓
Tester → 编写测试 + 沙箱执行 → 测试报告
    ↓
Reviewer → 代码审查 → 审查意见
    ↓
🔴 人工确认：代码质量 OK 吗？
    ↓
交付：代码 + 测试 + 文档 + 部署配置 + 安全报告 + 质量评分
```

**交付物清单：**

| 交付物 | 说明 | 生成方式 |
|--------|------|---------|
| 源代码 | 完整可运行的前后端代码 | Developer Agent |
| 测试用例 | pytest / vitest 测试 | Tester Agent |
| README.md | 安装、运行、项目结构说明 | 文档生成器 |
| API 文档 | OpenAPI / Swagger 规范 | 文档生成器 |
| 架构图 | Mermaid 格式，可直接渲染 | 文档生成器 |
| 部署配置 | Dockerfile + docker-compose.yml | 部署脚本生成器 |
| 安全报告 | 扫描结果 + 修复建议 | 安全扫描器 |
| 质量评分 | 代码复杂度/测试覆盖/安全/可维护性 | 质量评分器 |

### 2.2 代码工厂模式（快捷入口）

**一句话：** 选模板、填参数、秒级出项目

**使用场景：** 快速出页面、批量生成组件、搭建脚手架

**工作流程：**
```
选择模板（React/Vue/Flask/FastAPI/Go API/...）
    ↓
填写参数（项目名、功能描述、技术偏好）
    ↓
一键生成（秒级响应）
    ↓
可选：在主模式中继续迭代
```

**模板分类：**

| 分类 | 模板 |
|------|------|
| 前端 | React SPA、Vue 3 SPA、Next.js、静态站点 |
| 后端 | Flask API、FastAPI API、Express API、Go API |
| 全栈 | React+FastAPI、Vue+Flask、Next.js+Prisma |
| 工具 | CLI 工具、Chrome 扩展、npm 包 |

### 2.3 技术顾问模式（快捷入口）

**一句话：** 不只写代码，还帮你做技术决策

**使用场景：** 架构选型、性能优化、代码审查、技术咨询

**工作流程：**
```
描述问题（架构选型/性能瓶颈/代码质量/...）
    ↓
Architect 分析 → 给出方案 + 理由 + 对比
    ↓
可选：一键执行建议（如重构代码、优化配置）
```

**咨询类型：**

| 类型 | 说明 |
|------|------|
| 架构选型 | "用 GraphQL 还是 REST？""要不要上微服务？" |
| 性能优化 | "页面加载太慢怎么优化？""数据库查询慢怎么改？" |
| 代码审查 | "这段代码有什么问题？""怎么重构更好？" |
| 技术方案 | "用户系统怎么设计？""支付功能怎么实现？" |
| 安全咨询 | "有什么安全风险？""怎么防注入？" |

---

## 3. 功能模块总览

### 3.1 核心链路模块

| 模块 | 说明 | 状态 |
|------|------|------|
| PM Agent | 需求分析、用户故事拆解 | ✅ 已有 |
| Architect Agent | 技术方案、接口设计 | ✅ 已有 |
| Developer Agent | 编码实现 + 执行验证 + 自动修复 | ✅ 已有 |
| Tester Agent | 生成测试 + 沙箱执行 | ✅ 已有 |
| Reviewer Agent | 代码审查 + 质量把关 | ✅ 已有 |
| Proposer-Critic | Agent 内部对抗讨论（可配置开关） | ✅ 已有 |
| WebSocket 实时通信 | Agent 状态实时更新 | ✅ 已有 |
| 代码执行沙箱 | Python/Node/SQL 安全执行 | ✅ 已有 |
| LangGraph 图编排 | 条件分支 + 循环 + interrupt/resume | ✅ 已有 |

### 3.2 交付增强模块

| 模块 | 说明 | 优先级 |
|------|------|--------|
| 代码质量评分 | 自动打分（0-100），五维度雷达图 | P0 |
| 变更历史对比 | 每轮迭代快照，支持 diff 对比 | P0 |
| Agent 思考过程可视化 | 查看 Agent 的 prompt/响应/工具调用链 | P1 |
| 代码安全扫描 | 硬编码密钥/SQL 注入/XSS/依赖漏洞 | P1 |
| 项目文档自动生成 | README + API 文档 + 架构图 | P1 |
| 部署脚本生成 | Dockerfile + docker-compose + nginx + CI/CD | P1 |

### 3.3 平台化模块

| 模块 | 说明 | 优先级 |
|------|------|--------|
| Webhook 通知 | 项目完成/失败推送到钉钉/飞书/Slack | P2 |
| CLI 工具 | 命令行创建/查看/下载项目 | P2 |
| 项目模板市场 | 预置模板 + 用户自定义模板 | P2 |
| 知识库集成 | 上传技术文档，Agent 参考生成代码 | P3 |
| API 开放平台 | 第三方系统调用 Blueprint 生成代码 | P3 |
| 项目评分与排行榜 | 社区化评分、点赞、排行 | P3 |

### 3.4 协作与扩展模块

| 模块 | 说明 | 优先级 |
|------|------|--------|
| 多人协作 | 实时协作编辑，光标同步，文件锁 | P3 |
| 前端架构改造 | ProjectDetailPage 拆分 + Store 拆分 | P2 |
| 全局错误处理 | Toast 通知 + 全局异常捕获 | P2 |
| 多语言模板 | 模板市场扩展，支持更多技术栈 | 持续 |

---

## 4. 功能详细设计

### 4.1 代码质量评分

**后端:** `Blueprint/utils/quality_scorer.py`

五个维度，满分 100：

| 维度 | 权重 | 计算方式 |
|------|------|---------|
| 代码复杂度 | 25% | 行数、嵌套深度、函数长度 |
| 测试覆盖 | 25% | 测试文件数 vs 源文件数 |
| 安全风险 | 20% | 安全扫描结果 |
| 可维护性 | 15% | 命名规范、注释率、模块化 |
| 文档完整度 | 15% | README/注释/API 文档 |

**前端:** `QualityScore.vue` — 雷达图 + 进度条 + 等级标签（A/B/C/D/F）

### 4.2 变更历史对比

**后端:** `Blueprint/utils/diff_engine.py`

- 每轮迭代保存文件快照（`.snapshots/iter_001.json`）
- 支持任意两个迭代的 diff 对比
- 统计：变更文件数、新增行数、删除行数

**前端:** `DiffViewer.vue` — 文件列表 + 逐行对比（绿=新增，红=删除）

### 4.3 Agent 思考过程可视化

**后端:** `Blueprint/utils/memory.py` 新增 `AgentTrace`

记录每个 Agent 的：
- 发送给 LLM 的完整 prompt
- LLM 的原始返回
- 工具调用列表（写了什么文件、执行了什么命令）
- 耗时、Token 数

**前端:** `AgentTracePanel.vue` — 可折叠的 Trace 面板，嵌入 Agent 卡片下方

### 4.4 代码安全扫描

**后端:** `Blueprint/utils/security_scanner.py`

| 扫描类型 | 检测内容 |
|----------|---------|
| 硬编码密钥 | API Key、密码、Token、私钥 |
| SQL 注入 | 字符串拼接 SQL、f-string SQL |
| XSS 风险 | innerHTML、dangerouslySetInnerHTML |
| 依赖漏洞 | npm audit、safety check |
| 最佳实践 | 未处理异常、硬编码路径 |

**前端:** `SecurityReport.vue` — 安全分数 + 严重程度分布 + 问题列表

### 4.5 项目文档自动生成

**后端:** `Blueprint/utils/doc_generator.py`

| 文档 | 生成方式 |
|------|---------|
| README.md | 根据代码和需求自动生成 |
| API 文档 | 扫描路由提取 OpenAPI 规范 |
| 架构图 | 根据文件结构生成 Mermaid 图 |
| 安装指南 | 根据 tech stack 生成安装步骤 |

**前端:** `DocPreview.vue` — Tab 切换（README / API / 架构图），Markdown 渲染

### 4.6 部署脚本生成

**后端:** `Blueprint/utils/deploy_generator.py`

自动检测项目类型，生成：
- Dockerfile（Python/Node/Go/静态）
- docker-compose.yml（含数据库、Redis）
- nginx.conf（反向代理 + HTTPS）
- .github/workflows/deploy.yml（CI/CD）
- start.sh / start.bat（启动脚本）

**前端:** `DeployPanel.vue` — 文件预览 + 一键复制 + 全部下载

### 4.7 Webhook 通知

**后端:** `Blueprint/utils/webhook.py`

支持事件：project.completed / project.failed / project.started / agent.error

支持平台：钉钉、飞书、Slack、企业微信、自定义 URL

带签名验证（HMAC-SHA256）

**前端:** SettingsPage 扩展 — Webhook URL + 事件选择 + Secret + 测试按钮

### 4.8 CLI 工具

**后端:** `Blueprint/cli.py`

```bash
Blueprint create "做一个计算器" --wait     # 创建项目并等待完成
Blueprint status proj-123                  # 查看项目状态
Blueprint download proj-123 -o ./output    # 下载项目文件
Blueprint list                             # 列出所有项目
```

通过 REST API 与后端通信，无需前端改动。

### 4.9 项目模板市场

**后端:** `Blueprint/templates/registry.py`

模板分类：Web 应用 / API / 移动端 / 工具

每个模板包含：meta.json（描述）+ 文件内容 + 启动命令

支持用户自定义模板（上传到模板市场）

**前端:** `TemplatesPage.vue` — 模板卡片网格 + 分类导航 + 搜索 + 预览

### 4.10 知识库集成

**后端:** `Blueprint/knowledge/base.py`

基于 LangChain + ChromaDB 的 RAG 系统：
- 上传技术文档（.md / .txt / .pdf / .docx）
- 文档分块 + 向量化存储
- Agent 生成代码时自动检索相关文档
- 检索结果注入 Agent prompt

**前端:** SettingsPage 扩展 — 上传文档 + 文档列表 + 清空按钮

### 4.11 API 开放平台

**后端:** `Blueprint/api/public.py`

REST API 端点：
- POST /api/v1/projects — 创建项目
- GET /api/v1/projects/:id — 查询状态
- GET /api/v1/projects/:id/download — 下载文件
- POST /api/v1/webhook/register — 注册 Webhook

认证：API Key（Header: X-API-Key）
限流：免费版 10 次/分钟，Pro 版 100 次/分钟

**前端:** `ApiDocsPage.vue` — 交互式 API 文档 + API Key 管理 + 使用示例

### 4.12 项目评分与排行榜

**后端:** `Blueprint/utils/ranking.py`

评分维度：
- 代码质量分（40%）— 来自 QualityScorer
- 需求复杂度分（30%）— 基于 Agent 输出指标
- 完成速度分（30%）— 完成时间 vs 需求复杂度

排行榜：按日/周/月/全部排序，支持点赞

**前端:** `RankingPage.vue` — 排行榜表格 + 统计卡片 + 点赞功能

### 4.13 多人协作

**后端:** `Blueprint/collaboration/session.py`

- 实时协作编辑（WebSocket）
- 文件锁（防止同时编辑冲突）
- 光标同步（看到其他人的光标位置）
- 变更历史（CRDT 简化版）

**前端:**
- `CollabPanel.vue` — 在线用户列表 + 文件锁状态
- `CollabCursor.vue` — 彩色光标 + 用户名标签

---

## 5. 前端架构

### 5.1 页面结构

| 页面 | 路由 | 说明 |
|------|------|------|
| 登录页 | /login | 登录/注册 |
| 工作台 | / | 主模式（全栈工程师） |
| 项目列表 | /projects | 历史项目 |
| 项目详情 | /projects/:id | 文件/日志/评分/安全/文档/对比 |
| 设置 | /settings | LLM/Webhook/知识库 |
| 模板市场 | /templates | 代码工厂入口 |
| 排行榜 | /ranking | 社区评分 |
| API 文档 | /api-docs | 开放平台 |

### 5.2 组件拆分

**工作台（主模式）：**

```
WorkbenchPage
├── FlowPanel (左侧)
│   ├── AgentCard × 5（PM/Architect/Developer/Tester/Reviewer）
│   ├── IterationInfo（迭代进度）
│   ├── OutputPanel（文件预览/下载）
│   ├── DiscussionPanel（Proposer-Critic 讨论）
│   ├── QualityScore ← 新增
│   └── AgentTracePanel ← 新增
├── ChatPanel (右侧)
│   ├── ChatHeader（操作按钮）
│   ├── 消息列表（用户/系统/Agent/工具消息）
│   ├── AgentOutputCard（结构化 Agent 输出）
│   └── 输入框
└── 快捷入口（侧边栏）
    ├── 代码工厂按钮
    └── 技术顾问按钮
```

**项目详情页（拆分后）：**

```
ProjectDetailPage（Tab 切换）
├── ProjectInfoCard（项目信息）
├── ProjectFilesPanel（文件预览/下载）
├── ProjectLogPanel（开发日志）
├── ProjectTimeline（执行时间线）
├── QualityScore ← 新增
├── DiffViewer ← 新增
├── SecurityReport ← 新增
├── DocPreview ← 新增
└── DeployPanel ← 新增
```

### 5.3 Store 拆分

```
stores/
├── auth.js        — 认证状态（token, username）
├── project.js     — 项目元数据（id, name, status）
├── chat.js        — 消息和聊天（messages, input）
├── agent.js       — Agent 状态和输出（agentStatus, agentOutputs）
├── files.js       — 文件预览和下载（files, preview）
└── websocket.js   — 连接状态（isConnected, reconnecting）
```

### 5.4 新增 Composable

| Composable | 用途 |
|------------|------|
| useNotification | 全局消息提示（成功/错误/警告） |
| useLocalStorage | 响应式 localStorage 读写 |
| useCollaboration | 协作状态管理（用户/锁/光标） |

### 5.5 新增组件汇总

| 组件 | 所属页面 | 行数估算 |
|------|---------|---------|
| QualityScore.vue | 工作台 + 详情页 | ~120 |
| DiffViewer.vue | 详情页 | ~150 |
| AgentTracePanel.vue | 工作台 | ~200 |
| SecurityReport.vue | 详情页 | ~150 |
| DocPreview.vue | 详情页 | ~100 |
| DeployPanel.vue | 详情页 | ~150 |
| CollabPanel.vue | 工作台 | ~120 |
| CollabCursor.vue | 工作台 | ~40 |
| TemplateCard.vue | 模板市场 | ~60 |
| RankingCard.vue | 排行榜 | ~80 |
| StatsCard.vue | 排行榜 | ~40 |
| ApiKeyManager.vue | API 文档 | ~100 |
| Toast.vue | 全局 | ~50 |

---

## 6. 后端架构

### 6.1 API 端点汇总

**核心链路（已有）：**

| 端点 | 方法 | 说明 |
|------|------|------|
| /api/auth/login | POST | 登录 |
| /api/auth/register | POST | 注册 |
| /ws/project | WS | WebSocket 实时通信 |
| /api/projects | GET/POST | 项目 CRUD |
| /api/projects/:id | GET/DELETE | 项目详情 |
| /api/projects/:id/state | GET | 项目状态恢复 |
| /api/projects/:id/files | GET | 文件列表 |
| /api/projects/:id/download | GET | 下载文件 |
| /api/settings | GET/PUT | 系统设置 |
| /api/settings/presets | GET/POST/DELETE | API 预设 |

**新增端点（13 个功能）：**

| 端点 | 方法 | 说明 | 所属模块 |
|------|------|------|---------|
| /api/projects/:id/quality | GET | 质量评分 | 代码质量评分 |
| /api/projects/:id/diff | GET | 变更对比 | 变更历史对比 |
| /api/projects/:id/traces | GET | Agent 思考过程 | 思考过程可视化 |
| /api/projects/:id/security | GET | 安全扫描 | 代码安全扫描 |
| /api/projects/:id/docs | GET | 项目文档 | 文档自动生成 |
| /api/projects/:id/deploy | GET | 部署配置 | 部署脚本生成 |
| /api/settings/webhooks | GET/POST/DELETE | Webhook 管理 | Webhook 通知 |
| /api/settings/webhooks/:id/test | POST | 测试 Webhook | Webhook 通知 |
| /api/templates | GET | 模板列表 | 模板市场 |
| /api/templates/:id | GET | 模板内容 | 模板市场 |
| /api/knowledge/upload | POST | 上传文档 | 知识库集成 |
| /api/knowledge/list | GET | 文档列表 | 知识库集成 |
| /api/v1/projects | POST | API 创建项目 | 开放平台 |
| /api/v1/projects/:id | GET | API 查询状态 | 开放平台 |
| /api/ranking | GET | 排行榜 | 评分排行 |
| /api/ranking/:id/like | POST | 点赞 | 评分排行 |
| /api/projects/:id/collab/invite | GET | 协作邀请 | 多人协作 |

### 6.2 新增文件清单

| 文件 | 说明 | 行数估算 |
|------|------|---------|
| Blueprint/utils/quality_scorer.py | 质量评分 | ~150 |
| Blueprint/utils/diff_engine.py | 变更对比 | ~120 |
| Blueprint/utils/security_scanner.py | 安全扫描 | ~200 |
| Blueprint/utils/doc_generator.py | 文档生成 | ~150 |
| Blueprint/utils/webhook.py | Webhook 通知 | ~80 |
| Blueprint/utils/deploy_generator.py | 部署脚本生成 | ~200 |
| Blueprint/utils/ranking.py | 评分排行 | ~150 |
| Blueprint/cli.py | CLI 工具 | ~150 |
| Blueprint/knowledge/base.py | 知识库 | ~100 |
| Blueprint/templates/registry.py | 模板市场 | ~80 |
| Blueprint/api/public.py | 开放平台 API | ~120 |
| Blueprint/collaboration/session.py | 协作会话 | ~150 |

### 6.3 修改文件清单

| 文件 | 改动 |
|------|------|
| Blueprint/agents/graph.py | deliver_node 加快照保存 |
| Blueprint/agents/developer.py | 加 trace 记录 |
| Blueprint/agents/tester.py | 加 trace 记录 |
| Blueprint/agents/reviewer.py | 加 trace 记录 |
| Blueprint/api/projects.py | 新增 7 个端点 |
| Blueprint/api/settings.py | 新增 webhook 端点 |
| Blueprint/api/websocket.py | 新增协作消息处理 |
| Blueprint/utils/memory.py | 新增 AgentTrace 类 |
| requirements.txt | 新增 click, chromadb, httpx, pyyaml |

---

## 7. 实施路线图

### 第一批：核心体验增强（1.5 周）

可并行 Task 组：

```
并行组 A（无依赖）:
  Task 1-2: trace_db + Agent trace 记录 + API
  Task 3-4: quality_scorer（AST 分析）+ API + 缓存
  Task 5-6: security_scanner（包装 bandit）+ API

并行组 B（依赖组 A）:
  Task 7-8: 前端组件 + 集成 + 测试
```

| 功能 | 工作量 | 优先级 |
|------|--------|--------|
| Agent 思考过程可视化 | 2 天 | P1（零风险，纯追加） |
| 代码质量评分（AST 分析） | 2 天 | P1 |
| 代码安全扫描（bandit + npm audit） | 2 天 | P1 |
| 前端集成 + 测试 | 2 天 | P1 |

**交付物：** 项目完成后有质量评分、可看 Agent 思考过程、有安全报告

### 第二批：交付完整度 + 基础设施（2 周）

| 功能 | 工作量 | 优先级 |
|------|--------|--------|
| 变更历史对比（快照存项目外部） | 2 天 | P2 |
| deliver_node hook 链改造 | 1 天 | P2 |
| 项目文档自动生成 | 2 天 | P2 |
| 部署脚本生成 | 2 天 | P2 |
| Webhook 通知 + CLI | 2 天 | P2 |
| 前端架构重构（拆分 ProjectDetailPage） | 3 天 | P2 |

**交付物：** 完整交付物（代码+测试+文档+部署配置），支持通知和命令行

### 第三批：模板市场（1 周，可选）

| 功能 | 工作量 | 优先级 |
|------|--------|--------|
| 项目模板市场 | 3 天 | P3 |
| 全局错误处理 + Toast | 1 天 | P3 |

**已砍掉（P3）：** 知识库集成、API 开放平台、排行榜、多人协作 — 后续根据用户反馈决定是否做

---

## 8. 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 前端框架 | Vue 3 + Vite | 已有，轻量高效 |
| 状态管理 | Pinia | 已有，TypeScript 友好 |
| 路由 | Vue Router | 已有，支持 SPA |
| UI 组件 | 自定义 | 简洁风格，不依赖重型 UI 库 |
| 后端框架 | FastAPI | 已有，异步高性能 |
| Agent 编排 | LangGraph | 已有，图结构精确控制 |
| 沙箱 | subprocess + 超时 | MVP 够用，后续加 Docker |
| CLI | Click | Python CLI 标准库 |
| 安全扫描 | bandit（Python）+ npm audit（Node） | 专业工具，不自写正则 |

### 未来技术选型（第二批引入）

| 组件 | 选型 | 引入时机 |
|------|------|---------|
| 数据库 | PostgreSQL | 第二批，替代 SQLite |
| 缓存 | Redis | 第二批，LLM 响应缓存 + 限流 |
| 监控 | Prometheus + Grafana | 第三批，需要运维能力时 |

---

---

## 附录

- [冲突分析与规避方案](./2026-06-15-conflict-analysis.md) — 13 个新功能与现有代码的冲突点及规避方案

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| LLM 调用成本 | 多 Agent 多轮调用费用 | DeepSeek v4 flash 便宜（见成本模型），单项目 < $0.05 |
| 生成代码质量不稳定 | 用户信任度下降 | TDD 流程 + 多轮审查 + AST 质量评分 |
| 功能范围过大 | 开发周期过长 | 砍掉 P3（知识库/API平台/排行榜/协作），聚焦 Batch 1+2 |
| 前端重构风险 | 重构引入新 Bug | 先写测试，再重构，保持 100% 通过 |
| deliver_node 臃肿 | 追加功能破坏返回值 | hook 链模式，每个功能独立函数，有回归测试 |

### LLM 成本模型

| 场景 | LLM 调用次数 | 平均 token/次 | DeepSeek 成本 |
|------|-------------|--------------|--------------|
| 简单需求（跳过 PM） | 5 次（Dev→Test→Review×1-2轮） | 2,000 | ~$0.005 |
| 复杂需求（全流程） | 9-15 次 | 2,500 | ~$0.02-0.04 |
| Proposer-Critic 开启 | +4 次 | 1,500 | +$0.006 |
| **月度预算（10 项目/天）** | — | — | **~$10-15** |

DeepSeek v4 flash 单价：输入 $0.27/M tokens，输出 $1.10/M tokens。多轮调用不是成本瓶颈。

---

## 11. 成功指标

| 指标 | 目标 | 衡量方式 |
|------|------|---------|
| 需求到可运行代码 | < 3 分钟 | 端到端计时 |
| 代码可用率 | > 80% | 生成后改几行就能跑 |
| 交付完整度 | 100% | 每次都带测试+文档+部署配置 |
| 用户满意度 | > 4.0/5 | 内测反馈 |
| 安全扫描通过率 | > 90% | 无 Critical/High 问题 |
