# DevTeam 实现计划

> **日期：** 2026-06-04
> **设计文档：** [2026-06-04-devteam-multi-agent-design.md](./2026-06-04-devteam-multi-agent-design.md)
> **总工期：** 约11天

---

## 实现原则

1. **先跑通再优化** — 单Agent跑通全流程（Phase 1-6），再加Proposer-Critic（Phase 7）
2. **先骨架再血肉** — LangGraph图+WebSocket+沙箱先搭好，再填Agent逻辑
3. **前后端并行** — 后端Phase 1-5完成后，前端Phase 6开始
4. **每个Phase有可验证的交付物** — 不是"写了一堆代码"，而是"能跑一个demo"

## 分界线说明

**Phase 1-6：基础流程** — 单Agent跑通全流程，用于验证图结构、路由、interrupt、沙箱等核心机制。
**Phase 7：Proposer-Critic** — 在基础流程跑通后，加入双Agent讨论，提升输出质量。

如果Phase 7出bug，只可能是讨论逻辑的问题，不会混杂图结构或基础Agent的问题。

---

## Phase 1：项目骨架 + 基础设施（2天）

### 目标
搭建项目结构，LangGraph图能跑通（节点用mock函数），WebSocket能连通，沙箱能执行代码。

### 为什么WebSocket必须在Phase 1
interrupt机制依赖WebSocket：图执行到interrupt节点→暂停→通过WebSocket推送确认请求→前端展示确认按钮→用户点击→通过API resume→图继续执行。没有WebSocket，interrupt链路跑不通。

### 任务清单

```
1. 项目结构
   ├── devteam/
   │   ├── __init__.py
   │   ├── config.py          # 配置（复用RAGv3模式）
   │   ├── main.py            # FastAPI入口
   │   ├── api/
   │   │   ├── __init__.py
   │   │   ├── auth.py        # 复用RAGv3 auth
   │   │   ├── projects.py    # 项目CRUD
   │   │   └── websocket.py   # WebSocket处理
   │   ├── agents/
   │   │   ├── __init__.py
   │   │   ├── state.py       # ProjectState定义
   │   │   ├── graph.py       # LangGraph图构建
   │   │   ├── pm.py          # PM Agent
   │   │   ├── architect.py   # Architect Agent
   │   │   ├── developer.py   # Developer Agent
   │   │   ├── tester.py      # Tester Agent
   │   │   ├── reviewer.py    # Reviewer Agent
   │   │   ├── schemas.py     # Pydantic输出Schema
   │   │   └── discussion.py  # Proposer-Critic辅助函数（Phase 7用）
   │   ├── sandbox/
   │   │   ├── __init__.py
   │   │   └── executor.py    # 本地环境执行
   │   └── utils/
   │       ├── __init__.py
   │       └── llm.py         # LLM调用封装（含retry+rate_limiter）
   ├── static/
   │   ├── index.html         # 主工作台
   │   ├── projects.html      # 项目列表
   │   └── css/
   │       └── style.css      # 复用RAGv3暗黑风格
   ├── projects/              # 项目文件存储目录
   ├── requirements.txt
   └── start.py               # 一键启动
```

2. **State定义** — `agents/state.py`
   - 完整ProjectState TypedDict
   - add_messages自动追加

3. **Pydantic Schema** — `agents/schemas.py`
   - PMOutput, ArchitectOutput, DeveloperOutput, TesterOutput, ReviewerOutput
   - UserStory, Feature, APIEndpoint, DataModel, CodeFile, TestCase, ReviewIssue

4. **LangGraph图** — `agents/graph.py`
   - 用mock函数占位（每个节点直接返回固定数据）
   - 所有路由函数实现（含错误路由，见下方）
   - interrupt机制（human_confirm节点）
   - 验证：图能跑通，从START到END

   **错误路由（每个节点一个）：**
   ```python
   def route_after_pm(state: ProjectState) -> str:
       if state.get("error"):
           if "timeout" in state["error"].lower():
               return END
           return "pm"  # 回PM重试一次
       return "proceed"

   def route_after_developer(state: ProjectState) -> str:
       if state.get("error"):
           if "security" in state["error"].lower() or "path" in state["error"].lower():
               return END  # 安全问题不重试
           return "developer"  # 回Developer重试
       return "tester"
   ```

5. **WebSocket** — `api/websocket.py`
   - /ws/project 端点
   - run_project函数（stream推送）
   - interrupt→resume流程（完整链路）
   - 断线重连（reconnect + state_sync推送）

6. **沙箱** — `sandbox/executor.py`
   - execute_python(code, timeout=30)
   - execute_node(code, timeout=30)
   - execute_sql(code)
   - 临时目录管理
   - 输出捕获
   - 超时保护（含进程组杀掉）
   - 安全：start_new_session=True + os.killpg

   ```python
   import os
   import signal
   import subprocess
   import tempfile

   def execute_python(code: str, timeout: int = 30) -> dict:
       with tempfile.TemporaryDirectory() as tmpdir:
           file_path = os.path.join(tmpdir, "main.py")
           with open(file_path, "w") as f:
               f.write(code)
           try:
               result = subprocess.run(
                   ["python", file_path],
                   capture_output=True, text=True,
                   timeout=timeout, cwd=tmpdir,
                   start_new_session=True  # 新进程组
               )
           except subprocess.TimeoutExpired as e:
               # 超时时杀整个进程组
               if e.pid:
                   try:
                       os.killpg(os.getpgid(e.pid), signal.SIGKILL)
                   except ProcessLookupError:
                       pass
               return {"stdout": "", "stderr": "Timeout", "returncode": -1}
           return {
               "stdout": result.stdout,
               "stderr": result.stderr,
               "returncode": result.returncode
           }
   ```

7. **LLM调用封装** — `utils/llm.py`
   - call_llm(messages) → 统一调用接口
   - 内置retry（3次，指数退避）
   - 内置rate_limiter（信号量，默认最大并发5）
   - 所有Agent自动继承，不需要单独配置

```python
from threading import Semaphore
from rag.resilience import retry

_llm_semaphore = Semaphore(5)  # 最多5个并发LLM调用

@retry(max_attempts=3, backoff_base=1.0)
def call_llm(messages: list) -> str:
    """统一LLM调用，内置retry和rate_limiter"""
    with _llm_semaphore:
        return llm.invoke(messages).content
```

8. **配置** — `config.py`
   - DeepSeek API配置
   - 讨论轮次配置（Phase 7用）
   - 项目目录配置

9. **测试框架** — `tests/`
   - tests/conftest.py — 共享fixtures
   - tests/test_schemas.py — Schema校验测试
   - tests/test_sandbox.py — 沙箱执行测试
   - tests/test_graph.py — 图结构测试（mock跑通）
   - 后续Phase只往里加case，不新建文件

### 交付物
- 启动服务后，WebSocket连通
- 发送任意需求，mock节点依次执行，前端收到agent_start/agent_update消息
- interrupt暂停，前端弹出确认框，点击后图继续执行
- 沙箱能执行Python/Node.js/SQL代码

### 验证方式
```bash
python start.py
# 浏览器打开 localhost:8000
# 输入"做一个计算器"，观察流程面板是否依次点亮各节点
# interrupt确认框能正常弹出和响应
```

---

## Phase 2：PM Agent（1天）

### 目标
PM节点能分析需求，输出用户故事和功能清单。

### 任务清单

1. **PM Prompt** — `agents/pm.py`
   - PM_SYSTEM_PROMPT（角色定义+推理策略+输出格式）
   - PM_CRITIC_PROMPT（Phase 7用，先写好）

2. **PM节点实现** — `agents/pm.py`
   - pm_agent函数（sync）
   - 调用Phase 1的call_llm
   - Pydantic schema校验（PMOutput）
   - 输出验证（user_stories不能为空）
   - interrupt处理（needs_clarification时暂停等用户补充）

3. **Prompt构建函数**
   - build_pm_prompt(requirement) → 构建完整prompt

### 交付物
- 发送"做一个待办事项Web应用"
- PM返回结构化的用户故事和功能清单
- 前端聊天面板展示PM的输出

### 验证方式
```python
# 单独测试PM节点
from devteam.agents.pm import pm_agent
state = {"requirement": "做一个待办事项Web应用", "iteration": 0, ...}
result = pm_agent(state)
print(result["user_stories"])  # 应该有多个用户故事
print(result["features"])      # 应该有多个功能
```

---

## Phase 3：Architect Agent（1天）

### 目标
Architect节点能根据用户故事设计架构。

### 任务清单

1. **Architect Prompt** — `agents/architect.py`
   - ARCHITECT_SYSTEM_PROMPT
   - ARCHITECT_CRITIC_PROMPT

2. **Architect节点实现** — `agents/architect.py`
   - architect_agent函数（sync）
   - Pydantic schema校验（ArchitectOutput）
   - 输出验证（api_definitions不能为空）

3. **Prompt构建函数**
   - build_architect_prompt(user_stories, features)

### 交付物
- PM输出后，Architect自动执行
- 返回架构设计、API定义、数据模型
- 前端展示Architect的输出

### 验证方式
```python
# 测试PM→Architect连贯性
# 用Phase 2的PM输出作为Architect输入
```

---

## Phase 4：Developer Agent（1.5天）

### 目标
Developer节点能生成代码，用沙箱验证语法。前1天只做Python，后0.5天加语言分发框架。

### 任务清单

1. **Developer Prompt** — `agents/developer.py`
   - DEVELOPER_SYSTEM_PROMPT
   - DEVELOPER_CRITIC_PROMPT（Phase 7用，先写好）

2. **Developer节点实现** — `agents/developer.py`
   - developer_agent函数（sync）
   - Pydantic schema校验（DeveloperOutput）
   - 文件路径安全校验（防路径注入）
   - 语言分发框架（MVP只实现Python，其他语言预留）

   ```python
   def validate_and_execute(files: list[CodeFile]) -> list[dict]:
       results = []
       for file in files:
           if file.language == "python":
               sandbox_result = execute_python(file.content)
           elif file.language in ("html", "js", "css"):
               sandbox_result = syntax_check(file.content, file.language)  # MVP: 只做语法检查
           else:
               sandbox_result = {"passed": True, "note": "跳过验证"}
           results.append(sandbox_result)
       return results
   ```

3. **Prompt构建函数**
   - build_developer_prompt(architecture, api_definitions, data_models, iteration)

4. **单元测试** — `tests/test_developer.py`
   - 测试Python代码生成+执行
   - 测试路径安全校验

### 交付物
- Architect输出后，Developer自动执行
- 生成完整的项目文件（main.py, index.html, style.css等）
- Python代码能通过沙箱执行且无SyntaxError/ImportError

### 验证方式
```bash
# 1. Developer生成一个计算器代码
# 2. 沙箱执行该代码
# 3. 检查没有 SyntaxError 和 ImportError
```

---

## Phase 5：Tester + Reviewer Agent（1.5天）

### 目标
Tester能编写测试并执行，Reviewer能审查代码。

### 任务清单

1. **Tester Prompt** — `agents/tester.py`
   - TESTER_SYSTEM_PROMPT
   - 测试策略：
     - Python项目 → pytest
     - 前端项目 → 语法检查（html-validate / eslint）
     - 全栈项目 → 分别测试

2. **Tester节点实现** — `agents/tester.py`
   - tester_agent函数（sync）
   - 生成测试代码
   - 用沙箱执行测试
   - Pydantic schema校验（TesterOutput）
   - 测试结果解析（passed/failed）

3. **Reviewer Prompt** — `agents/reviewer.py`
   - REVIEWER_SYSTEM_PROMPT
   - 审查维度：placeholder扫描、一致性、边界、风格

4. **Reviewer节点实现** — `agents/reviewer.py`
   - reviewer_agent函数（sync）
   - Pydantic schema校验（ReviewerOutput）
   - 判断approved（无critical issue则通过）

### 交付物
- Developer输出后，Tester自动执行
- 生成测试用例并执行，返回测试报告
- Reviewer审查代码，返回审查意见

### 验证方式
```bash
# 完整流程测试：需求→PM→Architect→Developer→Tester→Reviewer→交付
# 输入"做一个计算器"，观察全流程是否跑通
# Developer生成的代码能被沙箱执行且无SyntaxError/ImportError
```

---

## Phase 6：前端（2天）

### 目标
主工作台完成，能实时展示Agent协作过程。

### 开始时机
Phase 2（PM Agent）完成后开始，此时有真实的Agent消息格式可供前端渲染。与Phase 3-5并行。

### 任务清单

1. **主工作台布局** — `static/index.html`
   - 两栏布局（桌面端优先，MVP不做移动端适配）
   - 左侧：Agent流程面板
   - 右侧：聊天面板

2. **Agent流程面板**
   - 5个节点（PM/Architect/Developer/Tester/Reviewer）+ Deliver
   - 节点状态：等待（灰）/ 执行中（蓝+呼吸动画）/ 完成（绿）/ 错误（红）/ 暂停（黄）
   - 迭代进度条
   - MVP用CSS动画，不做SVG卡通形象

3. **聊天面板**
   - 消息渲染（用name字段区分来源）
   - AGENT_LABELS映射（pm_proposer→"PM·方案"）
   - interrupt确认对话框
   - 文件预览/下载（项目完成后）

4. **WebSocket客户端**
   - 连接管理
   - 消息处理（agent_start/update/done/interrupt/error/project_done）
   - 断线重连（reconnect + state_sync）
   - 联调时间预留充足（前后端联调最容易超时）

5. **页面**
   - /login — 登录页（复用RAGv3风格）
   - / — 主工作台
   - /projects — 项目列表
   - /projects/:id — 项目详情

### 交付物
- 打开浏览器，输入需求，实时看到Agent协作过程
- interrupt时弹出确认框
- 项目完成后可预览和下载文件

### 验证方式
```bash
# 完整用户流程
1. 打开 localhost:8000
2. 输入"做一个待办事项Web应用"
3. 观察PM→Architect→确认架构→Developer→Tester→Reviewer→交付
4. 下载生成的文件
```

---

## Phase 7：Proposer-Critic集成 + 重新审查（1天）

### 目标
PM/Architect加入双Agent讨论，Developer加入后审。用户可触发重新审查。

### 任务清单

1. **讨论辅助函数** — `agents/discussion.py`
   - proposer_critic_discuss(task, proposer_prompt, critic_prompt, llm, max_rounds, mode)
   - full模式：Proposer→Critic循环
   - post_review模式：先生成→Critic审→有critical修一次
   - 结构化输出（CriticResult: approved, issues, suggestion）
   - 讨论记录返回（用于存入messages）

2. **配置** — `config.py`
   - DISCUSSION_CONFIG字典
   - 每个阶段的enabled/max_rounds/mode/prompts

3. **更新节点函数**
   - pm_agent：集成proposer_critic_discuss（full模式）+ user_feedback检查
   - architect_agent：集成proposer_critic_discuss（full模式）+ user_feedback检查
   - developer_agent：集成proposer_critic_discuss（post_review模式）+ user_feedback检查
   - tester_agent：不变
   - reviewer_agent：不变

4. **重新审查机制**
   - State加user_feedback和rethink_count字段
   - /api/rethink端点：更新state，从当前节点重新执行
   - 每个节点检查user_feedback，有反馈则再跑一轮Proposer-Critic
   - 终止条件：每节点最多3轮rethink

5. **前端**
   - 每个Agent输出后加[继续][重新审查]按钮
   - 点击[重新审查]弹出反馈输入框
   - 聊天面板支持折叠展开讨论详情
   - pm_proposer/pm_critic等消息正确渲染

### 交付物
- PM阶段展示讨论过程（Proposer出方案→Critic挑刺→达成共识）
- Developer阶段展示后审过程（生成代码→Critic审查→修复关键问题）
- 用户可点击[重新审查]，输入反馈后触发新一轮讨论

### 验证方式
```bash
# 1. 输入"做一个计算器"，观察PM的讨论过程
# 2. PM完成后，点击[重新审查]，输入"请补充国际化支持"
# 3. 观察PM是否根据反馈重新讨论并输出改进后的方案
```

---

## Phase 8：集成测试 + 优化（1天）

### 目标
全流程跑通，修复边界问题。

### 任务清单

1. **端到端测试**
   - 简单需求："做一个计算器"
   - 中等需求："做一个待办事项Web应用，支持增删改查"
   - 复杂需求："做一个博客系统，支持用户注册、文章发布、评论"
   - 模糊需求："做个好玩的"（测试interrupt澄清）

2. **边界测试**
   - LLM调用超时/失败 → 重试是否生效
   - PM输出为空 → 是否报错
   - Developer生成的代码有语法错误 → Tester是否捕获
   - 测试全部失败 → 循环3次后是否强制放行
   - interrupt后不操作 → 超时处理

3. **性能优化**
   - LLM调用延迟统计
   - 讨论轮次对总耗时的影响
   - 前端渲染性能

4. **Bug修复**
   - 修复测试中发现的问题

### 交付物
- 3个需求场景全流程跑通
- 边界case有合理处理
- 无明显bug

---

## 依赖关系

```
Phase 1 (骨架+WebSocket+沙箱)
    ↓
Phase 2 (PM) ──→ Phase 3 (Architect) ──→ Phase 4 (Developer)
                                              ↓
                                         Phase 5 (Tester+Reviewer)
                                              ↓
                                         Phase 7 (Proposer-Critic)
                                              ↓
                                         Phase 8 (集成测试)

Phase 6 (前端) ── 可在Phase 2完成后开始，与Phase 3-5并行
```

## 总工期

| Phase | 内容 | 工期 | 累计 |
|-------|------|------|------|
| 1 | 骨架+WebSocket+沙箱 | 2天 | 2天 |
| 2 | PM Agent | 1天 | 3天 |
| 3 | Architect Agent | 1天 | 4天 |
| 4 | Developer Agent | 1.5天 | 5.5天 |
| 5 | Tester+Reviewer | 1.5天 | 7天 |
| 6 | 前端（与Phase 2-5并行） | 2天 | 7天 |
| 7 | Proposer-Critic | 1天 | 8天 |
| 8 | 集成测试 | 1天 | 9天 |

**总计：约9天**（前端与后端并行，实际墙钟时间约7天）

---

## 风险和应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| DeepSeek API不稳定 | 中 | Agent输出质量下降 | 重试+熔断，备用模型 |
| LLM输出格式不规范 | 高 | Schema校验失败 | extract_json先提取再解析，失败则重试 |
| 代码生成质量差 | 中 | 测试不通过 | 循环修改，人工介入 |
| 前端动画卡顿 | 低 | 体验差 | 简化动画，用CSS而非JS |
| interrupt恢复失败 | 低 | 流程中断 | checkpoint持久化 |
| WebSocket断连时图还在执行 | 中 | 前端收不到结果 | checkpoint持久化 + 重连后state_sync |
| LLM输出不是合法JSON | 高 | Schema校验失败 | extract_json先提取再解析，失败则重试 |

---

## 面试话术

完成后的面试话术：

> "我用LangGraph构建了一个多Agent协同系统，6个角色化Agent按流程协作：PM分析需求→Architect设计架构→Developer编码→Tester测试→Reviewer审查。
>
> 核心设计有三点：
> 1. **Proposer-Critic对抗模式** — PM和Architect内部有双Agent讨论，3轮迭代直到达成共识，但不是盲目3轮，而是根据阶段特性配置：PM/Architect用full模式深度讨论，Developer用post_review模式快速迭代，Tester/Reviewer本身就是质量关卡不需要再套一层。
> 2. **双层保障** — Prompt层引导思考（角色定义+推理策略），代码层保障执行（Pydantic schema校验+resilience重试+路径安全检查）。
> 3. **interrupt机制** — 关键节点用LangGraph的interrupt暂停，等人工确认后继续，防止Agent跑偏。
>
> 前端用WebSocket实时展示Agent协作过程，用户可以看到每个Agent的思考和讨论。"
