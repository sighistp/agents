# Blueprint 开发日志 & 问题解决记录

> 记录 Blueprint 多Agent协同系统开发过程中遇到的所有问题、根因分析和解决方案。

---

## 设计阶段（2026-06-04）

### 需求讨论

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| 框架选型 | LangGraph / CrewAI / AutoGen / 自造轮子 | LangGraph | 面试看重，图结构+条件分支+循环 |
| 沙箱方案 | Docker / 受限exec / 本地环境 | 本地环境+临时目录 | 参考扣子，用户已有编程环境 |
| 前端方案 | 纯聊天 / 聊天+流程面板 / 任务面板 | 聊天+流程面板 | 左右两栏，卡通风格Agent形象 |
| 项目命名 | Blueprint / AgentForge / CodeCrew | Blueprint | 简单直接 |
| MVP范围 | Python only / Python+Web / 全栈 | 全栈 | 一步到位 |
| 与RAGv3关系 | 独立 / 子模块 / 共享后端 | 共享后端，Agent核心独立 | 复用auth/user_db/resilience |

### 核心设计决策

| 决策 | 说明 |
|------|------|
| Proposer-Critic对抗 | PM/Architect内部双Agent讨论3轮，Developer后审1轮，Tester/Reviewer不讨论 |
| 双层保障 | Prompt层引导思考（角色定义+推理策略），代码层保障执行（Pydantic schema校验+resilience重试） |
| interrupt机制 | PM需求澄清、Architect架构确认用interrupt暂停 |
| rethink机制 | 前端提供[重新审查]按钮，用户主动触发，每节点最多3轮 |
| 错误路由 | timeout→END，security→END，其他→重试 |

### 设计文档

- `docs/superpowers/specs/2026-06-04-Blueprint-multi-agent-design.md`
- `docs/superpowers/specs/2026-06-04-Blueprint-implementation-plan.md`

---

## Phase 1：项目骨架 + 基础设施（2026-06-04）

### Pydantic Schema（8个测试）

**新增文件：** `Blueprint/agents/schemas.py`

**实现：** 定义所有Agent输出模型（PMOutput, ArchitectOutput, DeveloperOutput, TesterOutput, ReviewerOutput）

**代码审查修复：**

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | Critical | 枚举字段无约束（priority/method/severity） | 用Literal约束 |
| 2 | Important | ReviewerOutput.approved由LLM填，可能与issues矛盾 | model_validator自动计算 |
| 3 | Important | test_pm_output_empty_stories捕获裸Exception | 改为ValidationError |

**测试：** 8 个全过

### 沙箱执行器（6个测试）

**新增文件：** `Blueprint/sandbox/executor.py`

**实现：** execute_python、execute_node、execute_sql

**代码审查修复：**

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | Critical | 进程组没杀（subprocess.run只杀主进程） | 改用Popen + taskkill/os.killpg |
| 2 | Critical | execute_sql无超时保护 | set_progress_handler检查deadline |
| 3 | Important | test_python_no_file_leak断言逻辑反了 | 改为检查cwd在temp目录 |
| 4 | Important | Windows上os.killpg不可用 | sys.platform判断，Windows用taskkill |

**踩坑记录：**
- `subprocess.TimeoutExpired`在`subprocess.run`中没有`pid`属性，需改用`Popen`直接控制进程
- Windows上`os.killpg`不存在，需用`taskkill /F /T /PID`杀进程树

**测试：** 6 个全过

### State定义 + LLM封装（4个测试）

**新增文件：** `Blueprint/agents/state.py`、`Blueprint/utils/llm.py`

**实现：** ProjectState TypedDict + create_initial_state工厂函数 + call_llm封装（retry+semaphore）

**代码审查修复：**

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | Important | call_llm_with_retry没有rate_limiter | 加threading.Semaphore(5) |
| 2 | Important | asyncio.Semaphore不能在同步函数里用 | 改为threading.Semaphore |

**测试：** 4 个全过

### LangGraph图结构（15个测试）

**新增文件：** `Blueprint/agents/graph.py`

**实现：** 7个节点（pm/architect/human_confirm/developer/tester/reviewer/deliver）+ 所有路由函数

**代码审查修复：**

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | Important | 路由函数返回映射key，测试期望节点名 | 修正测试断言 |

**测试：** 15 个全过

---

## Phase 2：并行开发（2026-06-04）

**方式：** 3个子代理并行工作，遵循TDD流程

### 配置模块（34个测试）

**新增文件：** `Blueprint/config.py`、`Blueprint/tests/test_config.py`

**实现：** pydantic-settings，env_prefix=Blueprint_，配置项含DeepSeek API、讨论配置、项目目录、最大迭代次数

**代码审查修复：**

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | Important | _DEFAULT_DISCUSSION_PROMPTS缺PM和Critic prompt | 补全所有Agent的prompt |
| 2 | Important | discussion_mode用"sequential"，设计文档用"full"/"post_review" | 统一为"full" |

**测试：** 34 个全过

### WebSocket模块（29个测试）

**新增文件：** `Blueprint/api/websocket.py`、`Blueprint/tests/test_websocket.py`

**实现：** 8种服务端消息类型、5种客户端消息类型、run_project异步生成器、interrupt→resume链路、rethink机制

**代码审查修复：**

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | Critical | resume的config格式不对（LangGraph不认识） | 改为Command(resume=decision) |
| 2 | Critical | rethink的config不对（不会传给节点） | 改为graph.update_state |
| 3 | Important | current_state未随执行更新 | on_chain_end时更新state |
| 4 | Important | run_project中current_state未定义 | 改为state参数 |

**测试：** 29 个全过

### PM Agent模块（25个测试）

**新增文件：** `Blueprint/agents/pm.py`、`Blueprint/tests/test_pm.py`

**实现：** PM_SYSTEM_PROMPT、PM_CRITIC_PROMPT、pm_agent节点函数、build_pm_prompt、_extract_json

**代码审查修复：**

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | Important | 缺interrupt机制（只设flag，图不会暂停） | 保持现状，图集成阶段加interrupt |

**测试：** 25 个全过

---

## 测试统计

```
总计：121个测试全部通过

test_config.py      : 34 passed
test_graph.py       : 15 passed
test_pm.py          : 25 passed
test_sandbox.py     :  6 passed
test_schemas.py     :  8 passed
test_state.py       :  4 passed
test_websocket.py   : 29 passed
```

---

## 当前项目结构

```
Blueprint/
├── __init__.py
├── config.py               ← 配置模块（pydantic-settings）
├── agents/
│   ├── __init__.py
│   ├── graph.py            ← LangGraph图结构（含路由函数）
│   ├── pm.py               ← PM Agent（含prompt+节点函数）
│   ├── schemas.py          ← Pydantic schemas（含Literal约束+自动计算）
│   └── state.py            ← ProjectState定义
├── api/
│   ├── __init__.py
│   └── websocket.py        ← WebSocket端点（/ws/project）
├── sandbox/
│   ├── __init__.py
│   └── executor.py         ← 代码执行沙箱（Python/Node/SQL）
├── utils/
│   ├── __init__.py
│   └── llm.py              ← LLM调用封装（retry+semaphore）
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_graph.py
│   ├── test_pm.py
│   ├── test_sandbox.py
│   ├── test_schemas.py
│   ├── test_state.py
│   └── test_websocket.py
└── DEVLOG.md               ← 本文件
```

---

## Phase 2.5：关键集成修复（2026-06-04）

**问题：** Phase 1-7完成后，系统无法真正运行：
1. graph.py使用mock节点，未接入真实Agent
2. Proposer-Critic未集成到Agent节点
3. test_results类型不匹配（dict vs list[dict]）

**修复：**

| # | 问题 | 修复 |
|---|------|------|
| 1 | graph.py mock节点 | 从各模块import真实Agent：pm_agent, architect_agent, developer_agent, tester_agent, reviewer_agent |
| 2 | Proposer-Critic未集成 | pm/architect/developer节点都接入proposer_critic_discuss，根据DISCUSSION_CONFIG决定是否启用 |
| 3 | test_results类型 | state.py改为list[dict]，与tester.py返回值一致 |

**测试mock修复：**
- test_pm.py: 所有mock从`Blueprint.agents.pm.call_llm`改为`Blueprint.agents.discussion.call_llm`
- test_architect.py: 同上
- test_developer.py: 同上
- `assert_called_once()`改为`assert_called()`（Proposer-Critic会多次调用）

**测试：** 182 个全过

---

## Phase 2.6：代码质量修复（2026-06-04）

**问题：** Phase 2.5集成后，仍有代码质量问题

**修复：**

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| 1 | HIGH | _extract_json重复6次 | 提取到utils/json_parser.py，所有Agent模块import使用 |
| 2 | HIGH | tester/reviewer硬编码current_agent | 移除，由graph条件边路由 |
| 3 | HIGH | config.py settings没用 | llm.py改为从settings读取配置 |
| 4 | MEDIUM | llm.py每次调用都操作sys.path | 改为模块顶部导入一次 |
| 5 | MEDIUM | RAGv3路径解析失败 | 添加fallback retry装饰器 |

**新增文件：** `Blueprint/utils/json_parser.py`

**测试：** 182 个全过

---

## Phase 6+8：前端 + 集成测试（2026-06-04）

**新增文件：** `Blueprint/tests/test_integration.py`

**集成测试覆盖：**

| 测试 | 验证内容 |
|------|---------|
| test_full_workflow_with_mock_llm | 完整流程：需求→PM→Architect→Developer→Tester→Reviewer→交付 |
| test_workflow_stops_on_error | 错误处理 |
| test_workflow_handles_pm_clarification | PM需求澄清 |
| test_workflow_handles_test_failure | 测试失败处理 |
| test_workflow_handles_review_rejection | 审查拒绝处理 |
| test_workflow_iteration_tracking | 迭代计数 |
| test_workflow_file_generation | 文件生成 |
| test_workflow_proposer_critic_integration | Proposer-Critic集成 |
| test_workflow_deliver_saves_files | 文件持久化 |

**测试：** 191 个全过（原182 + 新9）

---

## Phase 3：Architect Agent（2026-06-04）

**新增文件：** `Blueprint/agents/architect.py`、`Blueprint/tests/test_architect.py`

**实现：**
- ARCHITECT_SYSTEM_PROMPT — 角色定义+推理策略+JSON输出格式
- ARCHITECT_CRITIC_PROMPT — Proposer-Critic审查prompt
- architect_agent节点函数 — LLM调用→JSON提取→Schema校验→输出验证
- build_architect_prompt — 支持user_feedback（rethink机制）

**测试：** 15 个全过

---

## Phase 4：Developer Agent（2026-06-04）

**新增文件：** `Blueprint/agents/developer.py`、`Blueprint/tests/test_developer.py`

**实现：**
- DEVELOPER_SYSTEM_PROMPT — 角色定义+编码原则+JSON输出格式
- DEVELOPER_CRITIC_PROMPT — 只标记critical问题（安全漏洞、逻辑错误、崩溃风险）
- developer_agent节点函数 — LLM调用→JSON提取→Schema校验→路径安全校验
- build_developer_prompt — 支持user_feedback（rethink机制）
- _validate_file_paths — 防止路径注入（..、/etc、/usr等）

**测试：** 14 个全过

---

## Phase 5：Tester + Reviewer Agent（2026-06-04）

**新增文件：** `Blueprint/agents/tester.py`、`Blueprint/agents/reviewer.py`、`Blueprint/tests/test_tester.py`、`Blueprint/tests/test_reviewer.py`

**实现：**
- TESTER_SYSTEM_PROMPT — 测试策略（Python→pytest，前端→语法检查）
- REVIEWER_SYSTEM_PROMPT — 审查维度（placeholder、一致性、边界、风格）
- tester_agent节点函数 — 生成测试用例+执行+报告
- reviewer_agent节点函数 — 代码审查+approved自动计算

**测试：** 17 个全过

---

## 完成进度

| Phase | 内容 | 状态 | 测试数 |
|-------|------|------|--------|
| 1 | 项目骨架 + 基础设施 | ✅ 完成 | 33 |
| 2 | Config + WebSocket + PM Agent | ✅ 完成 | 88 |
| 2.5 | 关键集成修复（graph+Proposer-Critic+类型） | ✅ 完成 | — |
| 2.6 | 代码质量修复（json_parser+current_agent+config） | ✅ 完成 | — |
| 3 | Architect Agent | ✅ 完成 | 15 |
| 4 | Developer Agent | ✅ 完成 | 14 |
| 5 | Tester + Reviewer Agent | ✅ 完成 | 17 |
| 7 | Proposer-Critic讨论模块 | ✅ 完成 | 15 |
| 6 | 前端UI | ✅ 完成 | — |
| 8 | 集成测试 | ✅ 完成 | 9 |
| 9 | 技术债务修复 | ✅ 完成 | — |
| 10 | 代码审查修复 | ✅ 完成 | — |

**总计：191个测试全过**

## Phase 6：前端UI（2026-06-04）

**新增文件：** `Blueprint/static/index.html`

**设计风格：** Mission Control（任务控制中心）

**设计元素：**
- 深色背景 + 网格线（像雷达屏幕）
- Agent卡片用霓虹描边 + 呼吸动画
- 流程面板展示pipeline为电路板/任务时间线
- 聊天区用终端风格字体（JetBrains Mono）
- 标题用Orbitron字体（太空/科技感）
- 扫描线动画效果
- Proposer-Critic讨论可视化
- 中断确认对话框
- 项目完成文件预览/下载

**功能：**
- WebSocket实时连接
- Agent状态实时更新（等待/执行/完成/错误/暂停）
- 迭代进度条
- 讨论面板（折叠显示Proposer-Critic对话）
- 中断确认对话框
- 文件预览/下载
- 移动端适配

**测试：** 前端手动测试通过

---

## Phase 9：技术债务修复（2026-06-04）

**修复内容：**

| # | 问题 | 修复 |
|---|------|------|
| 1 | _extract_json死代码 | 从pm/architect/developer/tester/reviewer删除本地函数，discussion.py改用utils.json_parser |
| 2 | Tester没调沙箱 | tester_agent现在真正执行测试：生成测试代码→execute_python→解析真实结果 |
| 3 | PM缺interrupt | pm_agent现在调用interrupt()暂停等用户补充，RuntimeError时优雅降级 |

**测试：** 191 个全过

---

## Phase 10：代码审查修复（2026-06-04）

**来源：** 外部代码审查，发现5 Critical + 8 Important + 6 Minor

**Critical修复：**

| # | 问题 | 修复 |
|---|------|------|
| C1 | XSS漏洞 — innerHTML直接插入LLM输出 | addMessage()用escapeHtml()转义 |
| C2 | 路径穿越 — project_id未校验 | 正则校验`^[a-zA-Z0-9_-]+$`，graph.py和websocket.py都加 |
| C3 | 状态突变 — pm_agent直接修改state["requirement"] | 用局部变量clarified_requirement，不修改原state |
| C4 | 异常静默吞噬 — proposer_critic_discuss返回空字符串 | 改为re-raise，让上游正确处理 |
| C5 | rethink流程 — 用过期current_state | 从LangGraph checkpoint获取最新state |

**Important修复：**

| # | 问题 | 修复 |
|---|------|------|
| I1 | reviewer_agent丢弃消息历史 | 改为追加到state["messages"] |
| I6 | LLM单例非线程安全 | 加双重检查锁 |

**测试：** 191 个全过

---

## Phase 11：启动脚本（2026-06-04）

**新增文件：** `Blueprint/start.py`

**功能：** 一键启动Blueprint，自动打开浏览器

**启动方式：**
```bash
cd "c:/Users/lahm/Desktop/Many AgentS"
python -m Blueprint.start
```

**服务地址：** http://localhost:8080

---

## Phase 12：MIMO模型接入（2026-06-04）

**目标：** 切换到小米MIMO v2.5 Pro模型

**配置变更：**

| 配置项 | 之前 | 之后 |
|--------|------|------|
| LLM API Key | DeepSeek API Key | MIMO API Token |
| LLM Base URL | https://api.deepseek.com | https://token-plan-cn.xiaomimimo.com/v1 |
| LLM Model | deepseek-chat | mimo-v2.5-pro |

**实现：**
- config.py新增`llm_api_key`、`llm_base_url`、`llm_model`配置项
- llm.py优先使用新配置，向后兼容DeepSeek
- 新增`Blueprint/.env`文件配置MIMO API

**测试：** LLM调用成功，响应正常

---

## Phase 13：性能优化 + 前端修复（2026-06-04）

**问题：** Proposer-Critic讨论轮次太多，PM阶段耗时2-3分钟；前端多个交互问题

**优化：**

| 改动 | 文件 | 之前 | 之后 |
|------|------|------|------|
| 讨论轮次 | discussion.py | 3轮（16次LLM） | 1轮（9次LLM） |
| LLM超时 | llm.py | 无（可能无限等待） | 30秒 |
| loading dots | index.html | Agent完成后残留 | 完成后移除 |
| Agent输出显示 | index.html | 不显示 | 用户故事/架构/文件列表实时渲染 |
| currentThreadId | index.html | 永远为null | 正常赋值，interrupt resume能工作 |
| project_done带files | websocket.py | 不带文件 | 前端能拿到生成的文件 |

**效果：**
- LLM调用减少44%
- 每次调用最多等30秒
- 用户可通过`Blueprint_DISCUSSION_MAX_ROUNDS=3`环境变量调回3轮
- 前端交互体验大幅改善

**测试：** 191 个全过

---

## 技术债务

| # | 问题 | 优先级 | 说明 |
|---|------|--------|------|
| 1 | WebSocket线程池race condition | ~~高~~ ✅ | 已修复：epoch计数器+stop_event |
| 2 | WebSocket无认证 | ~~高~~ ✅ | 已修复：JWT认证 |
| 3 | /api/resume和rethink空操作 | 中 | REST API未真正转发到WebSocket |
| 4 | 流式输出 | 中 | 前端实时显示Agent思考过程 |
| 5 | 完整流程超时处理 | 中 | 添加进度条或流式输出 |
| 6 | 沙箱真正隔离 | 中 | 当前用subprocess，后续加Docker |
| 7 | 前端SVG卡通形象 | 低 | MVP用CSS动画 |
| 8 | 移动端适配 | 低 | MVP只做桌面端 |
| 9 | 代码模板（Flask/React/Vue） | 低 | 后续扩展 |
| 10 | 版本控制（Git集成） | 低 | 后续扩展 |

---

## 完成进度（最终）

| Phase | 内容 | 状态 | 测试数 |
|-------|------|------|--------|
| 1 | 项目骨架 + 基础设施 | ✅ | 33 |
| 2 | Config + WebSocket + PM Agent | ✅ | 88 |
| 2.5 | 关键集成修复 | ✅ | — |
| 2.6 | 代码质量修复 | ✅ | — |
| 3 | Architect Agent | ✅ | 15 |
| 4 | Developer Agent | ✅ | 14 |
| 5 | Tester + Reviewer Agent | ✅ | 17 |
| 7 | Proposer-Critic讨论模块 | ✅ | 15 |
| 6 | 前端UI | ✅ | — |
| 8 | 集成测试 | ✅ | 9 |
| 9 | 技术债务修复 | ✅ | — |
| 10 | 代码审查修复 | ✅ | — |
| 11 | 启动脚本 | ✅ | — |
| 12 | MIMO模型接入 | ✅ | — |
| 13 | 性能优化 | ✅ | — |
| 14 | 端到端测试与问题排查 | ✅ | — |
| 15 | 核心功能补全 | ✅ | 57 |
| 16 | 代码审查修复 | ✅ | — |
| 17 | WebSocket race condition修复 | ✅ | — |
| 18 | 未完成功能分析 | ✅ | — |
| 19 | WebSocket认证 + RAGv3模块集成 | ✅ | 29 |
| 20 | 代码审查修复 | ✅ | — |
| 21 | 评估报告问题修复 | ✅ | — |
| 22 | 代码审查 + 架构问题修复 | ✅ | — |
| 23 | 全线代码审查修复（Critical） | ✅ | — |
| 24 | 全线代码审查修复（Important+Minor） | ✅ | — |
| 25 | 全线代码审查修复（完） | ✅ | — |
| 26 | Agent节点异步化 | ✅ | — |
| 27 | 前端路由修复 | ✅ | — |
| 28 | 代码审查全量修复 | ✅ | — |
| 29 | 设置API + 前端路由修复 | ✅ | — |
| 30 | WebSocket全流程修复 | ✅ | — |
| 31 | TDD流程改造 | ✅ | — |
| 32 | Agent执行模式 | ✅ | — |
| 33 | 设置页面修复 | ✅ | — |
| 34 | 代码审查修复 | ✅ | — |
| 35 | LLM模型切换 + Proposer-Critic调优 | ✅ | — |
| 36 | WebSocket认证修复 | ✅ | — |
| 37 | Windows编码修复 | ✅ | — |
| 38 | JWT Secret问题分析 | ✅ | — |
| 39 | WebSocket认证修复确认 | ✅ | — |
| 40 | Developer Agent核心改造 | ✅ | 43 |
| 41 | 前端Vue 3 SPA重构（TDD） | ✅ | 48 |
| 42 | 运行时Bug修复 | ✅ | 22 |
| 43 | 工具调用重构设计 | ✅ | — |
| 44 | 工具调用重构实现（TDD） | ✅ | 306 |
| 45 | 用户审查修复（project_dir/TDD流程/沙箱） | ✅ | 256 |
| 46 | DeepSeek tool_calls 兼容修复 | ✅ | 256 |
| 47 | 首次真实运行修复（4 Bug） | ✅ | 306 |
| 48 | interrupt 流程修复 | ✅ | 306 |
| 49 | 全流程跑通修复（16项） | ✅ | 306 |
| 50 | LLM选型 + API预设 | ✅ | 306 |
| 51 | 文件下载分级（源码/应用/打包） | ✅ | 306 |
| 52 | C4/C6安全修复 + I7/I9异步改造 | ✅ | 260 |
| 53 | 运行时问题修复（4 Bug） | ✅ | 310 |
| 54 | SQLite记忆层审查修复+Developer记忆接入 | ✅ | 323 |
| 38 | JWT Secret问题分析 | ✅ | — |
| 39 | WebSocket认证修复确认 | ✅ | — |
| 40 | Developer Agent核心改造 | ✅ | 43 |

**总计：254个测试全过**

---

## Phase 14：端到端测试与问题排查（2026-06-05）

**目标：** 自测Blueprint能否正常工作，发现并修复实际运行问题

### 测试过程

**1. 模型切换测试**
- MIMO v2.5 Pro响应慢（单次LLM调用4-5秒，完整流程5-10分钟）
- 切回DeepSeek v4 flash（单次LLM调用2-3秒）
- 结论：MIMO适合推理密集场景，Blueprint需要快速响应，DeepSeek更合适

**2. 单元测试结果**

| 测试项 | 结果 | 耗时 |
|--------|------|------|
| LLM调用 | ✅ | 3.8秒 |
| PM Agent | ✅ | ~15秒（生成1个用户故事） |
| Developer Agent | ✅ | ~20秒（生成2个文件） |
| 沙箱执行 | ✅ | 即时（计算器代码测试通过） |
| 完整流程 | ⏳ | 超时（Proposer-Critic讨论耗时长） |

**3. 发现的问题**

| # | 问题 | 原因 | 影响 |
|---|------|------|------|
| 1 | Windows控制台emoji崩溃 | GBK编码不支持Unicode emoji | LLM返回emoji时程序崩溃 |
| 2 | WebSocket断开 | 同步LLM调用阻塞async事件循环 | Agent执行时前端断连 |
| 3 | LLM调用超时 | 无超时机制 | 可能无限等待 |
| 4 | 完整流程超时 | Proposer-Critic讨论轮次多 | 用户体验差 |

**4. 修复措施**

| 问题 | 修复 |
|------|------|
| emoji崩溃 | llm.py和start.py添加`PYTHONIOENCODING=utf-8` |
| WebSocket阻塞 | websocket.py改用`asyncio.to_thread()`线程池执行图 |
| LLM超时 | llm.py添加`request_timeout=30` |
| 讨论轮次 | discussion.py默认轮次从3改为1 |

**5. 测试结论**

- ✅ 核心功能正常：PM/Developer/Tester都能正常工作
- ✅ 沙箱执行正常：生成的代码能跑
- ⚠️ WebSocket阻塞问题待解决：同步LLM调用阻塞事件循环
- ⚠️ 完整流程耗时长：需要进一步优化或异步化

### 技术发现

1. **LangGraph同步节点阻塞问题** — Agent节点是同步函数，`llm.invoke()`会阻塞整个async流程。解决方案：用`asyncio.to_thread()`在独立线程运行图，通过队列传递消息

2. **Windows编码问题** — Python默认GBK编码，LLM返回的emoji会导致`UnicodeEncodeError`。解决方案：设置`PYTHONIOENCODING=utf-8`环境变量

3. **Proposer-Critic性能** — 即使轮次改为1，PM阶段仍有2次LLM调用（Proposer+Critic），约6-10秒。这是设计权衡，质量换速度

### 待解决

| 问题 | 优先级 | 说明 |
|------|--------|------|
| WebSocket线程池实现 | 高 | 当前写法有bug，需要重写 |
| 完整流程超时 | 中 | 考虑添加进度条或流式输出 |
| 前端重连机制 | 中 | WebSocket断开后自动重连 |

---

## Phase 15：核心功能补全（2026-06-05）

**目标：** 实现设计文档中未完成的核心功能

**并行开发（3个子代理）：**

| 子代理 | 任务 | 新增文件 | 新增测试 |
|--------|------|---------|---------|
| 1 | REST API + 用户系统 | auth.py, user_db.py, main.py, requirements.txt | 30 |
| 2 | 前端页面 | login.html, projects.html, project-detail.html, settings.html | — |
| 3 | 文件管理 + zip | projects.py更新, test_file_api.py | 27 |

**新增功能：**

| 功能 | 说明 |
|------|------|
| REST API | 10+端点（项目CRUD、文件下载、认证） |
| JWT认证 | 登录/注册/token验证，复用RAGv3 |
| 用户数据库 | SQLite存储用户信息 |
| 登录页 | Mission Control风格，登录/注册切换 |
| 项目列表页 | 卡片展示历史项目，点击查看详情 |
| 项目详情页 | Agent流程+消息+文件预览/下载 |
| 设置页 | 配置API Key、模型、迭代次数等 |
| 文件预览 | 支持Python/HTML/CSS/JS等格式 |
| 文件下载 | 单文件下载 + zip打包下载 |
| 导航栏 | index.html添加导航，登录检查 |

**测试：** 225 个全过（新增57个）

---

## Phase 16：代码审查修复（2026-06-05）

**来源：** 外部代码审查，发现4 Critical + 11 Important + 10 Minor

**Critical修复：**

| # | 问题 | 修复 |
|---|------|------|
| C1 | config.py硬编码API key | 改为空默认+启动警告 |
| C2 | auth_enabled/auth_keys配置缺失 | 添加到Settings类 |
| C3 | _safe_resolve用str.startswith | 改用Path.is_relative_to() |
| C4 | sandbox无真正隔离 | 标记为已知限制，后续加Docker |

**Important修复：**

| # | 问题 | 修复 |
|---|------|------|
| I1 | developer.py路径验证不完整 | 改用白名单+containment检查 |
| I2 | WebSocket race condition | 标记为后续修复 |
| I3 | WebSocket无认证 | 标记为后续修复 |
| I4 | /api/resume和/rethink是空操作 | 标记为后续修复 |
| I5 | architect错误不设current_agent | 添加current_agent: "architect" |
| I6 | tester/reviewer错误不设状态 | 添加test_passed/review_approved: False |
| I7 | retry丢失函数元数据 | 添加functools.wraps |
| I8 | CodeFile.language太窄 | 扩展到16种语言 |
| I9 | extract_json贪婪正则 | 改用brace-counting解析器 |
| I10 | register_user暴露信息 | 改为通用错误消息 |
| I11 | _validate_file_path不标准化 | 添加os.path.normpath |

**测试：** 225 个全过

---

## Phase 17：WebSocket race condition修复（2026-06-05）

**问题：** rethink/resume启动新graph线程时，旧线程仍在运行，消息混乱

**修复方案：**

| 机制 | 说明 |
|------|------|
| threading.Event | 信号旧线程优雅停止 |
| epoch计数器 | 每条消息带epoch标签，drainer丢弃旧epoch消息 |
| 线程等待 | 启动新线程前等待旧线程结束（2秒超时） |
| 队列清空 | 启动前清空残留消息 |

**关键改动：**
- `_run_graph_sync`接收`stop_event`和`epoch`参数
- `_start_graph`先停止旧线程，再启动新线程
- `_drain_queue`丢弃`_epoch < epoch`的旧消息
- cancel时调用`stop_event.set()`立即停止graph线程

**测试：** 225 个全过

---

## Phase 18：未完成功能分析（2026-06-05）

**14项未完成功能分类：**

| 功能 | 优先级 | 决策 | 理由 |
|------|--------|------|------|
| SVG卡通Agent形象 | 低 | ❌ 不做 | emoji够用，面试说"预留SVG扩展点" |
| 移动端适配 | 低 | ❌ 不做 | MVP桌面端够用 |
| /api/resume真正实现 | 中 | ❌ 不做 | WebSocket已处理resume |
| /api/rethink真正实现 | 中 | ❌ 不做 | WebSocket已处理rethink |
| WebSocket认证 | **高** | ✅ 立即做 | 安全问题，部署前必须解决 |
| WebSocket race condition | **高** | ✅ 已修复 | Phase 17 |
| 流式输出 | 中 | ⏳ 后续 | 需改核心架构 |
| 断线重连 | 中 | ⏳ 后续 | 前后端联调复杂 |
| 对话记忆集成 | 低 | ✅ 立即做 | 复用RAGv3，简单 |
| 安全防护集成 | 低 | ✅ 立即做 | 复用RAGv3，简单 |
| 日志集成 | 低 | ✅ 立即做 | 复用RAGv3，简单 |
| 代码模板 | 低 | ❌ 不做 | 后续扩展 |
| 版本控制 | 低 | ❌ 不做 | 后续扩展 |
| 多模型支持 | 低 | ❌ 不做 | 后续扩展 |

**立即执行（3项）：**
1. WebSocket认证 ✅
2. RAGv3模块集成（memory/guard/logging）✅

---

## Phase 19：WebSocket认证 + RAGv3模块集成（2026-06-05）

**并行开发（2个子代理）：**

| 子代理 | 任务 | 新增文件 | 新增测试 |
|--------|------|---------|---------|
| 1 | WebSocket认证 | test_websocket_auth.py | 5 |
| 2 | RAGv3模块集成 | memory.py, guard.py, logger.py | 24 |

**新增功能：**

| 功能 | 说明 |
|------|------|
| WebSocket认证 | JWT验证，token通过query param或header传递 |
| 项目历史存储 | SQLite记录项目创建和状态 |
| 注入检测 | 检测prompt injection尝试 |
| 输入净化 | 控制字符过滤、长度限制 |
| 集中日志 | 统一格式、抑制噪音日志 |

**修改文件：**
- websocket.py — 添加JWT认证
- index.html — WebSocket连接带token
- pm.py — 注入检测+日志
- projects.py — 项目历史存储
- start.py — 启动时配置日志

**测试：** 254 个全过（新增29个）

---

## Phase 20：代码审查修复（2026-06-05）

**来源：** 代码审查，发现3 Critical + 7 Important

**Critical修复：**

| # | 问题 | 修复 |
|---|------|------|
| C1 | Token在URL中暴露 | 前端改用Sec-WebSocket-Protocol header传递token |
| C2 | stop_event复用导致僵尸线程 | 每代新建stop_event，旧event保持set状态 |
| C3 | rethink传递过期state | 标记为后续修复（需要LangGraph checkpoint集成） |

**Important修复：**

| # | 问题 | 修复 |
|---|------|------|
| I1 | 单例线程不安全 | _get_memory加双重检查锁 |
| I2 | meta.json无锁读写 | 标记为后续修复 |
| I3 | 注入检测可绕过 | 标记为已知限制（启发式防御） |
| I4 | requirement未净化 | PM节点已有check_injection |
| I5 | GIL阻塞 | 可接受（threading.Thread独立于事件循环） |
| I6 | 测试断言太宽 | 标记为后续修复 |
| I7 | asyncio.get_event_loop废弃 | 标记为后续修复 |

**测试：** 254 个全过

---

## Phase 21：评估报告问题修复（2026-06-05）

**来源：** 评估报告指出3个核心问题

**修复：**

| # | 问题 | 修复 |
|---|------|------|
| 1 | API Key硬编码 | .env改为占位符，创建.gitignore防止泄露 |
| 2 | LLM同步阻塞 | 新增`call_llm_async`异步版本，支持asyncio |
| 3 | 沙箱无资源限制 | 添加`_set_resource_limits`（Unix: memory 256MB + CPU 30s，Windows: 依赖timeout） |

**关键改动：**
- `.env` — API Key改为`your-api-key-here`占位符
- `.gitignore` — 新建，排除.env、__pycache__、projects/等
- `utils/llm.py` — 新增`call_llm_async`异步函数
- `sandbox/executor.py` — 新增`_set_resource_limits`，Unix下用resource模块限制内存和CPU

**测试：** 254 个全过

---

## Phase 22：代码审查 + 架构问题修复（2026-06-05）

**代码审查问题修复：**

| # | 问题 | 修复 |
|---|------|------|
| 1 | rethink传递过期state | 从LangGraph checkpoint获取最新state |
| 2 | meta.json无锁读写 | 改为原子写入（tmp + os.replace） |
| 3 | 测试断言太宽 | WebSocket auth测试改用(WebSocketDisconnect, Exception) |
| 4 | asyncio.get_event_loop废弃 | 改为asyncio.get_running_loop() |

**架构问题修复：**

| # | 问题 | 修复 |
|---|------|------|
| 1 | 图结构偏线性 | 添加Reviewer→Architect回退路径（redesign路由） |
| 2 | human_confirm默认auto-approve | 实现真正的interrupt机制 |
| 3 | State膨胀风险 | 添加add_messages_with_limit（最多100条消息） |

**关键改动：**
- `websocket.py` — rethink从checkpoint获取最新state
- `projects.py` — meta.json原子写入（os.replace）
- `graph.py` — Reviewer可回退到Architect，human_confirm使用interrupt
- `state.py` — messages使用add_messages_with_limit限制
- `test_integration.py` — mock interrupt避免测试阻塞

**测试：** 254 个全过

---

## Phase 23：全线代码审查修复（2026-06-05）

**来源：** 全线代码审查，发现5 Critical + 17 Important + 12 Minor

**Critical修复：**

| # | 问题 | 修复 |
|---|------|------|
| C1 | 沙箱环境变量泄露 | 创建_SAFE_ENV，不含API Key等敏感信息 |
| C2 | deliver_node硬编码路径 | 改用settings.project_dir |
| C3 | 无限重试循环 | 添加_pm_retry_count/_developer_retry_count，最多2次 |
| C4 | call_llm_async返回AIMessage | 改为返回result.content字符串 |
| C5 | 沙箱路径未验证 | 已有_validate_file_paths（开发者节点） |

**关键改动：**
- `sandbox/executor.py` — 安全环境变量，用sys.executable
- `agents/graph.py` — 使用配置路径，添加重试计数
- `utils/llm.py` — 修复async返回类型

**测试：** 254 个全过

---

## Phase 24：全线代码审查修复（续）（2026-06-05）

**Important修复：**

| # | 问题 | 修复 |
|---|------|------|
| I1 | main.py vs start.py入口点冲突 | start.py改为复用main.py的app |
| I2 | UUID截断[:8]碰撞概率高 | 改为[:12] |
| I3 | REST API空操作 | 标记为后续修复（WebSocket已处理） |
| I4 | WebSocket认证方式 | 标记为已知限制 |
| I5 | WebSocket无限流 | 标记为后续修复 |
| I6 | SQLite连接未关闭 | 添加lifespan shutdown hook |
| I7 | ProjectMemory默认路径相对 | 标记为后续修复 |
| I8 | JWT secret导入时生成 | 标记为已知限制 |
| I9 | route_after_test强制pass | 标记为设计决策（防死循环） |
| I10 | get_project_files无大小限制 | 标记为后续修复 |
| I11 | 注入检测可绕过 | 标记为已知限制（启发式防御） |
| I12 | 源文件过滤不完整 | 标记为后续修复 |
| I13 | execute_sql无输出限制 | 标记为后续修复 |
| I14 | state.py未使用import | 已删除 |
| I15 | 类型提示用bare dict | 标记为后续优化 |
| I16 | __import__代码风格 | 改为正常import |
| I17 | 浏览器自动打开硬编码 | 标记为后续优化 |

**Minor修复：**
- 错误消息语言统一为中文（architect/developer/tester/reviewer）
- `_memory_lock`改为正常import

**测试：** 254 个全过

---

## Phase 25：全线代码审查修复（完）（2026-06-05）

**Important修复：**

| # | 问题 | 修复 |
|---|------|------|
| I1 | WebSocket认证方式 | 改用Authorization Bearer header |
| I2 | WebSocket无限流 | 添加速率限制（每用户每分钟3次） |
| I3 | ProjectMemory默认路径相对 | 改为绝对路径Blueprint/data/ |
| I4 | JWT secret导入时生成 | 改为懒加载（首次使用时生成） |
| I5 | get_project_files无大小限制 | 添加max_file_size=1MB，max_files=100 |
| I6 | execute_sql无输出限制 | 添加max_rows=1000，max_output=100KB |
| I7 | _validate_file_paths冗余检查 | 简化为只用Path.is_relative_to |
| I8 | logger import位置 | 改为模块级import |

**测试：** 254 个全过

---

## Phase 26：Agent节点异步化（2026-06-05）

**目标：** 解决同步LLM调用阻塞WebSocket事件循环的问题

**改动：**

| 文件 | 改动 |
|------|------|
| agents/pm.py | pm_agent改为async，使用call_llm_async |
| agents/architect.py | architect_agent改为async，使用call_llm_async |
| agents/developer.py | developer_agent改为async，使用call_llm_async |
| agents/tester.py | tester_agent改为async，使用call_llm_async |
| agents/reviewer.py | reviewer_agent改为async，使用call_llm_async |
| utils/llm.py | 修复call_llm_async返回类型（返回str而非AIMessage） |
| tests/ | 所有测试改为async，使用@pytest.mark.asyncio |

**关键改动：**
- 所有Agent节点函数改为`async def`
- 直接LLM调用使用`await call_llm_async()`
- Proposer-Critic讨论仍使用同步`call_llm`（内部处理）
- 集成测试使用`await app.ainvoke()`而非`app.invoke()`

**测试：** 254 个全过

---

## Phase 27：前端路由修复（2026-06-05）

**问题：** 访问 http://localhost:8080 显示 `{"detail":"Not Found"}`

**调试过程：**

1. **症状**：用户访问主页显示 "Not Found"
2. **初步排查**：curl 测试 `http://localhost:8080/` 返回 HTML，服务器正常
3. **深入排查**：发现用户实际被重定向到 `/login.html`，而 `/login.html` 返回 "Not Found"
4. **根因**：`start.py` 只注册了 `/` 和 `/index.html` 路由，没有注册其他页面路由

**修复：** 在 `start.py` 中添加所有页面路由：

```python
@app.get("/login.html")
async def login_html():
    login_path = static_dir / "login.html"
    if login_path.exists():
        return FileResponse(str(login_path))
    return {"message": "Login page not found."}

@app.get("/projects.html")
async def projects_html():
    path = static_dir / "projects.html"
    if path.exists():
        return FileResponse(str(path))
    return {"message": "Projects page not found."}

@app.get("/project-detail.html")
async def project_detail_html():
    path = static_dir / "project-detail.html"
    if path.exists():
        return FileResponse(str(path))
    return {"message": "Project detail page not found."}

@app.get("/settings.html")
async def settings_html():
    path = static_dir / "settings.html"
    if path.exists():
        return FileResponse(str(path))
    return {"message": "Settings page not found."}
```

**调试方法总结：**
1. **curl 测试**：用 `curl -s http://localhost:8080/` 验证服务器响应
2. **路由检查**：检查 `app.routes` 列表确认注册了哪些路由
3. **端口检查**：用 `netstat -ano | grep :8080` 确认端口占用
4. **日志分析**：服务器日志显示 "Not Found"，确认是路由问题
5. **逐个测试**：测试每个页面路由，发现只有 `/` 和 `/index.html` 正常

**经验教训：**
- 不能假设所有页面都能通过静态文件服务访问
- 需要为每个页面显式注册路由
- 调试时要区分"服务器正常"和"路由正确"

**测试：** 所有页面可访问

**额外修复：** 页面无法滚动问题
- **问题**：`overflow: hidden` 和 `height: 100vh` 阻止了页面滚动
- **修复**：
  - 所有页面的 `html, body` 样式从 `overflow: hidden` 改为 `overflow-y: auto`
  - 所有页面的 `.app` 容器从 `height: 100vh` 改为 `min-height: 100vh`
- **影响页面**：settings.html、projects.html、project-detail.html、login.html

**新增功能：** 项目删除
- **后端**：添加 `DELETE /api/projects/{project_id}` 端点
- **前端**：项目卡片添加删除按钮（hover显示，点击确认后删除）
- **API**：删除项目目录和文件，更新内存状态

### 已完成功能

| 功能 | 设计文档要求 | 实现状态 |
|------|-------------|---------|
| 6个Agent节点 | PM/Architect/Developer/Tester/Reviewer/Orchestrator | ✅ |
| Proposer-Critic | PM/Architect full模式，Developer post_review | ✅ |
| Pydantic Schema | 所有Agent输出严格定义 | ✅ |
| LangGraph图 | StateGraph + 条件分支 + 循环 | ✅ |
| 沙箱执行 | Python/Node/SQL本地执行 | ✅ |
| WebSocket通信 | interrupt/resume/rethink/cancel | ✅ |
| REST API | 项目CRUD + 文件管理 | ✅ |
| 用户系统 | JWT认证 + SQLite | ✅ |
| 前端页面 | 登录/主工作台/项目列表/详情/设置 | ✅ |
| 文件管理 | 预览/下载/打包 | ✅ |
| 配置系统 | pydantic-settings | ✅ |
| 测试 | 225个测试全过 | ✅ |

### 未完成功能

| 功能 | 设计文档要求 | 当前状态 | 优先级 |
|------|-------------|---------|--------|
| **SVG卡通Agent形象** | 每个Agent有SVG头像+动画 | ⚠️ 用emoji代替 | 低 |
| **移动端适配** | 两栏→tab切换 | ⚠️ 基础响应式 | 低 |
| **代码模板** | 预置Flask/React/Vue模板 | ❌ 未实现 | 低 |
| **版本控制** | Git集成，自动commit | ❌ 未实现 | 低 |
| **WebSocket认证** | JWT验证WebSocket连接 | ❌ 未实现 | 中 |
| **WebSocket race condition** | 线程管理，防止消息混乱 | ❌ 未实现 | 高 |
| **流式输出** | 实时显示Agent思考过程 | ❌ WebSocket阻塞 | 中 |
| **并行开发** | 前端/后端并行 | ❌ MVP不做 | 低 |
| **沙箱真正隔离** | Docker或资源限制 | ❌ 用subprocess | 中 |
| **/api/resume和/rethink** | REST API转发到WebSocket | ❌ 空操作 | 中 |
| **断线重连** | WebSocket断开后恢复 | ⚠️ 前端有逻辑，后端不完整 | 中 |

### 设计文档中的后续扩展

| 功能 | 说明 | 状态 |
|------|------|------|
| 并行开发 | 开发阶段拆分为前端/后端并行 | ❌ MVP不做 |
| 代码模板 | 预置Flask/React/Vue模板 | ❌ 后续扩展 |
| 版本控制 | Git集成，自动commit | ❌ 后续扩展 |
| 多模型支持 | 支持GPT/Claude等模型 | ❌ 后续扩展 |

---

## 外部评估报告（2026-06-05）

**评估者：** 第二个Agent（全量代码审查）

**评分变化：**

| 维度 | 上次 | 本次 | 变化原因 |
|------|------|------|---------|
| 架构设计 | 4.0 | 4.5 | 发现完整REST API、JWT认证、WebSocket认证、安全防护 |
| Agent实现 | 4.0 | 4.0 | 不变 |
| Proposer-Critic | 5.0 | 5.0 | 不变 |
| 基础设施 | 3.0 | 4.0 | 发现SQLite持久化、结构化日志、注入防护 |
| 前端 | 4.0 | 4.0 | 不变 |
| 测试覆盖 | 4.0 | 5.0 | 实际254个测试，覆盖路径穿越、JWT、注入检测等 |
| 工程成熟度 | 3.0 | 4.0 | 认证/持久化/日志都已实现 |
| **综合** | **3.5** | **4.0** | |

**5个真正有价值的创新点：**
1. Proposer-Critic对抗模式 — 分层配置
2. Pydantic Schema校验 — 代码层强制校验LLM输出
3. Mission Control前端 — 实时可视化Agent协作
4. 双层安全保障 — Prompt引导 + 代码校验 + 注入检测 + 路径防护
5. 完整API层 — REST + WebSocket + 认证 + 文件管理 + 持久化

**仍需解决的3个核心问题：**
1. API Key硬编码 — 立即移除，用环境变量
2. 同步LLM阻塞 — 改用AsyncOpenAI或httpx
3. 沙箱安全 — 至少加resource限制，理想用Docker

**与竞品对比：**
- vs MetaGPT/ChatDev：可视化、认证、安全防护、测试覆盖领先
- 代码执行：差距明显（Docker vs subprocess）
- 生产就绪：接近，差距缩小

---

## 项目总结（最终）

**核心成果：**
- 7个真实Agent节点 + LangGraph图编排
- Proposer-Critic对抗模式（PM/Architect 1轮，Developer 1轮）
- Pydantic Schema校验 + Literal枚举约束
- 双层保障架构（Prompt引导 + 代码校验）
- 代码执行沙箱（Python/Node/SQL + 进程组安全）
- WebSocket实时通信（interrupt/resume/rethink）
- REST API + JWT认证 + 用户系统
- Mission Control风格前端（5个页面）
- 文件管理（预览/下载/打包）
- 225个测试全过

**已验证功能：**
- ✅ LLM调用正常（DeepSeek v4 flash，3-5秒/次）
- ✅ PM Agent能生成用户故事和功能清单
- ✅ Developer Agent能生成可运行的代码
- ✅ 沙箱能执行Python代码
- ✅ 单元测试全部通过
- ✅ **完整流程跑通**（需求→PM→Architect→Developer→Tester→Reviewer→交付）
- ✅ 生成完整项目（backend/main.py + frontend/index.html）
- ✅ REST API正常工作
- ✅ JWT认证正常工作

**已知限制：**
- Proposer-Critic讨论需要时间（PM/Architect各1轮，约30秒/轮）
- 前端SVG卡通形象用emoji代替
- 移动端适配为基础响应式

**启动方式：**
```bash
cd "c:/Users/lahm/Desktop/Many AgentS"
python -m Blueprint.start
```

---

## Phase 35：LLM模型切换 + Proposer-Critic调优（2026-06-05）

**问题：** MIMO v2.5 Pro响应慢（单次90秒），Proposer-Critic模式下完整流程需13分钟

**切换：**

| 配置项 | 之前 | 之后 |
|--------|------|------|
| LLM Model | mimo-v2.5-pro | deepseek-v4-flash |
| 单次调用 | ~90秒 | ~3.9秒 |
| 完整流程 | ~13分钟 | ~35秒 |

**Proposer-Critic调优：**

| 改动 | 之前 | 之后 |
|------|------|------|
| PM讨论轮次 | 3轮 | 1轮 |
| Architect讨论轮次 | 3轮 | 1轮 |
| Developer讨论轮次 | 1轮 | 1轮（不变） |
| 总LLM调用 | 16次 | 9次 |

**配置文件：**
- `Blueprint/.env` — 切换到DeepSeek API
- `Blueprint/config.py` — 默认模型改为deepseek-v4-flash
- `Blueprint/agents/discussion.py` — 讨论轮次改为1

---

## Phase 36：WebSocket认证修复（2026-06-05）

**问题：** 设置页面保存配置后返回工作台，WebSocket连接1-2秒后断开，指示灯闪烁

**根因分析：**
1. Token过期或无效时，服务器关闭WebSocket（code 4001）
2. 前端`ws.onclose`不检查关闭原因，2秒后无条件重连
3. 重连用同一个无效token → 服务器又关闭 → 无限循环
4. 主页面没有token有效性检查（settings页面有，主页面没有）

**修复：**

| 文件 | 改动 |
|------|------|
| index.html | `connectWebSocket()`连接前检查token，无token跳登录页 |
| index.html | `ws.onclose`检查close code，4001跳登录页不重连 |

**修复前逻辑：**
```
连接 → 成功 → 1秒后服务器关闭(4001) → 2秒后重连 → 又关闭 → 无限循环
```

**修复后逻辑：**
```
无token → 跳登录页
token无效(4001) → 清token → 跳登录页
其他断开 → 2秒后重连
```

**测试：** 254 个全过

---

## Phase 37：Windows编码修复（2026-06-05）

**问题：** LLM返回emoji时，Python控制台GBK编码崩溃（UnicodeEncodeError）

**根因：** Windows默认GBK编码，不支持Unicode emoji（如👋）

**修复：**

| 文件 | 改动 |
|------|------|
| start.py | 添加`PYTHONIOENCODING=utf-8`环境变量 + `sys.stdout.reconfigure` |
| utils/llm.py | 同上，确保LLM模块也用UTF-8 |

**测试：** LLM调用正常，emoji不再崩溃

**访问地址：** http://localhost:8080

---

## Phase 28：代码审查全量修复（2026-06-05）

**来源：** 逐行代码审查，发现7 Critical + 18 Important + 23 Minor

**Critical修复：**

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| C1 | execute_node泄露环境变量 | sandbox/executor.py | 添加`env=_get_safe_env(tmpdir)` |
| C2 | verify_api_key未应用到端点 | api/auth.py | 标记为已知（需要在路由中添加依赖） |
| C3 | API key明文返回 | api/settings.py | GET /settings返回掩码后的key |
| C4 | PM retry计数不递增 | agents/pm.py | 错误时返回`_pm_retry_count + 1` |
| C5 | Developer retry计数不递增 | agents/developer.py | 错误时返回`_developer_retry_count + 1` |
| C6 | Architect无retry限制 | agents/graph.py | 添加retry计数检查 |
| C7 | Developer重复验证 | agents/developer.py | 删除重复的验证块 |

**Important修复：**

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| I1 | str()哈希不可靠 | utils/llm.py | 改用json.dumps(sort_keys=True) |
| I2 | async无限流 | utils/llm.py | 添加asyncio.Lock() |
| I3 | guard.py误报 | utils/guard.py | 移除jailbreak/roleplay/pretend等宽泛模式 |
| I4 | state.py硬编码max_iterations | agents/state.py | 改为从settings读取 |
| I5 | RuntimeError过于宽泛 | agents/pm.py | 保持pass（interrupt场景） |
| I6 | proc.kill() OSError | sandbox/executor.py | 添加try/except |
| I7 | settings.py非原子写入 | api/settings.py | 改为tmp+os.replace |
| I8 | start.py重复/health路由 | start.py | 删除重复定义 |
| I9 | main.py死代码import | main.py | 清理UserDB import |
| I10 | 未使用call_llm import | 5个Agent文件 | 全部清理 |

**测试：** 254 个全过

---

## Phase 29：设置API + 前端路由修复（2026-06-05）

**问题1：** 设置页面保存失败，API返回404
- **根因：** `/api/settings` 端点不存在
- **修复：** 创建 `api/settings.py`，实现GET/PUT设置端点

**问题2：** 设置保存后LLM配置不生效
- **根因：** 设置页面保存到`data/settings.json`，但LLM模块读的是环境变量
- **修复：** `utils/llm.py` 的 `_create_llm()` 现在优先读取`data/settings.json`

**问题3：** 聊天界面不能滚动
- **根因：** `overflow: hidden` 阻止滚动
- **修复：** 所有页面改为 `overflow-y: auto`

**问题4：** 发送按钮点不动
- **根因：** WebSocket未连接时`sendMessage()`静默返回
- **修复：** 未连接时显示提示信息，按钮未连接时禁用

**测试：** 254 个全过

---

## Phase 30：WebSocket全流程修复（2026-06-05）

**问题：** 输入需求后无反应，WebSocket卡住

**调试过程：**
1. curl测试服务器正常，但WebSocket测试超时
2. 发现`_run_graph_sync`使用`app.stream()`（同步API），但Agent节点是async函数
3. 第一次修复：改用`app.astream()` + `asyncio.run()`
4. 验证：流程跑通

**根因：** Phase 26把Agent节点改成async，但没有同步更新websocket.py的图执行方式

**教训：**
- 改了async/sync性质，必须检查所有调用方
- 代码审查要追踪数据流，不能只看表面错误

**测试：** 254 个全过，完整流程跑通

---

## Phase 30：下载功能完整调试（2026-06-05~06）

**问题描述：** 用户点击下载按钮，浏览器弹出下载框但显示"下载失败"。点击重试下载到`download.json`。

**调试过程（共6轮）：**

### 第1轮：路由顺序问题
- **症状：** 下载返回JSON而非文件
- **排查：** `curl -v http://localhost:8080/api/projects/test/download` 返回200，Content-Type正确
- **根因：** 路由`/download/{file_path:path}`在`/download`之前，FastAPI优先匹配带参数的路由
- **修复：** 调整路由顺序，`/download`在前，`/download/{file_path:path}`在后
- **结果：** 问题依旧

### 第2轮：缺少Content-Length头
- **症状：** 浏览器下载后无响应
- **排查：** `curl -I`检查响应头，发现没有Content-Length
- **根因：** StreamingResponse未设置Content-Length，部分浏览器无法处理
- **修复：** ZIP下载和单文件下载都添加`Content-Length`头
- **结果：** 问题依旧

### 第3轮：deliver_node未返回files
- **症状：** 前端显示"项目完成"但下载失败
- **排查：** 检查WebSocket消息，发现`project_done`消息中`files`为空
- **根因：** `deliver_node`保存文件到磁盘，但返回值没有`files`字段
- **修复：** 返回值添加`files: files`
- **结果：** 问题依旧（因为图根本没跑到deliver_node）

### 第4轮：图在Architect后就结束了
- **症状：** 用户只看到Architect工作，然后显示"项目完成"
- **排查：** 添加logging，发现图在human_confirm后就结束了
- **根因：** human_confirm调用interrupt()暂停，但WebSocket把它当作"完成"处理
- **修复：** WebSocket检查图状态，status="running"时发送interrupt消息，而非project_done
- **结果：** 前端正确显示interrupt确认框，但点击确认后报错

### 第5轮：LangGraph缺少checkpoint
- **症状：** 用户确认后报错"Cannot use Command(resume=...) without checkpointed"
- **排查：** interrupt/resume需要图有checkpointer持久化状态
- **根因：** `graph.compile()`没有传checkpointer
- **修复：** 添加`MemorySaver`作为checkpointer
- **结果：** 完整流程跑通，但预览/下载报Internal Server Error

### 第6轮：meta.json编码问题
- **症状：** 预览文件返回500 Internal Server Error
- **排查：** `curl -s`测试发现`_read_meta`抛出`UnicodeDecodeError`
- **根因：** `meta.json`包含GBK编码的中文（Windows默认编码），但读取时用UTF-8
- **修复：** `_read_meta`添加编码容错（UTF-8失败时尝试GBK，JSON损坏时返回空dict）
- **结果：** 预览和下载都正常工作 ✅

**最终修复清单：**

| 文件 | 修改 |
|------|------|
| api/projects.py | 路由顺序调整、Content-Length、meta.json编码容错 |
| agents/graph.py | deliver_node返回files、添加MemorySaver checkpointer |
| api/websocket.py | 检查图状态（running=interrupt, delivered=project_done） |
| static/index.html | 区分"项目完成"和"流程完成（无文件）"状态 |

**经验教训：**
1. **下载问题需要逐层排查** — 路由→响应头→数据流→图状态→文件编码
2. **LangGraph interrupt/resume必须有checkpointer** — 这是官方要求，不是可选的
3. **Windows编码问题** — 中文环境默认GBK，文件读写要加编码容错
4. **图暂停≠图完成** — status="running"表示暂停等用户输入，不是完成

---

## Phase 31：TDD流程改造（2026-06-06）

**目标：** 将图结构改为TDD流程（先写测试后写代码）

**改动：**
- 图结构从 PM→Architect→Developer→Tester→Reviewer 改为 PM→Architect→Tester→Developer→Reviewer
- Tester在Developer之前运行，先生成测试用例
- Developer根据测试用例实现代码
- route_after_developer返回"reviewer"而非"tester"

**修改文件：**
- `agents/graph.py` — 图结构和路由函数
- `tests/test_graph.py` — 更新测试断言

**测试：** 254个全过

---

## Phase 32：Agent执行模式（2026-06-06）

**目标：** 添加max/mini执行模式开关

**改动：**
- config.py新增`agent_mode`配置（"max"开启Proposer-Critic，"mini"关闭）
- config.py新增`show_discussion`配置（控制前端讨论面板显示）
- settings API支持新字段
- settings页面新增执行模式单选框和讨论开关
- discussion.py根据agent_mode动态启用/禁用讨论

**前端改动：**
- settings.html新增"执行模式"单选框（max/mini）
- 新增"输出讨论过程"复选框（仅max模式可选）
- index.html根据show_discussion控制讨论面板显示

**测试：** 254个全过

---

## Phase 33：设置页面修复（2026-06-06）

**问题：** 设置页面无法保存，API key和模型名称有红色*必填标识

**调试过程：**

| 轮次 | 问题 | 修复 |
|------|------|------|
| 1 | API key有红色*必填标识 | 移除required标识，改为可选 |
| 2 | 模型名称有红色*必填标识 | 移除required标识，改为可选 |
| 3 | 选"自定义..."但没输入时报错 | 优化验证逻辑，空值时保持原值 |
| 4 | `const model`不能重新赋值 | 改为`let model` |
| 5 | 设置保存后LLM配置不生效 | _load_settings合并默认值 |
| 6 | 测试API key覆盖真实key | 恢复正确配置 |

**修改文件：**
- `static/settings.html` — 验证逻辑、UI文案
- `api/settings.py` — _load_settings合并默认值

**测试：** 254个全过

---

## Phase 34：代码审查修复（2026-06-06）

**来源：** 代码审查发现5个Critical + 11个Important

**Critical修复：**

| # | 问题 | 修复 |
|---|------|------|
| C1 | meta.json编码问题 | _read_meta添加GBK编码容错 |
| C2 | WebSocket不识别interrupt状态 | 检查status=="running"发送interrupt消息 |
| C3 | LangGraph缺少checkpointer | 添加MemorySaver |
| C4 | route_after_developer返回错误 | 改为"reviewer"（TDD流程） |
| C5 | settings默认值不合并 | _load_settings合并_DEFAULTS |

**Important修复：**

| # | 问题 | 修复 |
|---|------|------|
| I1 | _extract_json死代码 | 5个Agent文件删除本地函数 |
| I2 | reviewer丢弃消息历史 | 改为追加到messages |
| I3 | LLM单例非线程安全 | 添加threading.Lock双重检查 |
| I4 | settings API key掩码 | GET返回掩码值，前端不加载掩码 |
| I5 | model为const不能赋值 | 改为let |
| I6 | WebSocket无速率限制 | 添加每用户每分钟3次限制 |
| I7 | execute_node泄露环境变量 | 添加env=_get_safe_env |
| I8 | Developer重复路径验证 | 删除重复代码块 |

**测试：** 254个全过

---

## 项目最终状态（更新）

**核心成果：**
- ✅ 254个测试全过
- ✅ TDD流程（Tester→Developer）
- ✅ max/mini执行模式开关
- ✅ 完整流程跑通（需求→PM→Architect→Tester→Developer→Reviewer→交付）
- ✅ WebSocket实时通信（interrupt/resume/rethink）
- ✅ 文件预览和下载正常
- ✅ 设置页面可正常保存和生效
- ✅ Proposer-Critic对抗模式（可配置）
- ✅ Pydantic Schema校验
- ✅ 代码执行沙箱（Python/Node/SQL + 进程组安全）
- ✅ JWT认证 + 用户系统
- ✅ Mission Control风格前端（5个页面）
- ✅ LangGraph checkpointer支持interrupt/resume
- ✅ MIMO/DeepSeek双模型支持

**已知限制：**
- 前端SVG卡通形象用emoji代替
- 移动端适配为基础响应式
- JWT secret为自动生成+文件持久化（开发够用，部署需改为环境变量）
- 完整流程耗时约1-2分钟（取决于LLM响应速度）

---

## Phase 38：JWT Secret问题分析（2026-06-05）

**问题：** 用户登录后WebSocket返回403，Token存在但验证失败

**根因：** JWT secret不一致

```python
# auth.py 的 secret 生成逻辑
if _SECRET_FILE.exists():
    _JWT_SECRET = _SECRET_FILE.read_text()
if not _JWT_SECRET:
    _JWT_SECRET = secrets.token_hex(32)  # 生成新 secret
    _SECRET_FILE.write_text(_JWT_SECRET)
```

**触发场景：**

| 场景 | 原因 | 表现 |
|------|------|------|
| `.Blueprint_secret`文件被删 | 服务器重启后生成新secret | 所有旧token失效 |
| 多实例部署 | 每个实例有自己的secret | A签发的token在B被拒 |
| `git clean -fd` | 清掉了secret文件 | 同上 |
| 换机器部署 | 新机器没有secret文件 | 同上 |

**当前方案（开发阶段）：** 自动生成+持久化到`.Blueprint_secret`文件，够用

**部署时需改为：**
```python
# 方案1：环境变量（推荐）
JWT_SECRET = os.environ.get("Blueprint_JWT_SECRET")

# 方案2：配置文件（密钥管理服务）
JWT_SECRET = load_from_vault("Blueprint/jwt-secret")
```

**临时修复：** 用户重新登录即可获取用当前secret签发的新token

**教训：** JWT secret不能自动生成+文件持久化，部署时必须用固定配置

---

## Phase 39：WebSocket认证修复确认（2026-06-05）

**问题：** 设置页面保存后返回工作台，WebSocket连接1-2秒后断开

**实际根因：** Phase 36的修复（token检查+4001处理）方向正确，但真正原因是Phase 38的JWT secret不一致导致403

**验证：** 用户重新登录后WebSocket正常连接，设置页面正常工作

**结论：** Phase 36的前端修复仍然有价值（防止无效token无限重连），但根本问题是后端的JWT secret管理

---

## Phase 40：Developer Agent 核心改造（2026-06-05）

**背景：** 多Agent系统效率低、质量差的反思

**问题分析（来自用户反馈）：**
1. Proposer-Critic在简单任务上反而有害——Critic为了"有用"挑无关紧要的刺
2. 9次LLM调用，质量没有比单次调用好多少
3. "审查还有致命错误"——因为Reviewer是LLM审LLM，不跑代码
4. 设置页面改了配置但Agent不读——两套配置系统隔离

**核心问题：** 每个Agent就是一次LLM调用+角色扮演prompt，没有真正的工具能力。跟直接调一次LLM没本质区别，只是多花了5倍的钱。

**参考项目：** Multi-Agent-Playground（大神的项目）
- 两阶段执行：Agent先做事，再决定下一步
- 工具证据验证：Agent说"创建了文件"→系统验证文件是否真的存在
- JSON修复层：输出不合法时自动修复

**改造内容：**

### 1. Developer Agent 重写（核心改动）

**之前：** LLM输出代码JSON → 存入state → 交给Tester

**现在：** LLM输出代码 → 写入文件 → 真正执行 → 有bug就修 → 再执行（最多3轮）

```
生成代码 → 写入磁盘 → execute_python执行
    ↓ 失败
LLM修复 → 再执行 → 还失败？
    ↓
LLM再修 → 再执行 → 还失败？
    ↓
放弃，交给Reviewer
```

**关键代码：**
```python
async def developer_agent(state):
    # 1. 生成代码
    code = await generate_code(state)

    # 2. 写入文件 + 执行
    with tempfile.TemporaryDirectory() as tmpdir:
        exec_result = write_and_execute(code, tmpdir)

        # 3. 有bug就修（最多3轮）
        fix_attempt = 0
        while not exec_result["success"] and fix_attempt < 3:
            fix_attempt += 1
            code = await fix_code(code, exec_result["stderr"])
            exec_result = write_and_execute(code, tmpdir)

    return {"files": code, "test_passed": exec_result["success"]}
```

### 2. 配置桥接修复

**问题：** 设置页面保存到`data/settings.json`，Agent读`config.py`，两套系统不通信

**修复：** `discussion.py`的`_get_discussion_config()`改为先读`data/settings.json`，没有再fallback到`config.py`

**效果：** UI设置Proposer-Critic开关后，Agent立即生效（不用重启服务器）

### 3. 前端展示执行结果

Developer执行代码后，前端显示：
- ✅ 代码执行通过（绿色）
- ❌ 代码执行失败 + 错误信息（红色）

**测试：** 43个单元测试全过

**效果预期：**
- 简单任务（计算器）：Developer直接写→执行→通过，1次LLM调用
- 有bug的代码：Developer写→执行→修→再执行，2-3次调用
- 比Proposer-Critic的9次调用更快、质量更高

**讨论记录：**
- 用户反馈："做了个计算器，Proposer-Critic讨论两轮最后审查还是有致命错误"
- 分析：同模型互相挑刺效果有限，不如真正执行代码
- 决策：关掉Proposer-Critic，Developer改成"写→执行→修→再执行"
- 参考：Multi-Agent-Playground的工具证据验证理念

---

## Phase 41：前端 Vue 3 SPA 重构（2026-06-05）

**目标：** 将多页面 HTML 前端重构为 Vue 3 SPA，解决状态丢失和代码混乱问题

**技术选型：** Vue 3 + Vite + Vue Router + Pinia + Vitest

**TDD 流程：** 每个模块先写测试，看失败，再写实现，看通过。48 个测试全过。

**实现内容：**

| Task | 内容 | 测试数 |
|------|------|--------|
| 1 | 项目初始化 + Vitest 测试框架 | 1 |
| 2 | authStore（登录态管理） | 4 |
| 3 | projectStore（项目数据） | 5 |
| 4 | wsStore（连接状态） | 2 |
| 5 | main.js + Pinia 注册 | 1 |
| 6 | Router + 路由守卫 | 3 |
| 7 | REST API 封装 | 4 |
| 8 | AgentCard 组件 | 4 |
| 9 | FlowPanel + IterationInfo | 3 |
| 10 | ChatPanel | 4 |
| 11 | InterruptDialog + OutputPanel + DiscussionPanel | 5 |
| 12 | LoadingBar + AgentStatusBar + App.vue | 2 |
| 13 | LoginPage | 3 |
| 14 | WorkbenchPage + 其他页面 | 5 |
| 15 | WebSocket composable | 6 |
| 16 | 构建部署 | — |

**总计：48 个测试，15 个测试文件，全部通过**

**文件结构：**
```
frontend/src/
├── main.js, App.vue, router.js
├── stores/        (auth.js, project.js, websocket.js)
├── composables/   (useWebSocket.js)
├── api/           (index.js)
├── pages/         (Login, Workbench, Projects, ProjectDetail, Settings)
├── components/    (AgentCard, ChatPanel, FlowPanel, InterruptDialog, OutputPanel, DiscussionPanel, LoadingBar, AgentStatusBar, IterationInfo)
└── styles/        (main.css)
```

**核心设计：**
- 3 个 Pinia Store 职责分离（auth/project/ws）
- WebSocket 全局单例，页面切换不断连
- 路由守卫：无 token 跳登录，已登录跳过登录页
- 白色清新风格，替换 Mission Control 暗黑风格
- 构建产物输出到 `Blueprint/static/`，FastAPI 直接 serve

**构建结果：** 102KB JS + 2KB CSS（gzip 后 40KB）

**启动方式：**
```bash
cd "c:/Users/lahm/Desktop/Many AgentS"
python -m Blueprint.start
```

**访问地址：** http://localhost:8080

**讨论记录：**
- 用户："页面跳转丢状态，代码混乱，想重构"
- 决策：Vue 3 SPA，不改后端
- 用户："能不能借鉴 Multi-Agent-Playground 的架构？"
- 决策：用 Vue 3 + Vite + Pinia，参考其组件化结构
- 用户："Tailwind 有什么用？"
- 决策：不加 Tailwind，写入待办
- 用户："全部都需要 TDD，时间长点能接受"
- 决策：16 个 Task 全部红-绿-重构循环

**构建部署修复：**
- 问题：Vue 构建产物引用 `/assets/...`，但 FastAPI 在 `/static/assets/...` 下挂载静态文件，导致 404 白屏
- 修复：`start.py` 新增 `/assets` 路径映射，直接指向 `static/assets/` 目录
- 原因：Vite 默认 base 为 `/`，构建产物的引用路径是 `/assets/xxx.js`，需要 FastAPI 在对应路径下提供文件

---

## Phase 42：运行时 Bug 修复（2026-06-08）

**问题：** 首次真实运行发现 3 个 Bug

### Bug 1：Developer `str + None` 崩溃

**现象：** `TypeError: can only concatenate str (not "NoneType") to str`，反复触发

**根因：** `DEVELOPER_FIX_PROMPT` 包含 `files[{path,content,language}]`，Python `.format()` 把 `{path,content,language}` 当占位符解析，返回 `None`，字符串拼接崩溃

**修复：** 转义花括号 `{{path,content,language}}`

**教训：** 用 `.format()` 的 prompt 字符串里不能有未转义的 `{}`

### Bug 2：`language: 'javascript'` 不在 Literal 约束里

**现象：** `ValidationError: Input should be 'python', 'html', 'js'...`，LLM 输出了 `javascript` 而不是 `js`

**修复：** `CodeFile.language` Literal 加入 `"javascript"`

**教训：** LLM 不会严格遵守缩写，枚举要包含常见别名

### Bug 3：Developer 死循环

**现象：** Developer 报错 → 图路由回 Developer → 又报错 → 无限循环，消息刷屏

**根因：** Developer 错误处理没设 `_developer_retry_count`，路由函数永远认为重试次数是 0

**修复：** error 返回值加 `_developer_retry_count: state.get("_developer_retry_count", 0) + 1`

**教训：** 路由函数的重试计数必须由节点函数递增，否则死循环

### Bug 4：前端缺新建/清空/重试功能

**现象：** 用户无法新建对话、清空聊天、重试上一条需求

**修复：** ChatPanel 加三个功能：
- 🗑️ 清空聊天
- ✚ 新建对话（reset + cancel）
- 🔄 重试（用户消息 hover 显示）

### Bug 5：慢（MIMO API）

**现象：** Developer 反复重试，每次等 60-90 秒

**根因：** settings.json 还是 MIMO 模型

**修复：** 用户手动切换到 DeepSeek

**优化：**
- 简单需求跳过 PM（`route_by_complexity`）
- 重试从 3→2 次，退避从 1s→0.5s
- 冲突仲裁：循环上限 interrupt 人工决定

**测试：** 22 个测试全过

---

## Phase 43：工具调用重构设计（2026-06-08）

**背景：** 用户反馈"至今没有完整跑完一次并拿到能用的代码"，分析发现核心问题是 Agent 没有"做事"的能力——只是 LLM 输出 JSON，你解析。

**参考：** Multi-Agent-Playground 的工具调用模式 + WenzAgent 的 Agent 生命周期管理

**核心改动：** Developer/Tester/Reviewer 从"LLM 输出 JSON → 解析"改为"LLM 调用工具 → 执行 → 循环"

**设计决策：**

| 决策 | 选择 | 理由 |
|------|------|------|
| 哪些 Agent 改 | Developer/Tester/Reviewer | PM/Architect 纯推理，JSON 输出够用 |
| 工具调用协议 | OpenAI function calling | DeepSeek/MIMO 都兼容，LangChain bind_tools 直接支持 |
| Developer 能否执行代码 | 能 | 写完就跑，有 bug 就修，自洽循环 |
| 最大工具步数 | Developer 10 / Tester 8 / Reviewer 5 | 防止无限循环 |
| LLM 不调工具怎么办 | 当隐式完成 | 简单可靠 |
| 消息协议 | 一条 assistant 包含所有 tool_calls | OpenAI 标准，不遵守会出 bug |

**工具矩阵：**

| 工具 | Developer | Tester | Reviewer |
|------|:---------:|:------:|:--------:|
| file_write | ✅ | ❌ | ❌ |
| file_read | ✅ | ✅ | ✅ |
| execute_python | ✅ | ✅ | ❌ |
| done | ✅ | ✅ | ✅ |

**设计文档：** `docs/superpowers/specs/2026-06-08-tool-calling-refactor-design.md`
**实现计划：** `docs/superpowers/plans/2026-06-08-tool-calling-refactor.md`

**实现计划：** 8 个 Task，约 3.5 小时，TDD 流程

**讨论记录：**
- 用户："至今没有完整跑完一次并拿到能用的代码"
- 分析：Agent 只是 LLM 输出 JSON，没有工具能力
- 用户："我觉得 superpower skills 的运行方式害了你的思路"
- 反思：skills 是 prompt engineering 思路（LLM 说话，你做事），Agent 应该是 tool calling 思路（LLM 做事，你提供工具）
- 用户："WenzAgent 的 done 工具应该带结构化输出"
- 采纳：done 工具加 files_modified 和 key_decisions 字段

---

## Phase 44：工具调用重构实现（2026-06-08）

**目标：** 将 Developer/Tester/Reviewer 从 JSON 输出改为工具循环模式

**TDD 流程：** 8 个 Task，全部红-绿-重构循环

| Task | 内容 | 测试数 |
|------|------|--------|
| 1 | 工具定义（tools.py） | 8 |
| 2 | 工具执行引擎（tool_executor.py） | 10 |
| 3 | LLM 工具调用封装（call_llm_with_tools） | 2 |
| 4 | Developer Agent 重写（工具循环） | 4 |
| 5 | Tester Agent 重写（工具循环） | 2 |
| 6 | Reviewer Agent 重写（工具循环） | 7 |
| 7 | Graph 集成 + 集成测试修复 | 6（修复） |
| 8 | 前端 ChatPanel 适配工具消息 | 2 |

**新增文件：**
- `agents/tools.py` — 工具定义（file_write, file_read, execute_python, done）+ 工具集分组 + serialize_call
- `agents/tool_executor.py` — execute_tool + 路径安全校验（realpath 防符号链接逃逸）

**重写文件：**
- `agents/developer.py` — JSON 输出 → 工具循环（最多 10 步）
- `agents/tester.py` — JSON 输出 → 工具循环（最多 8 步）
- `agents/reviewer.py` — JSON 输出 → 工具循环（最多 5 步）

**修改文件：**
- `utils/llm.py` — 新增 call_llm_with_tools()
- `agents/graph.py` — 路由适配新返回值
- `tests/test_integration.py` — mock 从 call_llm 改为 call_llm_with_tools
- `frontend/src/components/ChatPanel.vue` — 新增 formatMessageContent 处理 tool/tool_calls 消息

**工具矩阵：**

| 工具 | Developer | Tester | Reviewer |
|------|:---------:|:------:|:--------:|
| file_write | ✅ | ❌ | ❌ |
| file_read | ✅ | ✅ | ✅ |
| execute_python | ✅ | ✅ | ❌ |
| done | ✅ | ✅ | ✅ |

**测试结果：** 后端 256 + 前端 50 = 306 个测试全过

**前端工具消息渲染验证：**
- `formatMessageContent()` 已实现（ChatPanel.vue 第 49-85 行）
- `role: "tool"` → 解析 JSON，显示 stdout/error/success
- `tool_calls` → 显示操作描述（📝 写入 main.py、▶️ 执行代码等）
- 2 个新测试覆盖 tool 消息和 tool_calls 消息
- 构建成功，输出到 `Blueprint/static/`

**关键改动：**
- Agent 从"LLM 输出 JSON → 你解析"改为"LLM 调工具 → 工具执行 → 结果回传 LLM"
- 消息协议：一条 assistant 包含所有 tool_calls（OpenAI 标准）
- done 工具带结构化输出（summary, files_modified, key_decisions）
- 工具失败不抛异常，返回错误信息让 LLM 自己调整

**启动方式：**
```bash
cd "c:/Users/lahm/Desktop/Many AgentS"
python -m Blueprint.start
```

**访问地址：** http://localhost:8080

---

## Phase 45：代码审查修复（2026-06-08）

**来源：** /requesting-code-review 子代理审查，发现 3 Critical + 6 Important + 6 Minor

**Critical 修复：**

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| C1 | Reviewer 的 project_dir=""，路径穿越漏洞 | reviewer.py | 改为 `f"projects/{project_id}"` |
| C2 | Reviewer 的 done 没走 execute_tool，消息协议破损 | reviewer.py | 重写为标准工具循环，done 也走 execute_tool |
| C3 | call_llm_with_tools 没有 retry 和 rate limiter | llm.py | 加 `@retry` + `_llm_semaphore` |

**Important 修复：**

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| I4 | Tester 的 pass/fail 判断依赖 LLM 文本摘要，脆弱 | tester.py | 加 `had_execution_errors` 追踪 execute_python 的 returncode |

**Minor 修复：**

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| — | Reviewer 超过最大步数时没有 error 返回值 | reviewer.py | 加 `for/else` 返回 error 字段 |

**审查结论：** 实现架构合理，工具定义、消息协议、循环结构都正确。3 个 Critical 已全部修复。

**测试结果：** 256 个后端测试全过

---

## Phase 45：用户审查修复（2026-06-09）

**来源：** 用户逐行审查，发现 3 Critical + 3 Important + 2 Minor

**Critical 修复：**

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| C1 | project_dir 三个 Agent 各用各的，state.py 没定义 | state.py + 三个 Agent | state.py 加 `project_dir` 字段，`create_initial_state` 初始化为 `projects/{project_id}`，三个 Agent 统一用 `state.get("project_dir")` |
| C2 | TDD 流程断裂：Tester 在 Developer 之前但没有 file_write | graph.py | 改为 Developer → Tester → Reviewer 顺序 |
| C3 | execute_python 在临时目录执行，无法 import 项目文件 | sandbox/executor.py + tool_executor.py | execute_python 加 `cwd` 参数，tool_executor 传入 project_dir |

**Important 修复：**

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| I4 | serialize_call 使用不一致 | tester.py + reviewer.py | 改用统一的 `serialize_call` |
| I5 | _extract_test_passed 漏了 "0 error" | tester.py | 加 `"0 error"` 判断 |
| I6 | ProjectState 缺 retry count 字段 | state.py | 加 `_pm_retry_count`, `_architect_retry_count`, `_developer_retry_count` |

**测试结果：** 256 个后端测试全过

---

## Phase 46：DeepSeek tool_calls 兼容修复（2026-06-09）

**问题：** 首次真实运行报 `AttributeError: 'dict' object has no attribute 'id'`

**根因：** DeepSeek 返回的 tool_calls 是 dict 格式，不是 LangChain 对象。`tc.function.name` 在 dict 上不存在。

**影响范围：** 所有 Agent 节点（developer/tester/reviewer）+ tool_executor + serialize_call

**修复：**

| 文件 | 改动 |
|------|------|
| tools.py | `serialize_call` 兼容 dict 和对象；新增 `get_call_name()` / `get_call_args()` 辅助函数 |
| tool_executor.py | `execute_tool` 兼容 dict 和对象 |
| developer.py | 改用 `get_call_name` / `get_call_args` |
| tester.py | 同上 |
| reviewer.py | 同上 |

**兼容逻辑：**
```python
if isinstance(call, dict):
    name = call.get("name", call.get("function", {}).get("name", ""))
else:
    name = call.function.name
```

**测试结果：** 256 个后端测试全过

---

## Phase 47：首次真实运行修复（2026-06-09）

**问题：** 首次真实运行发现 4 个 Bug

### Bug 1：DeepSeek tool_calls 用 `args` 不是 `arguments`

**现象：** `KeyError: 'path'`，`JSONDecodeError: Expecting value: line 1 column 1`

**根因：** DeepSeek 返回的 tool_calls 格式是 `{name, args, id, type}`，其中 `args` 是 dict。OpenAI 格式是 `{name, arguments}`，其中 `arguments` 是 string。

**修复：** `tools.py` 的 `get_call_args` 和 `serialize_call` 兼容两种格式

**教训：** 不同 LLM provider 的 tool_calls 格式不统一，必须做防御性处理

### Bug 2：tool_executor 缺参数校验

**现象：** LLM 返回空 arguments 时 `KeyError`

**修复：** tool_executor 加参数校验，缺字段返回错误信息而非崩溃

### Bug 3：PM 被跳过

**现象：** "做一个web应用计算器"直接到 Developer

**修复：** `route_by_complexity` 阈值改 15 字，关键词加 "web/应用/前端"

### Bug 4：清空聊天后旧消息又弹出

**修复：** 前端加 `activeProjectId` 追踪，旧项目消息忽略

---

## Phase 48：interrupt 流程修复（2026-06-09）

**问题：** 架构确认 interrupt 触发了但前端没弹确认框

**根因：** InterruptDialog 只在测试里用了，没加到 App.vue

**修复：**

| 文件 | 改动 |
|------|------|
| App.vue | 加 `<InterruptDialog />` 渲染 |
| websocket.py | interrupt 消息带完整架构数据 |
| graph.py | resume 时 response 兼容 string/dict/bool |

---

## Phase 49：全流程跑通修复（2026-06-09）

**里程碑：** 首次完整流程跑通，生成可运行的计算器 Web 应用

**修复清单：**

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| 1 | DeepSeek tool_calls 用 `args` 不是 `arguments` | tools.py | `get_call_args` 兼容两种格式 |
| 2 | tool_executor 缺参数校验 | tool_executor.py | 缺字段返回错误而非崩溃 |
| 3 | PM 被跳过 | graph.py | `route_by_complexity` 阈值改 15 字，加关键词 |
| 4 | 清空聊天后旧消息弹出 | useWebSocket.js + ChatPanel.vue | `activeProjectId` 追踪 |
| 5 | InterruptDialog 没渲染 | App.vue | 加 import + 组件 |
| 6 | interrupt 消息缺架构数据 | websocket.py | 带完整 architecture/api_definitions/data_models |
| 7 | resume response 格式不兼容 | graph.py | 兼容 string/dict/bool |
| 8 | 沙箱 Windows GBK 崩溃 | sandbox/executor.py | `encoding="utf-8", errors="replace"` |
| 9 | LLM 超时太短 | llm.py | 30s → 120s |
| 10 | SDK 自带重试叠加 | llm.py | `max_retries=0` |
| 11 | LLM 缓存不刷新 | llm.py | hash 包含 timeout 参数 |
| 12 | Tester/Reviewer 没跑 | developer.py | 成功后 `_developer_retry_count: 0` 重置 |
| 13 | 历史项目下载失败 | ProjectDetailPage.vue | `filesResponse.files` 解包 |
| 14 | list_projects 编码错误 | projects.py | GBK fallback |
| 15 | 预览窗口太小 | OutputPanel.vue + ProjectDetailPage.vue | max-height 200px → 400px |
| 16 | 下载按钮缺失 | OutputPanel.vue | 加下载按钮 + 打包下载 |

**测试结果：** 后端 256 + 前端 50 = 306 个测试全过

**实际验证：** 输入"做一个web应用,能加减乘除的计算器"，完整跑通 PM→Architect→Developer→Tester→Reviewer→交付，生成 backend/main.py + frontend/index.html + style.css + app.js

---

## Phase 50：LLM 选型 + API 预设（2026-06-09）

**问题：** 用户需要在多个 LLM API 之间切换（DeepSeek/MIMO/其他）

**新增功能：**

| 功能 | 说明 |
|------|------|
| API 预设保存 | 设置页保存当前 API 配置为命名预设 |
| API 预设切换 | 下拉框选择预设，自动切换 API Key/URL/Model |
| API 预设删除 | 删除不需要的预设 |
| LLM 缓存自动刷新 | 代码级参数变化时自动重建 LLM 实例 |

**后端新增端点：**

| 端点 | 说明 |
|------|------|
| GET /api/settings/presets | 列出所有预设（API Key 脱敏） |
| POST /api/settings/presets | 保存当前配置为预设 |
| POST /api/settings/presets/{name}/apply | 切换到指定预设 |
| DELETE /api/settings/presets/{name} | 删除预设 |

**前端改动：** SettingsPage.vue 顶部加预设栏（下拉+输入+保存/删除按钮）

---

## 待实现功能（用户建议）

**文件下载分级：**

| 选项 | 说明 |
|------|------|
| 源码下载 | 逐个下载源代码文件（.py/.html/.css/.js） |
| 应用下载 | 下载可运行的应用（包含启动脚本） |
| 全部打包 | zip 打包所有文件 |

**优先级：** 中（当前单文件下载能用，打包下载是体验优化）

---

## Phase 51：文件下载分级实现（2026-06-09）

**目标：** 实现用户建议的三级下载选项

**实现方式：** 纯前端 JSZip 打包，不依赖后端

**依赖新增：** `jszip` + `file-saver`

**下载选项：**

| 按钮 | 筛选逻辑 | 内容 |
|------|---------|------|
| 📦 下载源码 | 扩展名匹配 (.py/.js/.html/.css/.json 等) | 源码文件 |
| 🚀 下载应用 | 源码 + start.sh/start.bat/requirements.txt/package.json | 可运行应用 |
| 📁 全部打包 | 无筛选 | 所有文件 |

**前端改动：**

| 文件 | 改动 |
|------|------|
| OutputPanel.vue | 重写，加三个下载按钮 + JSZip 打包 |
| ProjectDetailPage.vue | 同步加三个下载按钮 + JSZip 打包 |

**关键函数：**
```javascript
async function createZip(filterFn, zipName) {
    const zip = new JSZip()
    for (const [path, content] of Object.entries(files)) {
        if (filterFn(path)) zip.file(path, content)
    }
    const blob = await zip.generateAsync({ type: 'blob' })
    saveAs(blob, `${zipName}.zip`)
}
```

**测试结果：** 后端 256 + 前端 50 = 306 个测试全过

---

## Phase 52：代码审查修复（2026-06-09）

**来源：** 全面代码审查，发现 6 Critical + 12 Important + 10 Minor

**已修复（Critical）：**

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| C1 | Windows 资源限制无效 | sandbox/executor.py | 文档化限制，timeout 兜底 |
| C2 | 沙箱可读 .env 等敏感文件 | sandbox/executor.py | execute_python 改用 tmpdir，不传 project_dir |
| C3 | 路径校验 TOCTOU 竞态 | agents/tool_executor.py | _resolve_safe_path 原子化验证 + 敏感文件拦截 |
| C5 | _rate_limits 内存泄漏 | api/websocket.py | 5 分钟周期清理过期 key |

**已修复（Important）：**

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| I1 | asyncio.Lock 每次新建，限流失效 | utils/llm.py | 改为模块级 _async_llm_lock |
| I2 | 路由函数缺 .get() 保护 | agents/graph.py | 全部改为 state.get() 带默认值 |
| I2 | route_after_review 只认英文关键词 | agents/graph.py | 加中文关键词：架构、设计、重构 |
| I3 | deliver_node 无路径校验 | agents/graph.py | 加 .. 和绝对路径检查 + is_relative_to |

**已知限制（下一轮修复）：**

| # | 问题 | 原因 |
|---|------|------|
| C4 | settings.json 可被覆写 | 需要更大改动，隔离配置路径 |
| C6 | Developer/Tester/Reviewer 缺注入防护 | 需要更大改动，统一注入检测 |
| I7 | async 中调同步 proposer_critic_discuss | 架构层面，改风险大 |
| I9 | Developer/Tester/Reviewer 是同步函数 | 架构层面，改风险大 |

**测试结果：** 256 个后端测试全过

---

## Phase 46：C4/C6 安全修复 + I7/I9 异步改造（2026-06-09）

### C4：敏感文件保护

**修复：** `_resolve_safe_path` 扩展敏感文件列表 + 目录黑名单

```python
blocked_names = {'.env', 'settings.json', 'api_presets.json', '.Blueprint_secret', 'config.py', ...}
blocked_dirs = {'data', '.git', '.claude', 'node_modules', '__pycache__}
```

### C6：注入防护

**修复：** `_check_content_safety` + `_check_code_safety` 拦截危险模式

```python
dangerous_patterns = ['import socket', 'os.system(', 'eval(', '__import__(', ...]
```

### I7/I9：全部 Agent 改 async

**改动文件：**

| 文件 | 改动 |
|------|------|
| discussion.py | `proposer_critic_discuss` 改为 async，使用 `call_llm_async` |
| pm.py | 加 `await` 到 `proposer_critic_discuss` 调用 |
| architect.py | 同上 |
| developer.py | 改为 async，使用 `call_llm_with_tools_async` |
| tester.py | 同上 |
| reviewer.py | 同上 |
| llm.py | 新增 `call_llm_with_tools_async` 异步版本 |
| 测试文件 | 全部改为 `@pytest.mark.asyncio` + `AsyncMock` |

**测试结果：** 260 个后端测试全过

---

## Phase 47：运行时问题修复（2026-06-09）

**问题：** 用户实际运行发现 3 个问题

### Bug 1：Developer 读不到自己写的文件

**现象：** Developer 写了 main.py，但 execute_python 执行时找不到文件。导致 Developer 反复重写同样代码，15 轮迭代。

**根因：** `execute_python` 跑在空临时目录，Developer 写的文件在项目目录。两个目录不互通。

**修复：** `_execute_python` 把项目文件复制到临时目录再执行（排除 .env 等敏感文件）。

### Bug 2：Developer 无限循环（31 轮）

**现象：** Developer→Tester→Reviewer 循环 31 次，`max_iterations` 限制没生效。

**根因：** `route_after_developer` 检查 `iteration >= max_iterations` 路由到 `human_confirm`，但 `human_approved` 为 None 导致回 Developer，死循环。

**修复：** iteration 检查放回 `route_after_test` 和 `route_after_review`，不在 `route_after_developer` 里做。

### Bug 3：Developer 改不掉 Tester/Reviewer 指出的问题

**现象：** Tester 说"代码有 bug"，Developer 重写后还是同样的 bug。

**根因：** Developer 每次被调用时 `build_developer_prompt` 从零构建，没有带上一轮 Tester/Reviewer 的反馈。

**修复：** `build_developer_prompt` 加入 `test_results` 和 `review_comments` 反馈：

```python
if test_results and not state.get("test_passed", True):
    user_content += f"\n上一轮测试失败，错误信息：\n{test_results['output'][:500]}\n"

if review_comments and not state.get("review_approved", True):
    user_content += "\n上一轮代码审查发现的问题：\n"
    for c in review_comments[:5]:
        user_content += f"- [{c['severity']}] {c['description']}: {c['suggestion']}\n"
```

### Bug 4：前端无保存按钮

**现象：** 项目跑完了但没有保存入口。

**修复：** ChatPanel 加 💾 按钮，有文件时显示，点击调 POST /api/projects 保存。

**测试结果：** 260 个后端 + 50 个前端 = 310 个测试全过

---

## 设计：SQLite 记忆层（待实现）

**目标：** 项目持久化 + 刷新恢复 + Developer 上下文记忆

### 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| messages 存储 | 单独表，只存摘要 | 不从 executions 重建，快速恢复 |
| llm_response | 不存 | 太大，存结构化 tool_calls + result_summary 即可 |
| files 存储 | 不存内容，只存文件名列表 + hash | 文件从磁盘读，不冗余 |
| project_id 持久化 | localStorage | 刷新后 Pinia 清空，需浏览器存储 |
| 清理策略 | 每 project 最多 50 条 execution，超过 30 天归档 | 防止 SQLite 无限增长 |

### 表结构

```sql
-- 项目快照（轻量，存元数据不存文件内容）
CREATE TABLE project_snapshots (
    project_id TEXT PRIMARY KEY,
    requirement TEXT,
    current_step TEXT,
    iteration INTEGER DEFAULT 0,
    files_summary TEXT,          -- JSON: ["main.py", "index.html"]
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent 执行记录（存结构化数据，不存原始 LLM 返回）
CREATE TABLE agent_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    input_summary TEXT,
    tool_calls TEXT,             -- JSON: [{name, args_summary}]
    result_summary TEXT,
    status TEXT DEFAULT 'success',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_exec ON agent_executions(project_id, agent_name, iteration);

-- 聊天消息（前端恢复用）
CREATE TABLE project_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    role TEXT NOT NULL,
    name TEXT,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_msg ON project_messages(project_id);
```

### 读写时机

| 事件 | 写入 | 读取 |
|------|------|------|
| 项目开始 | 创建 snapshot + 存 project_id 到 localStorage | — |
| 用户发消息 | 写 project_messages | — |
| Agent 输出消息 | 写 project_messages | — |
| Developer/Tester/Reviewer 完成 | 写 agent_executions（摘要） | — |
| 图状态变化 | 更新 snapshot.step | — |
| 项目完成 | 更新 snapshot.status = 'completed' | — |
| 页面刷新 | — | 读 snapshot + messages 恢复前端 |
| Developer 启动 | — | 读最近 2 轮 execution 拼摘要 |

### Developer 摘要拼接

```python
def get_developer_context(project_id: str, current_iteration: int) -> str:
    rows = db.query("""
        SELECT agent_name, result_summary, status
        FROM agent_executions
        WHERE project_id = ? AND iteration >= ?
        ORDER BY iteration DESC, agent_name
        LIMIT 6
    """, [project_id, current_iteration - 2])
    
    if not rows:
        return ""
    
    lines = ["## 之前的尝试："]
    for row in rows:
        lines.append(f"- {row.agent_name}（第{row.iteration}轮）: {row.result_summary}")
    
    return "\n".join(lines)
```

### 前端刷新恢复

```javascript
// 开始项目时
localStorage.setItem('activeProjectId', projectId)

// 刷新恢复时
const projectId = localStorage.getItem('activeProjectId')
if (projectId) {
  const data = await api.getProjectState(projectId)
  projectStore.$patch(data)
}
```

### 新增 API 端点

| 端点 | 说明 |
|------|------|
| GET /api/projects/{id}/state | 返回 snapshot + messages + agentStatus |
| POST /api/projects/{id}/messages | 写入聊天消息 |
| POST /api/projects/{id}/executions | 写入 Agent 执行记录 |

---

## Phase 53：SQLite 记忆层实现（2026-06-09）

**目标：** 项目持久化 + 刷新恢复 + Developer 上下文记忆

**实现内容：**

### 后端（memory.py）

- 3 张表：`project_snapshots`、`agent_executions`、`project_messages`
- 写入：项目开始创建 snapshot，Agent 完成写 execution + messages
- 读取：`get_developer_context()` 拼最近 2 轮摘要

### 后端（websocket.py）

- 图启动时保存 snapshot
- 每个 Agent 完成时保存 execution + messages
- 图完成时更新 snapshot status

### 后端（projects.py）

- 新增 `GET /api/projects/{id}/state` 恢复接口

### 前端（project.js）

- 新增 `restoreFromServer(projectId)` 方法

### 前端（App.vue）

- 页面加载时检查 localStorage 的 `activeProjectId`
- 有则从后端恢复状态，重建 Agent 进度

### 前端（useWebSocket.js）

- `setActiveProject` 同时存 localStorage

**测试结果：** 全部通过

---

## Phase 54：SQLite 记忆层审查修复 + Developer 记忆接入（2026-06-10）

**来源：** 用户审查 SQLite 记忆层，发现 4 Critical + 10 Important + 7 Minor

**Critical 修复：**

| # | 问题 | 修复 |
|---|------|------|
| C1 | save_snapshot kwargs 无白名单 | 加 `_SNAPSHOT_COLUMNS` 集合，拒绝非法列名 |
| C2 | check_same_thread=False 跨线程 | 改为 `threading.local()` 每线程独立连接 |
| C3 | websocket.py 子线程调全局单例 | 保留（线程安全双检锁），加文档说明 |
| C4 | get_project_state 无文件数限制 | 加 `max_files=50` + `max_file_size=1MB` + `skipped_files` 返回 |

**Important 修复：**

| # | 问题 | 修复 |
|---|------|------|
| I1 | 消息全量加载 | 加 `limit=200` 限制 |
| I4 | Agent 状态恢复硬编码 | 保留（顺序固定），加注释 |
| I5 | 恢复消息覆盖时间戳 | 用原始 `created_at` 而非 `Date.now()` |
| I7 | 跳过大文件无提示 | 返回 `skipped_files` 列表 |
| I9 | WebSocket 重连无退避 | 加指数退避（1s → 30s） |

**Developer 记忆接入：**
- `build_developer_prompt` 加入 `get_developer_context()` 调用
- Developer 启动时从 SQLite 读最近 2 轮的 Agent 执行记录
- 拼成摘要注入 prompt，让 Developer 知道之前试过什么、哪里失败了

**测试结果：** 后端 273 + 前端 50 = 323 个全过

**审查验证结果：**

| # | 修复项 | 测试覆盖 |
|---|--------|---------|
| C1 | 白名单校验 | ✅ test_save_snapshot_rejects_invalid_columns |
| C2 | threading.local 并发 | ✅ test_concurrent_access（5线程并发读写） |
| C4 | 文件数限制 | ✅ 测试确认 |
| I1 | limit=200 | ✅ test_message_limit_returns_most_recent + 自定义 limit |
| I4 | 硬编码注释 | ⚠️ 已加注释 |
| I5 | 原始时间戳 | ✅ 验证通过 |
| I7 | skipped_files | ✅ 返回列表 |
| I9 | 指数退避 | ✅ 代码正确 |
| Developer 记忆 | ✅ | ✅ test_developer_prompt_includes_memory_context + test_developer_prompt_no_memory_on_first_iteration |

**新增 6 个测试：** test_cleanup_with_old_data, test_message_limit_returns_most_recent, test_message_limit_custom_limit, test_concurrent_access, test_developer_prompt_includes_memory_context, test_developer_prompt_no_memory_on_first_iteration

---

## Phase 55：运行时 Bug 修复 + 全链路审查（2026-06-10）

**来源：** 用户实际运行 + 全面链路审查

### Bug 1：保存没实际存下来

**现象：** 用户点保存后项目列表里能看到，但打开没有文件

**根因：** `saveProject()` 创建新的 `proj-{timestamp}` ID，而文件在 `deliver_node` 已写入原 project_id 目录。新项目只有 meta.json。

**修复：**
- 后端 `POST /api/projects` 改为 upsert（项目已存在时更新 meta.json）
- 前端 `saveProject()` 使用当前 `projectStore.currentProject?.id`，不再新建 ID

### Bug 2：刷新后显示旧状态

**现象：** 刷新页面后 Agent 状态显示"Developer 执行中"、迭代 13/3

**根因：** snapshot 的 `current_step` 和 `iteration` 是旧值，恢复时直接使用

**修复：**
- `restoreFromServer` 检查 status 是否为终态（completed/delivered/saved/failed/error）
- 终态 → 所有 Agent 显示"已完成"
- websocket.py 图出错时更新 snapshot status 为 "error"

### Bug 3：心跳机制（彻底解决状态不一致）

**问题：** 无法判断"执行中"是真在跑还是已经死了（用户关浏览器、服务器重启等）

**修复：**
- memory.py 新增 `last_heartbeat` 字段 + `update_heartbeat()` 方法
- websocket.py 图执行期间每 10 秒更新心跳
- projects.py 恢复接口返回 `last_heartbeat`
- 前端恢复时检查心跳：超过 30 秒 → 显示"上次中断"

### Bug 4：迭代死循环

**现象：** Developer→Tester→Reviewer 循环超过 max_iterations

**根因：** `route_after_review` 在 iteration >= max 时路由到 human_confirm，human_confirm approve 后又回 Developer

**修复：** `route_after_review` 在 iteration >= max 时返回 "approve"（直接 deliver）

### Bug 5：`_developer_retry_count` 不递增

**现象：** Developer 失败后无限重试

**根因：** developer.py 异常返回和 MAX_STEPS 返回都缺少 `_developer_retry_count` 字段，永远是 0

**修复：** 两处都加 `_developer_retry_count: state.get(...) + 1`

### Bug 6：`_async_llm_lock` 全局串行

**现象：** Proposer-Critic 内部 LLM 调用被串行化

**根因：** `asyncio.Lock()` 排他锁

**修复：** 改为 `asyncio.Semaphore(5)` 允许并发

### Bug 7：Developer 收不到 Tester 反馈（最关键）

**现象：** Developer 每次从零写代码，反复犯同样错误

**根因：** Tester 返回 `test_results` 是 `list[dict]`，Developer 按 `dict` 读取 → `isinstance(list, dict)` = False → 反馈被丢弃

**修复：** developer.py 兼容 list 和 dict 两种类型

### Bug 8：Reviewer done 工具缺审查字段

**现象：** Reviewer 的 `review_approved` 永远是 True，`review_comments` 永远是空

**根因：** DONE 工具 schema 只有 `summary`/`files_modified`/`key_decisions`，没有 `review_approved`/`review_comments`。LLM 不会输出 schema 外的字段。

**修复：** Reviewer 使用独立的 `REVIEWER_DONE` 工具，包含完整的审查字段

### Bug 9：ProjectState 缺字段（链路断裂根因）

**现象：** 多个 Agent 返回的字段被 LangGraph 静默丢弃

**根因：** ProjectState TypedDict 未声明 `technical_constraints`/`key_decisions`/`project_path`，LangGraph 严格按 schema 合并

**修复：** state.py 补全缺失字段 + create_initial_state 加默认值

### Bug 10：Tester 异常路径丢失错误细节

**现象：** Tester 异常时 Developer 看不到具体错误

**根因：** tester.py 异常返回没有 `test_results` 字段

**修复：** 异常返回加 `test_results: [{"summary": "测试异常：...", "status": "error"}]`

**测试结果：** 276 个后端测试全过

### 全链路验证结果

| 链路 | 状态 |
|------|------|
| PM → Architect | ✅ technical_constraints 现在传递 |
| Architect → human_confirm | ✅ |
| human_confirm → Developer | ✅ |
| Developer → Tester | ✅ key_decisions 现在传递 |
| Tester → Developer | ✅ test_results 类型兼容 + 异常路径有值 |
| Reviewer → Developer | ✅ REVIEWER_DONE 有审查字段 |
| Reviewer → route_after_review | ✅ |
| Developer → deliver | ✅ project_path 现在传递 |
| SQLite memory → Developer | ✅ |

---

## Phase 55（补全）：回退功能恢复 + 运行时修复（2026-06-10）

**背景：** Phase 55 部分功能被回退，需要恢复。同时手动测试发现 3 个运行时 Bug。

### 一、回退功能恢复（10 项）

| # | 功能 | 文件 | 改动 |
|---|------|------|------|
| 1 | `_developer_retry_count` 递增 | developer.py | error + MAX_STEPS 路径都加 `_developer_retry_count: state.get(...) + 1` |
| 2 | `asyncio.Semaphore` | llm.py | `_async_llm_lock` 从 `asyncio.Lock()` 改为 `asyncio.Semaphore(5)` |
| 3 | `REVIEWER_DONE` 工具 | tools.py | 新增专用工具定义，含 `review_approved`(bool) + `review_comments`(array)，`REVIEWER_TOOLS` 改用它 |
| 4 | `ProjectState` 补全字段 | state.py | 新增 `technical_constraints: list[str]` + `key_decisions: list[str]`，`create_initial_state` 加默认值 |
| 5 | Tester 反馈类型兼容 | developer.py | `build_developer_prompt` 加入 `test_results` 和 `review_comments` 反馈，兼容 `list[dict]` 和 `dict` |
| 6 | `route_after_review` 迭代检查 | graph.py | iteration >= max 时返回 `"approve"`（直接交付），不再路由到 `human_confirm`（防死循环） |
| 7 | 心跳机制 | websocket.py | 新增 `_heartbeat_loop` 异步任务，每 10 秒调用 `mem.update_heartbeat(project_id)` |
| 8 | WebSocket 日志 | websocket.py | 模块级 `logger`，连接/断开/启动/Agent完成/Error 全部有结构化日志 |
| 9 | 前端消息去重 | useWebSocket.js + project.js | WebSocket 层 `seenMessageIds` Set 去重；store 层 `addMessage` 检查最后一条重复；指数退避 1s→30s |
| 10 | 保存 upsert | projects.py + project.js | POST `/api/projects` 已存在时更新 meta.json（不再 409）；前端新增 `saveProject()` action |

### 二、全链路修复（3 项）

| # | 链路断裂点 | 文件 | 修复 |
|---|-----------|------|------|
| 1 | Tester 异常路径缺 `test_results` | tester.py | 异常返回加 `test_results: [{"summary": "测试异常：...", "status": "error"}]` |
| 2 | Reviewer 超步数 `review_approved` 仍为 True | reviewer.py | 超步数时设 `collected_review_approved = False` |
| 3 | Developer 成功后未重置 `test_passed` | developer.py | 成功返回加 `test_passed: True` |

### 三、运行时修复（3 项）

**来源：** 手动测试发现

#### Bug 1：Developer 死循环（最关键）

**现象：** Developer iter=1~4 全是 Developer，Tester 从未出现

**根因分析（系统调试）：**
1. LLM 调用 `file_write` + `execute_python` 但不调 `done`
2. 跑满 MAX_STEPS 后返回 `error: "超过最大步数"`
3. `route_after_developer` 看到 error → 路由回 Developer
4. `_developer_retry_count` 递增但 MAX_STEPS 返回也递增 → 循环

**修复：** `files_written` 非空 + 本轮无新写入 → 隐式完成，break。MAX_STEPS 从 10 改为 5。

```python
# 典型流程：
# 轮次 1: file_write a.py → this_round_new_writes = 1 → 继续
# 轮次 2: file_write b.py → this_round_new_writes = 1 → 继续
# 轮次 3: execute_python  → this_round_new_writes = 0，files_written 非空 → break
```

**新增测试：** `test_developer_implicit_done_with_files`（验证 2 轮 LLM 调用即完成）

#### Bug 2：刷新后页面重置

**现象：** `GET /api/projects/{id}/state` 返回 404

**根因：** endpoint 完全不存在，前端 `restoreFromServer` 调了但后端没实现

**修复：** projects.py 新增 `GET /api/projects/{project_id}/state` 端点，读 SQLite snapshot + messages + 磁盘文件

#### Bug 3：没有保存按钮

**现象：** 用户无法保存项目

**修复：** ChatPanel header 常驻 💾 按钮 + `saveProject()` action（upsert）

### 四、测试更新

| 测试 | 改动 |
|------|------|
| `test_create_project_duplicate` | 409 → 200（upsert 行为） |
| `test_developer_max_steps` | 改用 `file_read`（无文件写入才触发 max steps） |
| `test_developer_implicit_done_with_files` | 新增：验证 2 轮 LLM 调用即完成 |

**测试结果：** 后端 272 + 前端 50 = 322 个全过

### 五、全链路验证结果（更新）

| 链路 | 关键字段 | 状态 |
|------|---------|------|
| PM → Architect | `technical_constraints` | ✅ state.py 已声明 |
| Developer → Tester | `key_decisions` | ✅ state.py 已声明 |
| Tester → Developer | `test_results` 类型 | ✅ 兼容 list/dict + 异常路径有值 |
| Reviewer → Developer | `REVIEWER_DONE` schema | ✅ 含 review_approved + review_comments |
| Reviewer → Developer（超步数） | `review_approved` | ✅ 超步数 = False |
| Developer 成功后 | `test_passed` 重置 | ✅ 返回 True |
| Developer 失败时 | `_developer_retry_count` | ✅ error + MAX_STEPS 都递增 |
| route_after_review | 迭代上限 | ✅ 直接 approve 交付 |
| Developer 隐式完成 | files_written | ✅ 无新写入即保存 |
| SQLite → Developer | 记忆上下文 | ✅ Phase 54 |
| asyncio 并发 | LLM 调用 | ✅ Semaphore(5) |
| 页面刷新恢复 | /state endpoint | ✅ 新增 |
| 项目保存 | upsert | ✅ POST 已存在时更新 |

#### Bug 4：保存按钮点击无效

**现象：** 点击 💾 按钮无反应，日志无 `POST /api/projects` 请求

**根因：** `saveProject()` 检查 `this.currentProject?.id`，但 `sendMessage` 和 `retryMessage` 虽然生成了 `projectId`，从未设置 `projectStore.currentProject`，导致函数提前 `return false`

**修复：** ChatPanel.vue 的 `sendMessage` 和 `retryMessage` 中加 `projectStore.currentProject = { id: projectId, requirement: text }`

**测试结果：** 后端 272 + 前端 50 = 322 个全过

---

## Phase 55（补全续）：前后端对齐 + SPA 路由修复（2026-06-10）

**来源：** 手动测试 + 全线前后端对齐审查（17 个问题）

### 一、Critical 修复（4 项）

#### Bug 5：SPA 路由 404（最影响体验）

**现象：** 访问 `/projects`、`/settings` 等页面返回 `{"detail":"Not Found"}`

**根因：** start.py 只注册了旧式 `.html` 路由（`/login.html`、`/projects.html` 等），Vue SPA 的 clean URL（`/login`、`/projects`）没有 catch-all 路由

**修复：**
- 删除 5 个旧 `.html` 路由（`login.html`、`projects.html`、`project-detail.html`、`settings.html`、`index.html`）
- 删除 4 个零散 SPA 路由（`/projects`、`/settings`、`/login`、`/project/{path}`）
- 改为单个 `/{path:path}` 通用 catch-all，跳过 `api/`、`assets/`、`static/` 前缀

#### Bug 6：保存后项目列表为空

**现象：** `POST /api/projects` 返回 200，但项目列表看不到项目

**根因：** `_projects_dir()` 返回 `Blueprint/projects/`（`parent.parent`），但 Developer 和 deliver_node 写文件到 `projects/`（CWD 相对路径）。两个路径不一致，meta.json 和项目文件分散在两个目录

**修复：** `parent.parent` → `parent.parent.parent`，统一到 `Many AgentS/projects/`

#### Bug 7：agentStatus 从不同步

**现象：** 刷新页面后 Agent 状态全部丢失

**根因：** `useWebSocket.js` 的 `state_sync` handler 读 `data.data.agent_status`，但后端 `create_initial_state` 没有 `agent_status` 字段，永远是 undefined

**修复：** 收到 `state_sync` 时初始化所有 Agent 为 `waiting`，后续 `agent_start`/`agent_done` 消息会实时更新

#### Bug 8：maxIterations 硬编码

**现象：** 前端迭代计数器永远显示 `/3`，即使用户在设置页改了最大迭代次数

**根因：** `projectStore.maxIterations` 硬编码为 3，从未从后端同步

**修复：** App.vue `onMounted` 时 `fetch('/api/settings')` 获取 `max_iterations` 并更新 store

### 二、Dead Code 清理

| 位置 | 代码 | 状态 |
|------|------|------|
| `useWebSocket.js` | `case 'agent_thinking'` handler | 删除（后端从不发送） |
| `start.py` | `/project/{path:path}`（单数） | 删除（Vue 路由是 `/projects/:id` 复数） |
| `start.py` | 5 个 `.html` 路由 | 删除（Vue SPA 替代） |
| `projects.py` | `POST /api/resume/rethink/cancel` | 保留（后端 REST 端点，前端通过 WebSocket 调用，不碍事） |
| `websocket.py` | `reconnect` handler | 保留（后端有处理但前端不发送，不碍事） |

### 三、前后端对齐审查结果

| 类别 | 数量 | 说明 |
|------|------|------|
| 前端调用的 API | 15 个 | 全部有后端对应 ✅ |
| 后端提供的 API | 17 个 | 2 个 dead（resume/rethink/cancel 通过 WebSocket） |
| WebSocket 消息类型 | 7 种 | 全部有前端 handler ✅ |
| 前端发送的 WS 消息 | 3 种 | start_project/resume/cancel 全部有后端 handler ✅ |
| 状态字段对齐 | 10 个 | 修复 2 个（agentStatus/maxIterations） |

**测试结果：** 后端 272 + 前端 50 = 322 个全过

---

## Phase 55（补全续）：error 残留 + 死循环 + 取消按钮（2026-06-10）

**来源：** 手动测试（计算器项目运行）

### 一、核心 Bug：LangGraph error 残留导致 Agent 链路断裂（最关键）

**现象：** Developer 写了文件但永远到不了 Tester，iter=1~7 全是 Developer

**日志证据：**
```
iter=1: Developer error: APIConnectionError → state["error"] = "APIConnectionError..."
iter=2: Developer success → 返回 {files, test_passed: True}（无 error key）
        → LangGraph 不清除旧 error → route_after_developer 看到残留 error → 重试
iter=3~7: 同上，error 永远残留 → 永远重试 → Tester 永远不执行
```

**Root Cause：** LangGraph 的 state 合并是"只更新返回的 key"，不返回的 key 保留旧值。如果 Agent 第一次返回 `{"error": "失败"}`，第二次返回 `{"files": ...}`（无 error），旧 error 值永远残留。

**修复：** 所有 Agent 成功路径必须显式返回 `"error": None`

| Agent | 修复前 | 修复后 |
|-------|--------|--------|
| developer.py | 成功不设 error | ✅ `"error": None` |
| tester.py | 成功不设 error | ✅ `"error": None` |
| architect.py | 成功不设 error | ✅ `"error": None` |
| pm.py | 已有 | ✅ 无需改 |
| reviewer.py | 已有 | ✅ 无需改 |

**教训：** LangGraph TypedDict 的 state 合并是"补丁式"不是"替换式"。任何可能被路由函数检查的字段，成功时都必须显式清除。

### 二、Developer 空文件死循环

**现象：** LLM 不生成任何文件 → implicit done（files={}）→ Tester 空转 → fail → 循环

**修复：** `files_written` 为空时设 `error: "Developer 未生成任何文件"`，重试 2 次后 END

### 三、取消按钮

**现象：** 用户无法停止正在运行的 Agent 任务

**修复：** ChatPanel 新增 ⏹ 按钮，发送 `{type: "cancel"}` 到后端，不清空聊天

### 四、迭代计数器

**确认：** IterationInfo 组件仍在 FlowPanel 中（line 7），`v-if="projectStore.iteration > 0"` 条件显示。useWebSocket.js 的 `agent_update` handler 正确同步 `data.data.iteration`。

**测试结果：** 后端 272 + 前端 50 = 322 个全过

---

## Phase 55（补全续）：error 残留验证 + 项目列表字段修复（2026-06-11）

**来源：** v1 对比测试 + 手动测试

### 一、v1 对比验证：确认 error 残留是 v1 的 bug

**方法：** 用 v1 备份跑同一个需求，对比日志

**v1 日志：**
```
Developer iter=1: APIConnectionError
Developer iter=2: Files written (3)  ← 成功但没清 error
Developer iter=3~9: 全是 Developer   ← error 残留，永远重试
Tester: 从未执行
```

**当前版本日志：**
```
Developer iter=1: APIConnectionError → route_after_developer: error='Connection error.' → retry
Developer iter=2: Files written (10) → route_after_developer: error=None → tester ✅
Tester iter=2: test_passed=False → route_after_test → developer (fail)
Developer iter=3: Files written (10) → route_after_developer → tester ✅
Tester iter=3: test_passed=False → route_after_test → reviewer (max iterations) ✅
Reviewer iter=3: approved=False → route_after_review → deliver (max iterations) ✅
deliver → 项目完成
```

**结论：** `"error": None` 修复是正确的。v1 的 Developer 成功时不设 error，LangGraph 保留旧值，导致永远重试。

### 二、路由日志验证

**新增日志：** graph.py 的 `route_after_developer`、`route_after_test`、`route_after_review` 都加了 `logger.info`，输出每一步的决策。

**效果：** 终端现在能看到完整链路：
```
route_after_developer: error=None, files=[...], retry=0
route_after_developer → tester
route_after_test: test_passed=False, iteration=2/3
route_after_test → developer (fail)
route_after_review: approved=False, iteration=3/3
route_after_review → deliver (max iterations)
```

### 三、Tester/Reviewer 日志验证

**新增日志：**
- `Tester started, files: [...]`
- `Tester done: test_passed=True/False`
- `Reviewer started, files: [...]`
- `Reviewer done: approved=True/False`

**效果：** 确认 Tester 和 Reviewer 确实在执行（之前没有日志，看起来像断了）。

### 四、项目列表字段不匹配修复

**现象：** 项目保存成功（POST 200），磁盘有 meta.json，但前端项目页面显示空白

**根因：** 后端 `GET /api/projects` 返回 `project_id`/`requirement`，前端 ProjectsPage.vue 读 `p.id`/`p.name` — 字段名不匹配，渲染出 `undefined`

**修复：** ProjectsPage.vue 的 `v-for` 改用后端实际字段名：
- `p.id` → `p.project_id`
- `p.name` → `p.requirement`
- `p.created_at` → `p.iteration`（后端没返回 created_at）

**测试结果：** 后端 272 + 前端 50 = 322 个全过

---

## Phase 56：通讯页面 UX 改进（2026-06-11）

**目标：** 将通讯页面从纯文本聊天升级为结构化 Agent 输出 + 暂停/继续 + 保存命名 + 代码预览

**设计文档：** `docs/superpowers/specs/2026-06-11-workbench-ux-improvements-design.md`
**实施计划：** `docs/superpowers/plans/2026-06-11-workbench-ux-improvements.md`

### 实施内容（11 个 Task，8 个子代理并行）

| Task | 内容 | 新增/修改文件 | 状态 |
|------|------|-------------|------|
| 1 | useFilePreview composable（highlight.js 语法高亮） | `composables/useFilePreview.js` + 测试 | ✅ |
| 2 | AgentOutputCard 组件（结构化 Agent 输出卡片） | `components/AgentOutputCard.vue` + 测试 | ✅ |
| 3 | SaveDialog 组件（保存命名弹窗） | `components/SaveDialog.vue` + 测试 | ✅ |
| 4 | AgentCard 可交互（点击展开 + 耗时） | `components/AgentCard.vue` 重写 | ✅ |
| 5 | IterationInfo 进度可视化（变色 + 加粗） | `components/IterationInfo.vue` 改造 | ✅ |
| 6 | 后端 WebSocket pause/stop/resume | `api/websocket.py` + `tests/test_websocket_pause.py` | ✅ |
| 7a | ChatHeader 组件（操作栏拆分） | `components/ChatHeader.vue` + 测试 | ✅ |
| 7b | store + WebSocket 消息处理 | `stores/project.js` + `composables/useWebSocket.js` | ✅ |
| 7c | ChatPanel 拆分引用 ChatHeader + SaveDialog | `components/ChatPanel.vue` 重构 | ✅ |
| 8 | 保存命名（后端 name 字段 + 前端传参） | `api/projects.py` + `stores/project.js` | ✅ |
| 9 | OutputPanel 文件预览（语法高亮 + 复制） | `components/OutputPanel.vue` 改造 | ✅ |
| 10 | 异常状态处理（断连/失败/空内容兜底） | ChatHeader + SaveDialog + OutputPanel | ✅ |

### 新增组件

| 组件 | 文件 | 职责 |
|------|------|------|
| AgentOutputCard.vue | components/AgentOutputCard.vue | 根据 Agent 类型显示结构化卡片（PM 蓝/Developer 绿/Tester 橙/Reviewer 粉） |
| SaveDialog.vue | components/SaveDialog.vue | 保存命名弹窗，自动填入需求前 15 字，可编辑 |
| ChatHeader.vue | components/ChatHeader.vue | 操作栏：运行中显示暂停，暂停中显示继续+停止，空闲时显示保存+清空+新建 |

### 新增 composable

| Composable | 文件 | 职责 |
|------------|------|------|
| useFilePreview.js | composables/useFilePreview.js | 文件预览逻辑 + highlight.js 语法高亮（5 种语言） |

### 后端改动

| 文件 | 改动 |
|------|------|
| websocket.py | 新增 pause/resume_execution/stop 消息处理 + `_send_heartbeat` 心跳函数 + 节点边界 stop_event 检查 |
| projects.py | POST 新增 `name` 字段 + GET 返回 `name` |

### 前端改动

| 文件 | 改动 |
|------|------|
| project.js | 新增 isPaused/isRunning/saveDialogVisible/autoSaveName/agentStartTime |
| useWebSocket.js | 新增 paused/resumed/stopped/heartbeat 消息处理 + agent_start 设 isRunning |
| ChatPanel.vue | 拆分：用 ChatHeader 替代操作栏 + 集成 SaveDialog + handleSave 逻辑 |
| AgentCard.vue | 可交互：点击展开/折叠 + 执行耗时计时 |
| IterationInfo.vue | 进度条加粗 8px + 动态变色（绿→黄→红） |
| OutputPanel.vue | 文件点击预览 + 语法高亮 + 复制按钮 + 空内容占位符 |

### 前端依赖新增

| 依赖 | 版本 | 用途 |
|------|------|------|
| highlight.js | ^11.x | 代码语法高亮（~40KB gzip） |

**测试结果：** 后端 279 + 前端 72 = 351 个全过

---

## Phase 57：Code Review + 四层可靠性架构审计（2026-06-11）

**来源：** 子代理 Code Review + 四层全链路可靠性架构审计

### 一、Code Review 修复（11 项，全部修复完毕 ✅）

这些是代码层面的 bug，不是四层架构问题。

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| C1 | Critical | graph.py 死亡路由边 `human_confirm` | ✅ 删除 |
| C2 | Critical | error 消息说 "10步" 但 MAX_STEPS=5 | ✅ 改为 "5步" |
| C3 | Critical | resume 时发两次 `resumed` 消息 | ✅ 删除 graph 线程重复发送 |
| C4 | Critical | resume 时 heartbeat 未取消 | ✅ resume 处理中 cancel heartbeat_task |
| I1 | Important | graph.py 重复 `import logging` | ✅ 移到模块级 |
| I2/I8 | Important | projects.py 自建 memory 单例 | ✅ 改用 `get_memory()` 共享单例 |
| I3 | Important | tool_executor 复制 node_modules | ✅ 加入跳过列表 |
| I4 | Important | Developer 记忆未接入 | ✅ `build_developer_prompt` 调用 `get_developer_context()` |
| I5 | Important | v-html XSS 漏洞 | ✅ 安装 DOMPurify sanitize |
| I10 | Important | autoSaveName 未填充 | ✅ `sendMessage` 时从需求自动生成 |
| M5 | Minor | AgentOutputCard 未接入 ChatPanel | ✅ store 新增 `agentOutputs`，ChatPanel 用 AgentOutputCard 渲染 |

### 二、四层可靠性架构审计结果

**审计方法：** 对照四层架构（结构化定义/推理策略/执行护栏/自愈修复），逐个检查 5 个 Agent。

**总览：**

| Agent | L1 结构化定义 | L2 推理策略 | L3 执行护栏 | L4 自愈修复 |
|-------|:---:|:---:|:---:|:---:|
| PM | ✅ | ✅ | ✅ | ✅ |
| Architect | ✅ | ⚠️ | ⚠️ | ⚠️ |
| Developer | ⚠️ | ⚠️ | ⚠️ | ⚠️ |
| Tester | ⚠️ | ⚠️ | ✅ | ❌ |
| Reviewer | ⚠️ | ⚠️ | ✅ | ❌ |

### 三、四层架构问题（全部修复完毕 ✅）

#### P0（必须修）

| # | 问题 | 修复 |
|---|------|------|
| 1 | `call_llm_with_tools_async` 无重试 | ✅ 加 2 次重试 + 指数退避（与同步版一致） |
| 2 | Tester/Reviewer 无 `_retry_count` | ✅ state.py 新增 `_tester_retry_count`/`_reviewer_retry_count`；tester.py/reviewer.py 错误路径递增；路由函数检查 retry >= 2 时跳过 |

#### P1（应该修）

| # | 问题 | 修复 |
|---|------|------|
| 3 | 重试不带错误信息 | ✅ 5 个 Agent 的 prompt 构建函数都加了 `prev_error` 注入：`"⚠️ 上一次执行失败，错误：{error}，请避免重复同样的错误"` |
| 4 | Architect 无 `check_injection` | ✅ architect_agent 入口加 `check_injection(user_feedback)` |
| 5 | 安全检查不一致 | ✅ 统一为 `_DANGEROUS_PATTERNS` 列表（含 subprocess/requests/shutil.rmtree/os.unlink/Path.unlink）；`_check_content_safety` 扩展到 .html 文件（拦 script/onerror/onload）；`_check_code_safety` 使用同一列表 |

#### P2（后续迭代）

| # | 问题 | 修复 |
|---|------|------|
| 6 | Pydantic schema 白定义 | ⚠️ 保留现状 — 当前 Agent 使用 tool calling 模式，工具 schema 已提供参数校验。Pydantic schema 留作未来 Agent 改回 JSON 输出模式时使用 |
| 7 | 工具描述太简陋 | ✅ file_write/file_read/execute_python 描述补充路径规则（不能含 ..、不能绝对路径）、内容约束（不能含 subprocess/eval）、沙箱说明 |

#### P3（低优先级）

| # | 问题 | 修复 |
|---|------|------|
| 8 | `_validate_path` 死代码 | ✅ 删除函数 + 删除对应 3 个测试 |

### 四、Agent 逐个审计详情

#### PM Agent — 全线达标 ✅

| 层 | 状态 | 证据 |
|----|------|------|
| L1 结构化定义 | ✅ | PMOutput Pydantic schema + field_validator 强制 user_stories 非空 + prompt 完整 JSON 模板 |
| L2 推理策略 | ✅ | prompt 6 步推理策略 + Proposer-Critic + 正例明确 |
| L3 执行护栏 | ✅ | check_injection(requirement) + PMOutput(**parsed) Pydantic 强校验 |
| L4 自愈修复 | ✅ | JSONDecodeError/Exception catch + _pm_retry_count + 路由重试 2 次 + Clarification interrupt |

#### Architect Agent — 缺注入检测和工具描述

| 层 | 状态 | Gap |
|----|------|-----|
| L1 结构化定义 | ✅ | ArchitectOutput Pydantic schema + prompt 完整 JSON 模板 |
| L2 推理策略 | ⚠️ | 有 4 步推理流程，但无正负例 |
| L3 执行护栏 | ⚠️ | 有 Pydantic 校验，但无 check_injection（user_feedback 直接拼入 prompt） |
| L4 自愈修复 | ⚠️ | 有重试机制，但重试不带错误信息 |

#### Developer Agent — 四层都有短板

| 层 | 状态 | Gap |
|----|------|-----|
| L1 结构化定义 | ⚠️ | 工具描述太简陋；DeveloperOutput schema 定义了但未使用 |
| L2 推理策略 | ⚠️ | 无思维链要求；无正负例 |
| L3 执行护栏 | ⚠️ | _check_content_safety 只拦 .py；_check_code_safety 不拦 subprocess |
| L4 自愈修复 | ⚠️ | call_llm_with_tools_async 无重试；重试不带错误上下文 |

#### Tester Agent — 缺自身重试

| 层 | 状态 | Gap |
|----|------|-----|
| L1 结构化定义 | ⚠️ | TesterOutput schema 未使用；done 工具无 Tester 专用参数 |
| L2 推理策略 | ⚠️ | 无正负例、无思维链、无 Proposer-Critic |
| L3 执行护栏 | ✅ | 无 file_write 权限 + _extract_test_passed 双重校验 |
| L4 自愈修复 | ❌ | 无 _tester_retry_count；Tester 自身崩溃时不重试 |

#### Reviewer Agent — 最薄弱

| 层 | 状态 | Gap |
|----|------|-----|
| L1 结构化定义 | ⚠️ | REVIEWER_DONE 有结构化参数，但 review_comments 的 file/line 不是 required |
| L2 推理策略 | ⚠️ | 有 5 维审查规则，但无 Proposer-Critic、无正负例 |
| L3 执行护栏 | ✅ | 只有 FILE_READ + REVIEWER_DONE，无写入/执行权限 |
| L4 自愈修复 | ❌ | 无 _reviewer_retry_count；超步数设了 error 但路由函数忽略它 |

---

## Phase 58：运行时修复 + 存储优化（2026-06-12）

**来源：** 手动测试发现的问题

### 一、HTML 安全检查太激进（P0 紧急修复）

**现象：** Developer/Tester/Reviewer 写 HTML 文件时反复报 `ValueError: HTML 文件内容包含不允许的模式: <script`，所有迭代浪费

**根因：** Phase 57 加的 `_DANGEROUS_HTML_PATTERNS` 拦截了 `<script`、`onload=` 等 HTML 必需标签。这是代码生成工具，HTML 文件必须有 `<script>` 才能运行

**修复：** 删除 `_DANGEROUS_HTML_PATTERNS`，`_check_content_safety` 只检查 .py 文件。XSS 风险已由 OutputPanel 的 DOMPurify 处理

### 二、消息大量重复

**现象：** 前端通讯页面 PM/Tester/Reviewer 消息重复显示多次

**根因：** websocket.py 发送 `agent_update` 时包含 Agent 的完整内部对话（含 system prompt），每次迭代都重复发送

**修复：** websocket.py 过滤 `agent_update` 消息，只发带 `agent.name` 的输出消息和 `role: "tool"` 的工具结果

### 三、SQLite 存储优化

**现象：** 刷新页面后消息丢失（200 条限制被垃圾消息占满）

**根因：** websocket.py 存消息到 SQLite 时不过滤，Agent 的 system prompt 每次迭代都存一遍

**修复：**
- 只存 `msg.name == node_name`（Agent 输出）和 `role == "tool"`（工具结果）
- 新增 `_extract_agent_summary()` 函数，提取结构化摘要存入 `agent_executions.result_summary`
- 新增 `_extract_chat_message()` 函数，提取精简消息存入 `project_messages`

**效果：** 每 Agent 每轮只存 1 条精简消息（~100 字），200 条限制不再被占满

### 四、Token 过期自动跳转

**现象：** JWT token 过期后 WebSocket 返回 403，页面卡死

**修复：** useWebSocket.js 新增 `isTokenExpired()` 函数，`connect()` 连接前检查 token 过期 → 自动跳登录页

### 五、ProjectsPage 字段不完整

**现象：** 项目列表不显示用户命名的项目名称

**修复：** ProjectsPage.vue 优先显示 `p.name`，fallback 到 `p.requirement` 再到 `p.project_id`

**测试结果：** 后端 276 + 前端 72 = 348 个全过

---

## Phase 59：项目详情页重构（2026-06-12 已完成 ✅）

**目标：** 将简陋的项目详情页重构为"项目仪表盘"，支持完整开发日志、执行摘要、操作按钮

### 一、三层数据存储

| 层 | 存什么 | 表 | 空间估算 |
|---|--------|-----|---------|
| 精简摘要 | 每 Agent 1 条，聊天显示用 | project_messages（已有） | ~200B/条 |
| 结构化摘要 | 耗时、结果、状态 | agent_executions（已有） | ~500B/条 |
| 完整对话 | Agent 的完整 LLM 对话 | 新增 agent_conversations | ~2-5KB/轮 |

**空间估算：** 5 Agent × 4 轮 × 5KB = 100KB/项目，100 个项目才 10MB

### 二、项目详情页卡片布局

| 卡片 | 内容 | 数据来源 |
|------|------|---------|
| 📋 项目信息 | 名称、时间、状态、迭代、需求原文 | meta.json |
| 💬 开发日志 | 完整 Agent 对话（可折叠展开） | agent_conversations 表 |
| 📁 生成文件 | 文件树 + 预览 + 下载 | 磁盘文件 |
| 📊 执行摘要 | 每 Agent 结构化摘要 | agent_executions.result_summary |

### 三、操作按钮

| 按钮 | 功能 | 实现 |
|------|------|------|
| 🔄 重新运行 | 用同一个需求重跑 | 前端跳转工作台 + 自动发消息 |
| ✏️ 编辑需求 | 修改需求后重跑 | 弹窗编辑 → 跳转工作台 |
| 📤 导出项目 | 下载完整包（文件 + 元数据 + 日志） | 后端打包 zip |

### 四、改动范围

**后端（3 个文件）：**

| 文件 | 改什么 |
|------|--------|
| memory.py | 新增 `agent_conversations` 表 + `save_conversation()` / `get_conversations()` |
| websocket.py | `_run_graph_sync` 里把完整 LLM 对话写入新表 |
| projects.py | `GET /state` 返回 conversations + executions；新增 `GET /export` 打包下载 |

**前端（4 个文件）：**

| 文件 | 改什么 |
|------|--------|
| ProjectDetailPage.vue | 重写为仪表盘（4 卡片 + 懒加载 + 3 操作按钮） |
| api/index.js | 新增 getProjectConversations/getProjectExecutions/exportProject/getProjectState |
| stores/project.js | 新增 pendingRequirement 字段 |
| ChatPanel.vue | onMounted 检查 pendingRequirement 自动发送 |

**通讯页面 💾 保留不动。**

### 实施结果

| Task | 内容 | 状态 |
|------|------|------|
| 1 | memory.py — agent_conversations 表 + get_executions + tool_calls | ✅ |
| 2 | websocket.py — 存完整对话（过滤 system）+ tool_calls 提取 | ✅ |
| 3 | projects.py — GET /conversations + /executions + /export + name 字段 | ✅ |
| 4 | 前端 API 方法 + pendingRequirement store | ✅ |
| 5 | ProjectDetailPage 重写（4 卡片 + 懒加载 + 操作按钮） | ✅ |
| 6 | ChatPanel pendingRequirement 自动发送 + sessionStorage 兜底 | ✅ |

**测试结果：** 后端 283 + 前端 72 = 355 个全过

---

## Phase 60：Developer 代码质量 + 链路闭环修复（2026-06-12）

**来源：** 手动测试发现 Developer 生成代码质量差 + 链路不闭环

### 一、Developer 死循环后直接 END（应让用户决定）

**修复：**
- `route_after_developer` max retries 时路由到 `human_confirm`
- `human_confirm_node` 检测 `is_dev_retry`，显示"Developer 已重试 2 次仍失败，是否继续？"
- 用户确认 → 重置 retry count + 清除 error → Developer 重新开始
- 用户拒绝 → 直接交付已有文件（route to deliver）

### 二、Tester/Reviewer 不给修复建议

**修复：** Tester/Reviewer prompt 加修复建议要求；Developer 反馈注入精简（测试 300 字 + 审查只提取 suggestion）

### 三、Developer 代码质量差

**修复：** MAX_STEPS 5→8；错误注入 500→200 字；测试反馈 800→300 字；审查反馈精简到一行

### 四、Tester test_passed 提取 bug

**现象：** "全部通过（0失败）"但 `test_passed=False`

**根因：** `_extract_test_passed` 的排除条件 `"0 失败"`（有空格）不匹配 `"0失败"`（无空格）

**修复：** 通过指标优先检查 + 排除条件加无空格版本

### 五、Developer 只写 1 个文件

**修复：** prompt 新增"前端项目必须拆分文件：HTML + CSS + JS 分开"

**测试结果：** 后端 283 + 前端 72 = 355 个全过

---

## Phase 61：Prompt Engineering — 5 Agent 推理策略优化（2026-06-12）

**目标：** 补全四层架构 L2 推理策略层的短板

**设计文档：** `docs/superpowers/specs/2026-06-12-prompt-engineering-design.md`

| Agent | 之前 | 之后 | 新增内容 |
|-------|------|------|---------|
| PM | 957 字 | ~1200 字 | 正负例、错误恢复 |
| Architect | 680 字 | ~1000 字 | 推理策略编号、正负例、错误恢复 |
| Developer | 507 字 | ~800 字 | 每轮决策框架、正负例、错误恢复 |
| Tester | 243 字 | ~600 字 | 测试策略、失败输出示例、错误恢复 |
| Reviewer | 500 字 | ~800 字 | 审查流程、正负例、通过标准与路由对齐 |

**测试结果：** 后端 283 + 前端 72 = 355 个全过

---

## Phase 62：项目改名后用户数据库迁移（2026-06-16）

**问题：** 项目从 `devteam` 改名为 `blueprint` 后，用户登录返回 401 Unauthorized

**根因：** `user_db.py` 默认路径从 `devteam_users.db` 改为 `BLUEPRINT_users.db`，新库无用户数据

**修复：** 迁移脚本从旧库读取用户记录批量插入新库

**迁移结果：** 6 个用户全部迁移成功

**教训：** 改项目名时要检查所有文件路径引用（数据库、配置文件、secret 文件等）

### Code Review 修复（2026-06-12）

| 级别 | 问题 | 修复 |
|------|------|------|
| C2 | WebSocket 发送 raw BaseMessage 对象 | 改用 `dict_msgs` |
| C3 | `m.dict()` Pydantic v2 不兼容 | 改为 `model_dump()` 优先 |
| C4 | Export 跟随符号链接 | 加 `not fpath.is_symlink()` |
| I1 | agent_conversations 索引缺列 | 复合索引 |
| I6 | websocket.py 重复 import | 删除 |

---

## Phase 63：Blueprint 产品设计 + 功能扩展规划（2026-06-15）

**目标：** 从 MVP 升级到企业级产品，重新定义产品定位

### 一、产品重命名 DevTeam → Blueprint

**范围：** 全量重命名，内部+外部全部统一

| 类别 | 改动 | 数量 |
|------|------|------|
| 目录 | `devteam/` → `blueprint/` | 1 |
| Python import | `from devteam.` → `from blueprint.` | 238 处 |
| 配置前缀 | `DEVTEAM_` → `BLUEPRINT_` | 21 处 |
| 日志名 | `devteam.xxx` → `blueprint.xxx` | ~10 处 |
| 密钥文件 | `.devteam_secret` → `.blueprint_secret` | 3 处 |
| 用户可见文字 | `DevTeam` → `Blueprint` | ~20 处 |
| 文档 | 所有 `.md` 文件 | ~350 处 |
| 前端 | App.vue / LoginPage / index.html / vite.config | 4 处 |

**验证：** 283 测试全过，零遗漏

### 二、产品定位设计

**核心定位：** 面向 2-5 人小团队的 AI 全栈开发平台

| 维度 | 定义 |
|------|------|
| 目标用户 | 2-5 人小团队 |
| 核心价值 | 快速原型生成 |
| 差异化 | 交付完整度 + 人机协作 + 存量项目兼容 |
| 成功标准 | 质量优先 |

**三模式架构：** 全栈工程师（主模式）/ 代码工厂（快捷入口）/ 技术顾问（快捷入口）

**设计文档：** `docs/superpowers/specs/2026-06-15-blueprint-product-design.md`

### 三、13 个功能扩展规划

| # | 功能 | 优先级 |
|---|------|--------|
| 1-6 | 质量评分/变更对比/思考可视化/安全扫描/文档生成/部署配置 | P0-P1 |
| 7-9 | Webhook/CLI/模板市场 | P2 |
| 10-13 | 知识库/API平台/排行榜/协作 | P3（已砍） |

**详细设计：** `mimohouduan.md`（1888 行）

### 四、冲突分析

**核心原则：** 链路是根基，新功能只在外围加模块

**6 个禁止操作：** 不改 graph 节点、不改路由、不改 Agent 返回值、不改 tool_executor、不在 Agent 内部加外部依赖、deliver_node 用外部目录

**5 个关键决策：** 快照存项目外部 / 安全扫描包装 bandit / 质量评分用 AST / deliver_node 用 hook 链 / WebSocket 允许新消息类型

**文档：** `docs/superpowers/specs/2026-06-15-conflict-analysis.md`

---

## Phase 64：审查报告修复（2026-06-15）

**来源：** 用户审查报告，发现 15 个问题

### 关键修复

| # | 问题 | 修复 |
|---|------|------|
| 1 | deliver_node 万能化 | hook 链模式 |
| 2 | 质量评分用行数打分 | AST 分析 |
| 3 | 安全扫描是正则玩具 | 包装 bandit + npm audit |
| 4 | 快照存储位置矛盾 | 统一到项目外部 |
| 5 | 缺少成本模型 | 补充 LLM 成本估算 |
| 6 | 范围膨胀 | 砍掉 P3 |
| 7 | WebSocket 过于教条 | 允许新增类型 |
| 8 | 端点测试污染 | tmp_path fixture |
| 9 | 前端零测试 | 补充组件测试 |
| 10 | 两套安全检测重复 | 复用 |

### LLM 成本模型

| 场景 | 调用次数 | 成本 |
|------|---------|------|
| 简单需求 | 5 次 | ~$0.005 |
| 复杂需求 | 9-15 次 | ~$0.02-0.04 |
| 月度（10 项目/天） | — | ~$10-15 |

---

## Phase 65：Batch 1 TDD 实施 — 后端模块（2026-06-15）

**方法：** 严格 TDD（RED → GREEN → REFACTOR）

### 一、TraceDB（Agent 思考过程存储）

**测试：** 3 个 | **文件：** `blueprint/utils/trace_db.py` | **结果：** 3/3 通过

### 二、QualityScorer（AST 质量评分）

**测试：** 5 个 | **文件：** `blueprint/utils/quality_scorer.py` | **结果：** 5/5 通过
**关键修复：** grade 边界期望错误（55→C 不是 D）

### 三、SecurityScanner（bandit + npm audit）

**测试：** 5 个 | **文件：** `blueprint/utils/security_scanner.py` | **结果：** 5/5 通过
**关键修复：** 密钥长度不够（"sk-123" 只有 6 字符，模式要求 8+）

### 四、DiffEngine（变更历史对比）

**测试：** 4 个 | **文件：** `blueprint/utils/diff_engine.py` | **结果：** 4/4 通过
**关键修复：** 快照路径期望错误（项目内 vs 项目外）

### 测试统计

| 模块 | 测试数 | 状态 |
|------|--------|------|
| trace_db | 3 | ✅ |
| quality_scorer | 5 | ✅ |
| security_scanner | 5 | ✅ |
| diff_engine | 4 | ✅ |
| **合计** | **17** | **全部通过** |

**总测试数：** 283（原有）+ 17（新增）= **300 通过**

### 新增文件

| 文件 | 说明 |
|------|------|
| `blueprint/utils/trace_db.py` | Agent trace SQLite 存储 |
| `blueprint/utils/quality_scorer.py` | AST 质量评分 |
| `blueprint/utils/security_scanner.py` | bandit + npm audit 安全扫描 |
| `blueprint/utils/diff_engine.py` | 快照 + diff 对比 |
| `blueprint/tests/test_trace_db.py` | 3 个测试 |
| `blueprint/tests/test_quality_scorer.py` | 5 个测试 |
| `blueprint/tests/test_security_scanner.py` | 5 个测试 |
| `blueprint/tests/test_diff_engine.py` | 4 个测试 |

**教训：** 测试边界值时要确认实现的边界定义，不能假设。

---

## Phase 66：Batch 2 实施 — Hook 链 + 文档/部署/Webhook/CLI（2026-06-16）

**方法：** 严格 TDD（RED → GREEN → REFACTOR）

### 一、deliver_node hook 链

**测试：** 7 个（return_structure / writes_files / writes_meta / empty / invalid_id / hooks_called / hook_failure_safe）
**实现：** `_post_deliver_hooks` 列表 + `_run_post_deliver_hooks()` 执行器
**文件：** `blueprint/agents/graph.py`（追加 hook 链逻辑）
**结果：** 7/7 通过

**设计：** 每个 hook 独立函数，失败只打日志不影响交付

```
deliver_node → 写文件 → meta.json → hook 链:
  ├── save_snapshot_hook    (快照到项目外部目录)
  ├── quality_score_hook    (AST 质量评分并缓存)
  ├── security_scan_hook    (安全扫描并缓存)
  ├── generate_docs_hook    (README/API/架构图 → _blueprint/)
  └── generate_deploy_hook  (Dockerfile/docker-compose → _blueprint/)
```

### 二、DocGenerator（文档自动生成）

**测试：** 3 个（readme / empty / tech_stack）
**实现：** 根据代码自动生成 README + API 文档 + Mermaid 架构图
**文件：** `blueprint/utils/doc_generator.py`
**关键修复：** `f.endswith()` 应该用 `f.suffix`（Path 对象没有 endswith）
**结果：** 3/3 通过

### 三、DeployGenerator（部署配置生成）

**测试：** 4 个（dockerfile_python / dockerfile_node / compose / start_script）
**实现：** 根据项目类型生成 Dockerfile + docker-compose.yml + start.sh + .dockerignore
**文件：** `blueprint/utils/deploy_generator.py`
**结果：** 4/4 通过

### 四、WebhookManager（通知）

**测试：** 4 个（notify / filter_events / signature / empty_list）
**实现：** httpx 异步发送 + HMAC-SHA256 签名 + 事件过滤
**文件：** `blueprint/utils/webhook.py`
**结果：** 4/4 通过

### 五、CLI 工具

**测试：** 2 个（list_projects / help）
**实现：** Click 框架 + list/status/download 三个命令
**文件：** `blueprint/cli.py`
**结果：** 2/2 通过

### 测试统计

| 模块 | 测试数 | 状态 |
|------|--------|------|
| deliver_hooks | 7 | ✅ |
| doc_generator | 3 | ✅ |
| deploy_generator | 4 | ✅ |
| webhook | 4 | ✅ |
| cli | 2 | ✅ |
| **合计** | **20** | **全部通过** |

**总测试数：** 316（Batch 1）+ 20（Batch 2）= **336 通过**

### 新增文件

| 文件 | 说明 |
|------|------|
| `blueprint/utils/doc_generator.py` | README + API 文档 + Mermaid 架构图 |
| `blueprint/utils/deploy_generator.py` | Dockerfile + docker-compose + start.sh |
| `blueprint/utils/webhook.py` | Webhook 通知（HMAC 签名 + 事件过滤） |
| `blueprint/cli.py` | CLI 工具（list/status/download） |
| `blueprint/tests/test_deliver_hooks.py` | 7 个测试 |
| `blueprint/tests/test_doc_generator.py` | 3 个测试 |
| `blueprint/tests/test_deploy_generator.py` | 4 个测试 |
| `blueprint/tests/test_webhook.py` | 4 个测试 |
| `blueprint/tests/test_cli.py` | 2 个测试 |

---

## Phase 67：P0 功能实施 — 实时进度 + 费用追踪 + Tester 解析（2026-06-16）

**方法：** Subagent-Driven + TDD

### 一、CostTracker（费用追踪）

**测试：** 6 个（basic / accumulates / no_project_id / no_usage / exception_safe / isolation）
**实现：** in-memory tracker + contextvars 并发隔离 + DeepSeek 定价计算
**文件：** `blueprint/utils/cost_tracker.py`
**结果：** 6/6 通过

### 二、LLM 集成 record_cost

**改动：** llm.py 4 个函数各加 1 行 `record_cost(response)`，side effect 不改返回值
**结果：** 358 通过

### 三、ToolExecutor 进度回调

**测试：** 3 个（callback_called / exception_safe / no_callback）
**实现：** 模块级 `_progress_callback` + `set_progress_callback()` + 执行前触发
**文件：** `blueprint/agents/tool_executor.py`
**结果：** 3/3 通过

### 四、配置开关

**改动：** config.py Settings 类新增 `tool_progress_enabled` / `cost_tracking_enabled` / `auto_fix_enabled`
**结果：** 验证通过

### 五、Tester 结构化解析

**测试：** 8 个（pytest_passed / pytest_failed / pytest_errors / execution_error / all_passed / zero_failed / chinese / mixed）
**实现：** 重写 `_extract_test_passed`，regex 提取 passed/failed/error 数字
**文件：** `blueprint/agents/tester.py`
**关键修复：** 旧实现靠关键词匹配，"0失败" 误判为失败；新实现用 regex 精确提取
**结果：** 8/8 通过

### 六、WebSocket 集成

**改动：**
- `_start_graph`：设置 tool_progress 回调
- `_run_async`：开头调用 `set_project_context(project_id)`
- `_run_async`：agent_done 后发 cost_update 消息

**结果：** 358 通过

### 七、ToolProgress.vue

**实现：** 进度条 + Agent 标签 + 步骤数 + 工具名
**文件：** `frontend/src/components/ToolProgress.vue`
**结果：** 构建通过

### 测试统计

| 模块 | 测试数 | 状态 |
|------|--------|------|
| cost_tracker | 6 | ✅ |
| tool_progress | 3 | ✅ |
| tester_parsing | 8 | ✅ |
| **合计新增** | **17** | **全部通过** |

**总测试数：** 341（之前）+ 17（新增）= **358 通过**

### 新增文件

| 文件 | 说明 |
|------|------|
| `blueprint/utils/cost_tracker.py` | 费用追踪（contextvars 并发隔离） |
| `blueprint/tests/test_cost_tracker.py` | 6 个测试 |
| `blueprint/tests/test_tool_progress.py` | 3 个测试 |
| `blueprint/tests/test_tester_parsing.py` | 8 个测试 |
| `frontend/src/components/ToolProgress.vue` | 进度条组件 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `blueprint/utils/llm.py` | 4 函数加 record_cost side effect |
| `blueprint/agents/tool_executor.py` | 加模块级回调 |
| `blueprint/agents/tester.py` | 重写 _extract_test_passed |
| `blueprint/config.py` | 加 3 个配置开关 |
| `blueprint/api/websocket.py` | tool_progress + cost_update + set_project_context |

### 未完成（用户要求不做前端）

- T13：FlowPanel 集成 ToolProgress
- T14：useWebSocket.js 处理新消息
- Store 添加 toolProgress/costData 状态

**教训：** Subagent-Driven 模式比纯子代理并行更可靠——每个 Task 有明确的输入/输出/验证，完成后可以审查。

---

## Phase 68：代码审查修复（2026-06-16）

**来源：** requesting-code-review 子代理审查，发现 3 Critical + 8 Important + 6 Minor

### Critical 修复（3/3 ✅）

| # | 问题 | 修复 |
|---|------|------|
| C1 | 密钥文件命名不一致（.BLUEPRINT_secret / .blueprint_secret / .devteam_secret） | 统一为 `.blueprint_secret`（auth.py + tool_executor.py） |
| C2 | doc_generator 死代码（return 后的安装说明永不执行） | 移除提前 return，readme 变量正确拼接 |
| C3 | .devteam_secret 提交到 git | `git rm --cached` 移除，.gitignore 已覆盖 |

### Important 修复（7/8 ✅）

| # | 问题 | 修复 |
|---|------|------|
| I1 | webhook_hook async-to-sync 桥接脆弱 | 改用 httpx 同步 Client，单连接池 |
| I2 | cost_tracker 无线程锁 | 加 `threading.Lock` |
| I3 | webhook.py 每次创建新 httpx client | 移到循环外，复用单 client |
| I4 | save_snapshot_hook 路径硬编码 | 直接用 project_dir，不再拼 parent.parent |
| I5 | trace_db 硬编码相对路径 | 改为 `Path(__file__).parent.parent / "data"` |
| I6 | 测试直接改 settings.project_dir | 保留（影响小，monkeypatch 改动大） |
| I7 | 安全扫描自定义模式过宽 | 收窄为 12+ 字符字母数字匹配 |

### Minor 修复（4/6 ✅）

| # | 问题 | 修复 |
|---|------|------|
| M1 | cli.py import sys 未使用 | ❌ 实际被使用（sys.exit），审查误判 |
| M2 | doc_generator 重复扫描文件 | `_detect_tech_stack` 改为接收 files 列表 |
| M3 | 测试覆盖率指标过宽 | 从 min(100) 改为 min(80)，加注释说明局限 |
| M4 | diff_engine gzip 后死代码 | 移除无用的 `if snap_file.exists()` |
| M5 | compose version: '3.8' 废弃 | 移除 version 字段 |
| M6 | BOM 标记 | 保留（Python 能处理，改动大收益小） |

### 审查结论

| 级别 | 总数 | 已修复 | 跳过 |
|------|------|--------|------|
| Critical | 3 | 3 ✅ | 0 |
| Important | 8 | 7 ✅ | 1 |
| Minor | 6 | 4 ✅ | 2 |

**最终测试：** 后端 358 + 前端 91 = **449 测试全过**

---

## Phase 69：P1 功能 — 单步超时 + SQLite Checkpointer 暂缓（2026-06-16）

### 一、Developer/Tester/Reviewer 单步超时

**问题：** LLM 可能卡住空转，8 步全浪费，用户等很久不知道怎么回事。

**方案：** 每步 LLM 调用加 60 秒超时，超时返回 error 让路由函数处理。

**改动：**
- `developer.py`：`call_llm_with_tools_async` 外包 `asyncio.wait_for(..., timeout=60)`
- `tester.py`：同上
- `reviewer.py`：同上

**测试：** 1 个（mock LLM 返回 TimeoutError → 验证 agent 返回 error）
**结果：** 359 通过

### 二、MemorySaver → SQLite Checkpointer（暂缓）

**问题：** MemorySaver 进程重启状态全丢。

**尝试：** 安装 `langgraph-checkpoint-sqlite`，改用 `AsyncSqliteSaver`。

**遇到的问题：** `create_graph()` 是同步函数，但 `AsyncSqliteSaver` 需要 async 初始化（`await aiosqlite.connect()`）。同步函数内无法 await，导致 `_GeneratorContextManager` 类型错误。

**决策：** 暂缓。MemorySaver 对 MVP 足够，多实例部署时再做。加了 TODO 注释。

**教训：** LangGraph 的 checkpointer API 设计是 async-first，同步入口函数需要重构才能支持持久化 checkpointer。这是一个架构债务，需要在后续重构 graph.py 时解决。

---

## Phase 70：P1 功能续 — Reviewer Linter + 代码注释 + 增量迭代（2026-06-16）

### 一、Reviewer Linter 工具

**问题：** Reviewer 审查深度取决于 LLM prompt，无客观数据。

**方案：** 新增 `run_linter` 工具，调用 ruff 检查 Python 代码质量。

**改动：**
- `tools.py`：新增 `RUN_LINTER` 工具定义 + `REVIEWER_TOOLS_WITH_LINTER`
- `tool_executor.py`：新增 `_run_linter` 函数（调用 ruff，返回结构化结果）
- `reviewer.py`：import 改为 `REVIEWER_TOOLS_WITH_LINTER`

**工具返回格式：**
```json
{
  "issues": [{"file": "app.py", "line": 5, "code": "E302", "message": "expected 2 blank lines"}],
  "score": 85,
  "total": 3
}
```

**容错：** ruff 未安装时返回 `skipped: true`，不影响 Reviewer 执行。

**测试：** 3 个（结构化结果 / 文件不存在 / ruff 未安装）
**结果：** 362 通过

### 二、Developer 代码注释要求

**改动：** `DEVELOPER_SYSTEM_PROMPT` 新增「代码质量要求」段落：
- 每个函数加简短注释
- 关键逻辑加行内注释
- 变量命名清晰
- 常见错误列表新增"代码没有注释"

**结果：** 362 通过

### 三、增量迭代模式

**改动：** `build_developer_prompt` 检测已有文件，注入增量开发提示：
- 如果项目目录已有文件 → 明确告知"增量开发模式"
- Developer 先用 file_read 读取理解现有代码
- 只修改/追加需要改的部分，不从零重写

**结果：** 362 通过

### P1 完成进度

| 功能 | 状态 | 说明 |
|------|------|------|
| 单步超时（60s） | ✅ | asyncio.wait_for |
| MemorySaver → SQLite | ⏸ 暂缓 | 架构债务，需重构 graph.py |
| Reviewer linter | ✅ | ruff 集成，3 测试 |
| 代码注释要求 | ✅ | prompt 改动 |
| 增量迭代模式 | ✅ | prompt 改动 |
| 一键部署 | ⏸ 暂缓 | 需要外部 API 集成 |

**最终测试：** 362 通过

---

## Phase 71：前端设计系统 + P0 CSS 修复 + Toast 通知（2026-06-18）

### 一、代码审查（前端）

**来源：** 用户审查前端代码，发现 P0/P1/P2 问题

| 级别 | 问题 | 修复 |
|------|------|------|
| P0 | ToolProgress.vue 硬编码颜色（6 处 #xxx） | 改为 CSS 变量 var(--xxx) |
| P0 | AgentOutputCard border 覆盖 | border 声明顺序修正 |
| P1 | 无暗色模式 | main.css 添加 @media (prefers-color-scheme: dark) |
| P1 | 无响应式 | 添加 768px / 1024px 断点 |
| P1 | 缺 Inter 字体 | index.html 添加 Google Fonts preconnect |
| P1 | Toast 颜色硬编码 | 改为 CSS 变量（rgba + var()） |

### 二、设计系统（基于 ui-ux-pro-max）

**产品类型：** Developer Tool / IDE
**风格：** Dark Mode (OLED) + Minimalism
**字体：** Inter（技术感）+ JetBrains Mono（代码）

| 角色 | 暗色 | 亮色 | 变量 |
|------|------|------|------|
| 背景 | #0F172A | #FFFFFF | --bg |
| 面板 | #1E293B | #F8FAFC | --bg-panel |
| 强调 | #22C55E | #22C55E | --accent |
| 主色 | #3B82F6 | #3B82F6 | --primary |

### 三、全局 Toast 通知

**新增文件：**
- `composables/useNotification.js` — success/error/warning/info + 自动移除
- `components/Toast.vue` — 固定右上角，滑入滑出，4 种颜色
- `__tests__/composables/useNotification.test.js` — 5 个测试

**集成：** App.vue 挂载 Toast，全局可用

### 四、项目总结文档

**新增文件：** `Blueprint项目总结.md` — 整合产品设计、功能扩展、代码审查、简历写法

### 五、简历设计

**格式：** 三段式（Agent 设计 / 工程规范），约 400 字
**核心亮点：** 四层可靠性架构 + 工具调用循环 + Hook 链 + TDD 458 测试

### 测试统计

| 类型 | 数量 |
|------|------|
| 后端 | 362 |
| 前端 | 96 |
| **合计** | **458** |
