# Blueprint 项目总结（2026-06-15~16）

> 本文档整合产品设计、功能扩展、代码审查、实施进度、简历写法

---

## 一、产品定位

**Blueprint** — 面向 2-5 人小团队的 AI 全栈开发平台。

| 维度 | 定义 |
|------|------|
| 目标用户 | 2-5 人小团队（创业公司、工作室） |
| 核心价值 | 一句话需求 → 完整可运行的 Web 项目 |
| 差异化 | 交付完整度 + 人机协作 + 存量项目兼容 |
| 成功标准 | 质量优先——生成的代码改几行就能用 |

**三模式架构：**
- 全栈工程师（默认主模式）— 完整 Agent 链路
- 代码工厂（快捷入口）— 模板秒级生成
- 技术顾问（快捷入口）— 架构选型咨询

---

## 二、已完成功能

### 核心链路（5 Agent 协作）

```
PM → Architect → [人工确认] → Developer(工具循环) → Tester → Reviewer → [人工确认] → 交付
```

### 后端模块（15 个）

| 模块 | 文件 | 说明 |
|------|------|------|
| 质量评分 | utils/quality_scorer.py | AST 分析 5 维度，满分 100 |
| 安全扫描 | utils/security_scanner.py | bandit + npm audit + 自定义密钥检测 |
| 变更对比 | utils/diff_engine.py | gzip 压缩快照 + unified_diff |
| Agent Trace | utils/trace_db.py | SQLite 存储 prompt/response/工具链 |
| 文档生成 | utils/doc_generator.py | README + API 文档 + Mermaid 架构图 |
| 部署配置 | utils/deploy_generator.py | Dockerfile + docker-compose + start.sh |
| 费用追踪 | utils/cost_tracker.py | contextvars 并发隔离 + DeepSeek 定价 |
| Webhook | utils/webhook.py | HMAC-SHA256 + 事件过滤 |
| CLI | cli.py | list / status / download 命令 |
| 记忆层 | utils/memory.py | 项目持久化 + 刷新恢复 |
| 注入防护 | utils/guard.py | 28 条规则检测 |
| LLM 封装 | utils/llm.py | retry + 异步 + 超时 + 费用记录 |
| 日志 | utils/logger.py | 结构化日志 |
| 配置 | config.py | pydantic-settings + 3 个开关 |
| 工具执行 | agents/tool_executor.py | 模块级回调 + 路径安全 + ruff linter |

### 前端（6 个组件）

| 组件 | 说明 |
|------|------|
| QualityScore.vue | 质量评分雷达图 + 进度条 |
| SecurityReport.vue | 安全扫描结果 |
| DiffViewer.vue | 迭代间 diff 对比 |
| AgentTracePanel.vue | Agent 思考过程 |
| ToolProgress.vue | 实时工具进度 |
| OutputPanel.vue | 文件预览/下载 |

### API 端点（24 个）

项目 14 + 认证 2 + 设置 7 + WebSocket 1

### 测试覆盖

| 类型 | 数量 |
|------|------|
| 后端 | 362 |
| 前端 | 91 |
| **合计** | **453** |

---

## 三、Agent 架构设计

### 四层可靠性架构

| 层 | 职责 | 实现 |
|----|------|------|
| L1 结构化定义 | Agent 输出格式约束 | Pydantic schema + 工具 JSON schema |
| L2 推理策略 | Agent 思考方式 | prompt 正负例 + 错误恢复指引 + 每轮决策框架 |
| L3 执行护栏 | 输入/输出安全 | 注入检测 + 路径校验 + 工具权限最小化 |
| L4 自愈修复 | 错误恢复 | 重试计数 + 路由降级 + 超时保护 + 用户兜底 |

### 5 个 Agent 角色

| Agent | 输入 | 输出 | 工具 |
|-------|------|------|------|
| PM | 用户需求 | user_stories + features | 无（纯推理） |
| Architect | user_stories | architecture + api_definitions + data_models | 无（纯推理） |
| Developer | 架构 + 需求 | files（代码） | file_write / file_read / execute_python / done |
| Tester | files + 需求 | test_passed + test_results | file_read / execute_python / done |
| Reviewer | files | review_approved + review_comments | file_read / run_linter / done |

### Agent 间通信

```
共享 State（TypedDict，35+ 字段）
├── PM 输出 → user_stories, features
├── Architect 读 user_stories → 输出 architecture, api_definitions
├── Developer 读 architecture → 输出 files, key_decisions
├── Tester 读 files → 输出 test_passed, test_results
├── Reviewer 读 files → 输出 review_approved, review_comments
└── 路由函数根据各 Agent 返回值决定下一步流向
```

### 工具调用循环

```
Developer 每步:
  1. LLM 绑定工具 → 返回 tool_calls
  2. 执行 file_write（写入磁盘）
  3. 执行 execute_python（沙箱验证）
  4. 结果回传 LLM
  5. LLM 判断：有 bug → 修复；没问题 → done
  6. 循环最多 8 步，每步 60s 超时
```

### 路由逻辑

```
route_by_complexity: 简单需求跳过 PM
route_after_pm: 成功→Architect / 错误→重试 / 超限→END
route_after_architect: 成功→human_confirm / 错误→重试
route_after_human: 确认→Developer / 拒绝→Architect / 停止→deliver
route_after_developer: 成功→Tester / 错误→重试(最多2次)→用户决策
route_after_test: 通过→Reviewer / 失败→Developer / 超限→直接交付
route_after_review: 通过→deliver / 不通过→Developer / 架构问题→Architect
```

### Hook 链（交付后自动执行）

```
deliver_node → 写文件 → meta.json → hook 链:
  ├── save_snapshot_hook      (快照到外部目录)
  ├── quality_score_hook      (AST 质量评分并缓存)
  ├── security_scan_hook      (安全扫描并缓存)
  ├── generate_docs_hook      (README/API/架构图)
  ├── generate_deploy_hook    (Dockerfile/docker-compose)
  └── webhook_hook            (项目完成通知)
```

每个 hook 独立 try/except，失败只打日志不影响交付。

---

## 四、典型问题与解决方案

### 1. LangGraph state 残留导致死循环

**现象：** Developer 成功后路由函数仍判为失败，无限重试。
**根因：** LangGraph state 合并是补丁式——返回的字段更新，没返回的保留旧值。Developer 成功时不返回 error，旧值残留。
**解决：** 每个 Agent 成功路径显式返回 `"error": None`。

### 2. Developer 只写 1 个文件

**现象：** 前端项目所有代码塞在一个 index.html 里。
**根因：** MAX_STEPS=5 + 15 行反馈噪音 → LLM 倾向"快速完成"。
**解决：** MAX_STEPS 5→8 + 反馈精简到 7 行 + prompt 加代码质量要求。

### 3. WebSocket 阻塞断链

**现象：** Agent 执行时前端断连。
**根因：** 同步 LLM 调用阻塞 asyncio 事件循环。
**解决：** `asyncio.to_thread()` 独立线程 + epoch 计数器防旧线程消息混乱。

### 4. Proposer-Critic 反效果

**现象：** 同模型互评，Critic 挑无关紧要的刺，9 次 LLM 调用质量没提升。
**解决：** 关闭讨论模式，Developer 改为"写→执行→修→再执行"，LLM 调用减少 44%。

### 5. Tester "0失败" 误判

**现象：** "全部通过（0失败）"被判为失败。
**根因：** 关键词匹配排除条件 `"0 失败"`（有空格）不匹配实际输出 `"0失败"`（无空格）。
**解决：** 用 regex 精确提取 `(\d+)\s*failed`。

---

## 五、简历写法

### 项目名称

**Blueprint — 多 Agent 协同 AI 全栈开发平台 | 独立开发**

### 技术栈

Python · FastAPI · LangGraph · Vue 3 · WebSocket · SQLite · ruff · bandit

### 项目描述

基于 LangGraph 的多 Agent 协同系统，用户输入一句话需求，5 个 AI Agent 自动协作生成完整可运行的 Web 项目（前端+后端+测试+文档+部署配置），关键节点人工确认。449 个测试全过。

### Agent 设计

- 设计四层可靠性架构保障 Agent 质量：L1 结构化定义（Pydantic schema 强校验输出）→ L2 推理策略（prompt 正负例 + 错误恢复指引）→ L3 执行护栏（注入检测 + 工具权限最小化）→ L4 自愈修复（重试计数 + 路由降级 + 用户兜底）
- 5 个 Agent 通过共享 State（TypedDict，35+ 字段）通信：PM 输出 user_stories → Architect 读取并输出 architecture → Developer 读取架构写代码 → Tester 读取代码跑测试 → Reviewer 读取代码审查，路由函数根据各 Agent 返回的 error/test_passed/review_approved 决定下一步流向
- Developer/Tester/Reviewer 采用工具调用循环：LLM 绑定 OpenAI function calling 格式工具 → 返回 tool_calls → 执行 → 结果回传 → 循环最多 8 步，每步 60s 超时保护。Developer 有 file_write/file_read/execute_python/done 四个工具，Tester 只有 file_read/execute_python/done（最小权限），Reviewer 只有 file_read/run_linter/done（纯审查）
- 设计 Hook 链架构：交付后自动执行质量评分、安全扫描、文档生成、部署配置、Webhook 通知，6 个 hook 独立 try/except，失败不影响交付

### 工程规范

- TDD 驱动开发，449 个测试（362 后端 + 91 前端）全过；外部 API 全量 Mock
- 模块级回调 + try/except 兜底：新功能通过 hook 链/工具回调零风险接入，失败只打日志不影响主流程
- 安全防护四层：输入注入检测 + 工具路径校验 + 沙箱隔离 + bandit/npm audit 扫描；敏感文件（.env/.git/配置）黑名单实时拦截
- 3 轮代码审查（3 Critical + 15 Important + 10 Minor 全部修复），每个功能有配置开关可独立回滚

---

## 六、待办清单

| 优先级 | 功能 | 工作量 | 状态 |
|--------|------|--------|------|
| P1 | MemorySaver → SQLite | 1 天 | ⏸ 暂缓（架构债务） |
| P1 | 一键部署 | 2 天 | ⏸ 暂缓 |
| P2 | 前端 ProjectDetailPage 拆分 | 3 天 | ❌ 未做 |
| P2 | 全局 Toast 通知 | 1 天 | ❌ 未做 |
| P3 | 项目模板市场 | 3 天 | ❌ 未做 |
| P3 | 知识库集成 | 5 天 | ❌ 已砍 |
| P3 | API 开放平台 | 5 天 | ❌ 已砍 |
| P3 | 排行榜 | 3 天 | ❌ 已砍 |
| P3 | 多人协作 | 5 天 | ❌ 已砍 |

---

## 七、文档索引

| 文档 | 路径 |
|------|------|
| 产品设计 | `docs/superpowers/specs/2026-06-15-blueprint-product-design.md` |
| 冲突分析 | `docs/superpowers/specs/2026-06-15-conflict-analysis.md` |
| P0 设计 | `docs/superpowers/specs/2026-06-16-p0-features-design.md` |
| Batch 1 计划 | `docs/superpowers/plans/2026-06-15-batch1-core-experience.md` |
| P0 实施计划 | `docs/superpowers/plans/2026-06-16-p0-features.md` |
| 功能扩展 | `mimohouduan.md` |
| 企业级方案 | `mimo xiufu.md` |
| 开发日志 | `blueprint/DEVLOG.md`（3633 行） |
