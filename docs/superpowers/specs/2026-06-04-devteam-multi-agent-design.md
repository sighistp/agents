# Blueprint — 多Agent协同AI开发团队 设计文档

> **日期：** 2026-06-04
> **状态：** 设计定稿，待实现
> **目标：** 用户输入一句话需求，多Agent自动完成需求分析→架构设计→编码→测试→审查→交付

---

## 1. 项目概述

### 1.1 定位

Blueprint 是一个基于 LangGraph 的多Agent协同系统，模拟真实软件开发团队的工作流程。用户输入自然语言需求（如"做一个待办事项Web应用"），系统自动完成从需求分析到代码交付的全流程。

### 1.2 核心特性

- **6个角色化Agent**：PM、Architect、Developer、Tester、Reviewer、Orchestrator
- **Proposer-Critic对抗模式**：PM/Architect深度讨论（3轮），Developer后审（1轮），Tester/Reviewer不讨论
- **Pydantic Schema校验**：每个Agent输出严格定义，代码层校验而非靠prompt
- **双层保障**：Prompt层引导思考（角色定义+推理策略），代码层保障执行（重试+校验+安全检查）
- **图架构**：LangGraph StateGraph 编排，条件分支+循环，后续可扩展并行
- **条件分支+循环**：测试失败回开发、审查不通过回开发，最多循环3次
- **人工介入**：关键节点（架构确认、需求澄清）支持interrupt暂停等人确认
- **本地环境执行**：直接调用用户本地的Python/Node.js环境，无需Docker
- **实时可视化**：前端展示Agent协作过程+讨论详情，卡通风格动画

### 1.3 与RAGv3的关系

复用RAGv3的基础设施模块，但Agent核心完全独立：

| 维度 | RAGv3 | Blueprint |
|------|-------|---------|
| 定位 | 知识库问答 | 代码生成 |
| Agent | 单Agent + 4工具 | 6个角色化Agent + LangGraph编排 |
| 前端 | 暗黑科技风聊天 | 流程可视化 + 聊天 |
| 共享 | auth, user_db, memory, resilience, guard, 前端CSS变量 |

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────┐
│                    前端 (HTML/CSS/JS)                │
│  ┌──────────────┐  ┌──────────────────────────────┐ │
│  │   聊天面板    │  │    Agent协作流程面板（卡通）    │ │
│  └──────────────┘  └──────────────────────────────┘ │
└─────────────────────┬───────────────────────────────┘
                      │ WebSocket + REST API
┌─────────────────────┴───────────────────────────────┐
│                 FastAPI 后端                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  /api/chat  │  │ /api/projects│ │ /api/tasks  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────┐
│              LangGraph 编排引擎                       │
│  ┌─────────────────────────────────────────────┐    │
│  │           主图 (Orchestrator)                │    │
│  │  ┌─────┐ ┌────────┐ ┌──────┐ ┌──────┐     │    │
│  │  │ PM  │→│Architect│→│Develop│→│ Test │     │    │
│  │  └─────┘ └────────┘ └──────┘ └──┬───┘     │    │
│  │                                 ↓          │    │
│  │                            ┌──────┐        │    │
│  │                            │Review│──→交付  │    │
│  │                            └──────┘        │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────┐
│                    工具层                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │本地环境执行│ │文件读写   │ │测试运行   │            │
│  └──────────┘ └──────────┘ └──────────┘            │
└─────────────────────────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────┐
│                  存储层                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ SQLite   │ │ 项目文件  │ │Checkpoint│            │
│  │(复用RAGv3)│ │  临时目录 │ │(LangGraph)│           │
│  └──────────┘ └──────────┘ └──────────┘            │
└─────────────────────────────────────────────────────┘
```

> **注**：MVP阶段为线性流程，不做并行子图。后续可扩展：开发阶段拆分为前端/后端并行，结果合并回state。

---

## 3. Agent角色定义

| 角色 | 职责 | 输入 | 输出 | 可用工具 |
|------|------|------|------|---------|
| **PM（产品经理）** | 需求分析、任务拆解 | 用户原始需求 | 用户故事、功能清单、技术约束 | 无（纯推理） |
| **Architect（架构师）** | 技术方案设计 | 用户故事 | 架构图、模块划分、API定义、数据模型 | 无（纯推理） |
| **Developer（开发者）** | 编码实现 | 架构设计 + 接口定义 | 源代码文件 | file_write, file_read, code_execute |
| **Tester（测试员）** | 编写测试 + 执行 | 代码 + 需求 | 测试用例、测试报告、Bug列表 | file_read, test_run, code_execute |
| **Reviewer（审查员）** | 代码审查 | 代码 + 测试报告 | 审查意见、改进建议 | file_read（只读） |
| **Orchestrator（调度员）** | 流程控制 | 所有Agent输出 | 阶段流转决策 | 条件判断（代码实现，非LLM） |

### Agent内部结构

```
Agent = LLM + System Prompt + Tools
```

每个Agent有独立的system prompt，定义角色性格、输出格式、约束条件。

---

## 4. LangGraph图结构

### 4.1 State定义

```python
from langgraph.graph.message import add_messages
from typing import Annotated, TypedDict

class ProjectState(TypedDict):
    # 项目标识
    project_id: str                     # 项目唯一ID

    # 需求
    requirement: str                    # 用户原始需求
    user_stories: list[dict]            # PM输出
    features: list[dict]                # 功能清单

    # 架构
    architecture: dict                  # 架构设计
    api_definitions: list[dict]         # API接口
    data_models: list[dict]             # 数据模型

    # 代码
    files: dict[str, str]               # {文件路径: 内容}

    # 测试
    test_cases: list[dict]              # 测试用例
    test_results: dict                  # 执行结果
    test_passed: bool                   # 是否通过

    # 审查
    review_comments: list[dict]         # 审查意见
    review_approved: bool               # 是否通过

    # 流程控制
    current_agent: str                  # 当前执行的Agent
    iteration: int                      # 循环次数
    max_iterations: int                 # 最大循环次数（默认3）
    status: str                         # running/delivered/failed
    error: str | None                   # 错误信息
    need_human_confirm: bool            # 是否需要人工确认架构
    human_approved: bool | None         # 人工确认结果

    # 用户反馈（重新审查用）
    user_feedback: str | None           # 用户反馈内容
    rethink_count: dict[str, int]       # 每个节点的重新审查次数 {"pm": 0, "architect": 0, ...}

    # 消息记录（自动追加，不会覆盖）
    messages: Annotated[list, add_messages]
```

### 4.2 路由函数

```python
def route_after_pm(state: ProjectState) -> str:
    if state.get("error"):
        if "timeout" in state["error"].lower():
            return END  # LLM超时，已重试过，END
        return "pm"  # 其他错误，回PM重试一次
    return "proceed"

def route_after_architect(state: ProjectState) -> str:
    if state.get("error"):
        if "timeout" in state["error"].lower():
            return END
        return "architect"
    if state.get("need_human_confirm", True):
        return "confirm"
    return "auto"

def route_after_human(state: ProjectState) -> str:
    if state.get("human_approved"):
        return "approve"
    return "reject"

def route_after_developer(state: ProjectState) -> str:
    if state.get("error"):
        if "security" in state["error"].lower() or "path" in state["error"].lower():
            return END  # 安全问题不重试
        return "developer"  # 其他错误，回Developer重试
    return "tester"

def route_after_test(state: ProjectState) -> str:
    if state["test_passed"]:
        return "pass"
    if state["iteration"] >= state["max_iterations"]:
        return "pass"  # 达到上限，强制放行
    return "fail"

def route_after_review(state: ProjectState) -> str:
    if state["review_approved"]:
        return "approve"
    if state["iteration"] >= state["max_iterations"]:
        return "approve"  # 达到上限，强制交付
    return "reject"
```

### 4.3 节点函数

```python
from langgraph.types import interrupt

def pm_agent(state: ProjectState) -> dict:
    """需求分析，需求不清晰时interrupt等用户补充"""
    try:
        result = llm.invoke(build_pm_prompt(state["requirement"]))
        user_stories = parse_user_stories(result)
        features = parse_features(result)

        if not user_stories or len(features) < 2:
            clarification = interrupt({
                "type": "clarify",
                "message": "需求描述较简略，请补充细节",
                "current_analysis": result,
                "questions": ["具体要支持哪些功能？", "目标用户是谁？"]
            })
            state["requirement"] += f"\n补充说明：{clarification}"
            result = llm.invoke(build_pm_prompt(state["requirement"]))
            user_stories = parse_user_stories(result)
            features = parse_features(result)

        return {
            "user_stories": user_stories,
            "features": features,
            "current_agent": "architect",
            "messages": [{"role": "assistant", "name": "pm",
                          "content": f"已拆分为 {len(user_stories)} 个用户故事"}]
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}

def architect_agent(state: ProjectState) -> dict:
    """架构设计"""
    try:
        result = llm.invoke(build_architect_prompt(state["user_stories"]))
        return {
            "architecture": parse_architecture(result),
            "api_definitions": parse_apis(result),
            "data_models": parse_models(result),
            "current_agent": "developer",
            "messages": [{"role": "assistant", "name": "architect",
                          "content": "架构设计完成"}]
        }
    except Exception as e:
        return {"error": str(e)}

def developer_agent(state: ProjectState) -> dict:
    """编码实现，每次进入iteration+1"""
    try:
        new_iteration = state.get("iteration", 0) + 1
        result = llm.invoke(build_developer_prompt(state))
        generated_files = parse_files(result)
        return {
            "files": generated_files,
            "iteration": new_iteration,
            "current_agent": "tester",
            "messages": [{"role": "assistant", "name": "developer",
                          "content": f"第{new_iteration}次迭代，已生成 {len(generated_files)} 个文件"}]
        }
    except Exception as e:
        return {"error": str(e)}

def tester_agent(state: ProjectState) -> dict:
    """编写测试并执行"""
    try:
        test_code = llm.invoke(build_tester_prompt(state))
        test_results = execute_tests(state["files"], test_code)
        return {
            "test_cases": parse_test_cases(test_code),
            "test_results": test_results,
            "test_passed": test_results["passed"],
            "messages": [{"role": "assistant", "name": "tester",
                          "content": f"测试{'通过' if test_results['passed'] else '失败'}"}]
        }
    except Exception as e:
        return {"error": str(e)}

def reviewer_agent(state: ProjectState) -> dict:
    """代码审查"""
    try:
        result = llm.invoke(build_reviewer_prompt(state))
        comments = parse_review_comments(result)
        approved = len([c for c in comments if c["severity"] == "critical"]) == 0
        return {
            "review_comments": comments,
            "review_approved": approved,
            "messages": [{"role": "assistant", "name": "reviewer",
                          "content": f"审查{'通过' if approved else '不通过，发现 ' + str(len(comments)) + ' 个问题'}"}]
        }
    except Exception as e:
        return {"error": str(e)}

def human_confirm_node(state: ProjectState) -> dict:
    """人工确认架构，interrupt暂停"""
    response = interrupt({
        "type": "confirm",
        "message": "请确认以下架构设计",
        "architecture": state["architecture"],
        "api_definitions": state["api_definitions"],
        "data_models": state["data_models"]
    })
    return {"human_approved": response.get("approved", False)}

def deliver_node(state: ProjectState) -> dict:
    """打包交付物，持久化文件到项目目录"""
    import os
    import json
    from pathlib import Path

    # 项目目录：projects/{project_id}/
    project_id = state.get("project_id", "default")
    project_dir = Path("projects") / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    # 写入代码文件（resume时覆盖，但先检查内容是否变化）
    for file_path, content in state.get("files", {}).items():
        full_path = project_dir / file_path
        if full_path.exists() and full_path.read_text(encoding="utf-8") == content:
            continue  # 内容没变，跳过
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    # 写入元数据
    meta = {
        "requirement": state["requirement"],
        "user_stories": state.get("user_stories", []),
        "features": state.get("features", []),
        "architecture": state.get("architecture", {}),
        "iteration": state.get("iteration", 0),
    }
    (project_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    return {
        "status": "delivered",
        "current_agent": "done",
        "project_path": str(project_dir),
        "messages": [{"role": "assistant", "name": "system",
                      "content": f"项目完成！文件已保存到 {project_dir}"}]
    }
```

### 4.4 图构建

```python
from langgraph.graph import StateGraph, START, END

graph = StateGraph(ProjectState)

# 添加节点
graph.add_node("pm", pm_agent)
graph.add_node("architect", architect_agent)
graph.add_node("human_confirm", human_confirm_node)
graph.add_node("developer", developer_agent)
graph.add_node("tester", tester_agent)
graph.add_node("reviewer", reviewer_agent)
graph.add_node("deliver", deliver_node)

# 入口
graph.add_edge(START, "pm")

# PM条件分支（clarify通过interrupt处理，不走路由）
graph.add_conditional_edges("pm", route_after_pm, {
    "proceed": "architect",
    "error": END
})

# Architect → 人工确认 or 直接开发
graph.add_conditional_edges("architect", route_after_architect, {
    "auto": "developer",
    "confirm": "human_confirm"
})

# Human Confirm → Developer or 回 Architect
graph.add_conditional_edges("human_confirm", route_after_human, {
    "approve": "developer",
    "reject": "architect"
})

# Developer → Tester（含错误路由）
graph.add_conditional_edges("developer", route_after_developer, {
    "tester": "tester",
    "developer": "developer",  # 错误重试
    END: END  # 安全问题直接END
})

# Tester → Reviewer or 回 Developer
graph.add_conditional_edges("tester", route_after_test, {
    "pass": "reviewer",
    "fail": "developer"
})

# Reviewer → Deliver or 回 Developer
graph.add_conditional_edges("reviewer", route_after_review, {
    "approve": "deliver",
    "reject": "developer"
})

# Deliver → 结束
graph.add_edge("deliver", END)

app = graph.compile()
```

### 4.5 流程图

```
START
  ↓
┌───────┐    用户故事    ┌───────────┐
│  PM   │──────────────→│ Architect │
└───┬───┘               └─────┬─────┘
    │                         │
    │ clarify?           ┌────┴────┐
    │                    │ auto?   │ confirm?
    ↓                    ↓        ↓
   END            ┌────────────┐  ┌──────────────┐
                  │  Developer │←─│ human_confirm │
                  └──────┬─────┘  └──────┬───────┘
                         │               │ reject?
                         │               ↓
                         │          ┌───────────┐
                         │          │ Architect  │ (回炉)
                         │          └───────────┘
                         ↓
                  ┌────────────┐
                  │   Tester   │
                  └──────┬─────┘
                   pass  │  fail
                  ┌──────┴──────┐
                  ↓             ↓
            ┌──────────┐   (iteration < 3?)
            │ Reviewer  │     yes → 回 Developer
            └─────┬────┘     no  → 强制 pass
             approve│  reject
                  ↓     ↓
            ┌──────────┐ (iteration < 3?)
            │ Deliver  │   yes → 回 Developer
            └────┬─────┘   no  → 强制 approve
                 ↓
               END
```

### 4.6 Proposer-Critic讨论模式

每个Agent内部采用双Agent对抗审查，提高输出质量。讨论记录统一存入`messages`字段，前端用`name`字段区分来源。

#### 讨论配置

```python
DISCUSSION_CONFIG = {
    "pm": {
        "enabled": True,
        "max_rounds": 3,
        "mode": "full",
        "proposer_prompt": "你是资深产品经理，擅长需求分析...",
        "critic_prompt": "你是技术负责人，从可行性、完整性角度审查..."
    },
    "architect": {
        "enabled": True,
        "max_rounds": 3,
        "mode": "full",
        "proposer_prompt": "你是系统架构师，擅长技术选型...",
        "critic_prompt": "你是架构审查专家，关注扩展性、性能瓶颈..."
    },
    "developer": {
        "enabled": True,
        "max_rounds": 1,
        "mode": "post_review",
        "critic_prompt": "你是代码审查专家，只标记 critical 级别问题..."
    },
    "tester": {"enabled": False},
    "reviewer": {"enabled": False},
}
```

#### 两种模式

- **full**（PM/Architect）：Proposer出方案→Critic挑刺→循环，最多3轮
- **post_review**（Developer）：先生成代码→Critic审一轮→有critical问题修一次→不再审查

#### 全流程调用次数

```
PM:         3轮 × 2 = 6次  (最坏情况，通常2轮就LGTM)
Architect:  3轮 × 2 = 6次  (最坏情况)
Developer:  生成1 + 审查1 + 修复1 = 3次
Tester:     1次
Reviewer:   1次
─────────────────────────
最坏: 17次  |  典型: 10-12次  |  原方案: 30次
```

#### 讨论记录结构（统一存入messages）

```python
messages = [
    {"role": "user",        "content": "做一个待办事项应用"},
    {"role": "assistant",   "name": "pm_proposer",  "content": "拆分为5个用户故事..."},
    {"role": "assistant",   "name": "pm_critic",    "content": "⚠ 遗漏编辑功能"},
    {"role": "assistant",   "name": "pm_proposer",  "content": "补充为6个用户故事..."},
    {"role": "assistant",   "name": "pm_critic",    "content": "✅ LGTM"},
    {"role": "assistant",   "name": "arch_proposer","content": "采用前后端分离架构..."},
    {"role": "assistant",   "name": "arch_critic",  "content": "✅ 接口定义清晰"},
    {"role": "assistant",   "name": "developer",    "content": "已生成 4 个文件"},
    {"role": "assistant",   "name": "developer_critic", "content": "⚠ 缺少错误处理"},
    {"role": "assistant",   "name": "developer",    "content": "已修复 1 个关键问题"},
    {"role": "assistant",   "name": "tester",       "content": "8个测试用例，全部通过"},
    {"role": "assistant",   "name": "reviewer",     "content": "代码质量良好，通过审查"},
]
```

#### Developer节点实现（post_review模式）

```python
def developer_agent(state: ProjectState) -> dict:
    """Developer：生成代码 → 审查 → 有critical问题则修一次"""
    messages = list(state.get("messages", []))

    # 1. 生成代码
    code = generate_code(state)
    messages.append({
        "role": "assistant", "name": "developer",
        "content": f"已生成 {len(code)} 个文件"
    })

    # 2. Critic 审查一轮
    critique_result = call_llm([
        SystemMessage(content=DEVELOPER_CRITIC_PROMPT),
        HumanMessage(content=f"请审查以下代码，标记问题严重程度：\n\n{format_code(code)}")
    ])
    critique = parse_json(critique_result)
    # {"approved": bool, "critical_issues": [...], "suggestions": [...]}

    messages.append({
        "role": "assistant", "name": "developer_critic",
        "content": format_critique(critique)
    })

    # 3. 有 critical 问题才修一次，修完不再审查
    if critique["critical_issues"]:
        fix_prompt = f"修复以下关键问题：\n{critique['critical_issues']}\n\n原代码：\n{format_code(code)}"
        fixed_code = call_llm([
            SystemMessage(content=DEVELOPER_PROMPT),
            HumanMessage(content=fix_prompt)
        ])
        code = parse_code(fixed_code)
        messages.append({
            "role": "assistant", "name": "developer",
            "content": f"已修复 {len(critique['critical_issues'])} 个关键问题"
        })

    return {
        "files": code,
        "iteration": state.get("iteration", 0) + 1,
        "current_agent": "tester",
        "messages": messages
    }
```

#### 前端渲染

```javascript
const AGENT_LABELS = {
    "pm_proposer": "PM · 方案",
    "pm_critic": "PM · 审查",
    "arch_proposer": "架构师 · 方案",
    "arch_critic": "架构师 · 审查",
    "developer": "开发",
    "developer_critic": "开发 · 审查",
    "tester": "测试",
    "reviewer": "审查",
};

function renderMessage(msg) {
    const name = msg.name || msg.role;
    const avatar = AGENT_AVATARS[name] || AGENT_AVATARS[name.split("_")[0]];
    const label = AGENT_LABELS[name];

    return `
        <div class="message ${name}">
            <img src="${avatar}" class="avatar" />
            <div class="label">${label}</div>
            <div class="content">${msg.content}</div>
        </div>
    `;
}
```

### 4.7 Agent输出Schema（Pydantic）

每个Agent的输出用Pydantic模型严格定义，而非裸dict。

```python
from pydantic import BaseModel, validator

class UserStory(BaseModel):
    id: str
    title: str
    description: str
    acceptance_criteria: list[str]
    priority: str  # "high" | "medium" | "low"

class Feature(BaseModel):
    name: str
    description: str
    priority: str
    related_stories: list[str]

class PMOutput(BaseModel):
    user_stories: list[UserStory]
    features: list[Feature]
    technical_constraints: list[str]
    needs_clarification: bool = False
    clarification_questions: list[str] = []

class APIEndpoint(BaseModel):
    method: str  # GET/POST/PUT/DELETE
    path: str
    description: str
    request_body: dict | None = None
    response_body: dict | None = None

class DataModel(BaseModel):
    name: str
    fields: dict[str, str]  # {字段名: 类型}
    relationships: list[str] = []

class ArchitectOutput(BaseModel):
    architecture_description: str
    tech_stack: dict[str, str]  # {前端: React, 后端: FastAPI, ...}
    modules: list[str]
    api_definitions: list[APIEndpoint]
    data_models: list[DataModel]

class CodeFile(BaseModel):
    path: str           # 文件路径，如 "src/main.py"
    content: str        # 文件内容
    language: str       # python/html/js/css/sql

class DeveloperOutput(BaseModel):
    files: list[CodeFile]
    dependencies: list[str]  # 需要安装的包

class TestCase(BaseModel):
    id: str
    name: str
    description: str
    code: str           # 测试代码
    expected: str       # 预期结果

class TestResult(BaseModel):
    test_id: str
    passed: bool
    output: str
    error: str | None = None

class TesterOutput(BaseModel):
    test_cases: list[TestCase]
    test_results: list[TestResult]
    all_passed: bool
    coverage_summary: str

class ReviewIssue(BaseModel):
    file: str
    line: int | None = None
    severity: str  # "critical" | "warning" | "suggestion"
    description: str
    suggestion: str

class ReviewerOutput(BaseModel):
    issues: list[ReviewIssue]
    approved: bool  # 无critical issue则为True
    summary: str
```

### 4.8 Agent Prompt设计原则

Prompt层负责角色定义和推理策略，代码层负责校验和重试。两者互补。

#### Prompt层（引导LLM思考）

```python
PM_SYSTEM_PROMPT = """
你是资深产品经理，有10年B端产品经验。按以下原则工作：

【探索阶段】
- 先理解用户真正想要什么，不要急着出方案
- 如果需求模糊，标记 needs_clarification: true 并列出疑问
- 不要猜测，不确定就问

【方案阶段】
- 提出最合理的方案，附带 trade-off 分析
- 用户故事必须有明确的验收标准，不允许模糊表述

【输出阶段】
- 严格按照JSON schema输出，不要添加其他文字
- 每个用户故事必须有 id/title/description/acceptance_criteria/priority

【自审阶段】
- 输出前检查：是否有遗漏？是否有歧义？
- 验收标准是否可测试？优先级是否合理？
"""

ARCHITECT_SYSTEM_PROMPT = """
你是系统架构师，擅长技术选型和架构设计。按以下原则工作：

【约束识别】
- 先识别技术约束：语言、框架、部署环境、性能要求
- 不要过度设计，MVP阶段够用就行

【方案设计】
- 提出最合理的架构方案，说明为什么选这个
- API定义必须完整：method/path/request/response
- 数据模型必须明确字段类型

【自审阶段】
- 接口是否清晰？扩展性如何？
- 有没有遗漏的边界情况？
"""

DEVELOPER_SYSTEM_PROMPT = """
你是高级程序员，代码质量是你的底线。按以下原则工作：

【任务拆解】
- 先列出要生成的文件清单，再逐个实现
- 每个文件职责单一，不要一个文件做太多事

【编码原则】
- 必须有错误处理（try/except）
- 必须有输入校验
- 函数/类必须有docstring
- 变量命名清晰，不用缩写

【自审阶段】
- 代码能运行吗？边界条件处理了吗？
- 有没有安全风险（路径注入、SQL注入）？
"""

REVIEWER_SYSTEM_PROMPT = """
你是代码审查专家，严格但公正。按以下维度逐项检查：

【Placeholder扫描】
- 有没有TODO/TBD/未完成的部分？
- 有没有硬编码的值应该提取为配置？

【内部一致性】
- 代码和需求对得上吗？
- 接口定义前后一致吗？

【边界检查】
- 错误处理做了吗？
- 空值/异常输入处理了吗？

【代码风格】
- 命名规范吗？有注释吗？
- 有没有重复代码？

每个问题必须指出具体文件和行号，不要泛泛而谈。
"""
```

#### 代码层（保障执行）

```python
from threading import Semaphore
from rag.resilience import retry

_llm_semaphore = Semaphore(5)  # 最多5个并发LLM调用

@retry(max_attempts=3, backoff_base=1.0)
def call_llm(messages: list) -> str:
    """统一LLM调用，内置retry和rate_limiter"""
    with _llm_semaphore:
        return llm.invoke(messages).content

def parse_and_validate(raw_output: str, schema: type[BaseModel]) -> BaseModel:
    """解析LLM输出并用Pydantic校验"""
    # 尝试提取JSON
    json_str = extract_json(raw_output)
    # Pydantic校验
    return schema.model_validate_json(json_str)

def validate_file_paths(files: list[CodeFile]) -> list[CodeFile]:
    """校验文件路径安全"""
    safe_files = []
    for f in files:
        # 防止路径注入
        if ".." in f.path or f.path.startswith("/"):
            raise SecurityError(f"不安全的文件路径: {f.path}")
        # 防止写入系统目录
        if any(f.path.startswith(p) for p in ["/etc", "/usr", "/var", "C:\\Windows"]):
            raise SecurityError(f"不允许写入系统目录: {f.path}")
        safe_files.append(f)
    return safe_files
```

### 4.9 Agent节点完整实现（以PM为例）

```python
from rag.resilience import retry

def pm_agent(state: ProjectState) -> dict:
    """PM节点：Prompt引导 + Schema校验 + 重试兜底 + 用户反馈"""
    messages = list(state.get("messages", []))
    rethink_count = state.get("rethink_count", {}).get("pm", 0)

    # Proposer-Critic讨论模式
    config = DISCUSSION_CONFIG["pm"]

    if config["enabled"]:
        result, discussion = proposer_critic_discuss(
            task=build_pm_prompt(state["requirement"]),
            proposer_prompt=PM_SYSTEM_PROMPT,
            critic_prompt=PM_CRITIC_PROMPT,
            llm=llm,
            max_rounds=config["max_rounds"],
            mode=config["mode"]
        )
        # 讨论记录存入messages
        for round_data in discussion:
            messages.append({"role": "assistant", "name": "pm_proposer",
                             "content": round_data["proposal"]})
            messages.append({"role": "assistant", "name": "pm_critic",
                             "content": format_critique(round_data["critique"])})
    else:
        result = call_llm([
            SystemMessage(content=PM_SYSTEM_PROMPT),
            HumanMessage(content=build_pm_prompt(state["requirement"]))
        ])

    # Schema校验
    output = parse_and_validate(result, PMOutput)

    # 输出验证
    if not output.user_stories:
        raise ValueError("PM输出为空，重试")

    # 需要澄清则interrupt（interrupt暂停后，图会自动重新执行本节点）
    if output.needs_clarification:
        clarification = interrupt({
            "type": "clarify",
            "message": "需求不够明确，请补充",
            "questions": output.clarification_questions
        })
        state["requirement"] += f"\n补充：{clarification}"
        result = call_llm([
            SystemMessage(content=PM_SYSTEM_PROMPT),
            HumanMessage(content=build_pm_prompt(state["requirement"]))
        ])
        output = parse_and_validate(result, PMOutput)

    # 用户反馈（重新审查）— 由前端rethink API触发，不默认interrupt
    if state.get("user_feedback") and rethink_count < 3:
        result, extra_discussion = proposer_critic_discuss(
            task=f"用户反馈：{state['user_feedback']}\n\n原方案：{result}\n\n请根据反馈改进",
            proposer_prompt=PM_SYSTEM_PROMPT,
            critic_prompt=PM_CRITIC_PROMPT,
            llm=llm,
            max_rounds=2,
            mode="full"
        )
        for round_data in extra_discussion:
            messages.append({"role": "assistant", "name": "pm_proposer",
                             "content": round_data["proposal"]})
            messages.append({"role": "assistant", "name": "pm_critic",
                             "content": format_critique(round_data["critique"])})
        output = parse_and_validate(result, PMOutput)
        rethink_count += 1

    messages.append({"role": "assistant", "name": "pm",
                      "content": f"已拆分为 {len(output.user_stories)} 个用户故事"})

    return {
        "user_stories": [s.model_dump() for s in output.user_stories],
        "features": [f.model_dump() for f in output.features],
        "current_agent": "architect",
        "user_feedback": None,  # 清除反馈
        "rethink_count": {**state.get("rethink_count", {}), "pm": rethink_count},
        "messages": messages
    }
```

> **注**：所有Agent节点（PM/Architect/Developer）都支持rethink机制，实现模式相同——检查`user_feedback`字段，有反馈则触发新一轮Proposer-Critic。Tester/Reviewer本身是质量关卡，不支持rethink。

---

## 5. 沙箱策略

### 5.1 方案：本地环境 + 临时目录

直接调用用户本地的Python/Node.js/SQL环境，无需Docker。

```python
import subprocess
import tempfile
import os
import signal

def execute_python(code: str, timeout: int = 30) -> dict:
    """在临时目录执行Python代码，含进程组安全杀掉"""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "main.py")
        with open(file_path, "w") as f:
            f.write(code)
        try:
            result = subprocess.run(
                ["python", file_path],
                capture_output=True, text=True,
                timeout=timeout, cwd=tmpdir,
                start_new_session=True  # 新进程组，防止子进程泄漏
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

def execute_node(code: str, timeout: int = 30) -> dict:
    """在临时目录执行Node.js代码"""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "main.js")
        with open(file_path, "w") as f:
            f.write(code)
        try:
            result = subprocess.run(
                ["node", file_path],
                capture_output=True, text=True,
                timeout=timeout, cwd=tmpdir,
                start_new_session=True
            )
        except subprocess.TimeoutExpired as e:
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

def execute_sql(code: str) -> dict:
    """SQLite内存执行"""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    try:
        cursor = conn.execute(code)
        rows = cursor.fetchall()
        return {"stdout": str(rows), "stderr": "", "returncode": 0}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": 1}
```

### 5.2 安全限制

- 超时保护：默认30秒
- 临时目录：执行后自动清理
- 输出捕获：stdout/stderr全部捕获
- 后续可选升级：import白名单、Docker隔离

---

## 6. 前端设计

### 6.1 页面清单

```
├── /login              登录页（复用RAGv3风格）
├── /                   主工作台（Agent流程+聊天）
├── /projects           项目列表（历史项目）
├── /projects/:id       项目详情（回看Agent过程）
└── /settings           设置（API Key、迭代次数、是否人工确认等）
```

### 6.2 主工作台布局

```
┌────────────────────────────────────────────────────────────┐
│  Blueprint Logo                              用户头像 | 设置  │
├──────────────────────────┬─────────────────────────────────┤
│                          │                                 │
│    Agent协作流程面板       │        聊天面板                 │
│    （动态高亮+计数器）      │                                 │
│                          │   ┌───────────────────────┐     │
│    ┌───┐                 │   │ PM: 需求分析完成       │     │
│    │PM │ ✓ 完成           │   │ 已拆分为5个用户故事    │     │
│    └─┬─┘                 │   ├───────────────────────┤     │
│      ↓                   │   │ Architect: 架构设计中  │     │
│    ┌───────────┐         │   │ 正在定义API接口...     │     │
│    │ Architect  │ ✓ 完成   │   ├───────────────────────┤     │
│    └─────┬─────┘         │   │                       │     │
│          ↓               │   │ [确认架构] [拒绝]      │     │
│    ┌─────────────────┐   │   │                       │     │
│    │ Developer       │   │   ├───────────────────────┤     │
│    │ ◉ 正在执行 (第2轮)│   │   │                       │     │
│    └────────┬────────┘   │   │  用户输入框            │     │
│             ↓            │   │  [发送需求...]         │     │
│    ┌───────────┐         │   └───────────────────────┘     │
│    │  Tester   │         │                                 │
│    │  ○ 等待   │         │                                 │
│    └───────────┘         │                                 │
│    ┌───────────┐         │                                 │
│    │ Reviewer  │         │                                 │
│    │  ○ 等待   │         │                                 │
│    └───────────┘         │                                 │
│                          │                                 │
│    迭代进度: ████░░ 2/3   │                                 │
└──────────────────────────┴─────────────────────────────────┘
```

### 6.3 节点状态视觉

| 状态 | 颜色 | 动画 |
|------|------|------|
| 等待中 | 灰色 | 无 |
| 执行中 | 蓝色 | 呼吸光效 + 动作动画 |
| 完成 | 绿色 | 淡入对勾 |
| 错误 | 红色 | 抖动 |
| 暂停 | 黄色 | 脉冲 |

### 6.4 卡通Agent形象

每个Agent用SVG卡通头像+动画：
- **PM** — 戴眼镜的产品经理，思考时有"..."动画
- **Architect** — 拿图纸的架构师，设计时有画线动画
- **Developer** — 戴耳机敲键盘的程序员，编码时有打字动画
- **Tester** — 拿放大镜的测试员，测试时有扫描动画
- **Reviewer** — 拿红笔的审查员，审查时有批注动画

### 6.5 移动端适配

```css
/* 桌面：两栏 */
@media (min-width: 768px) {
    .workspace { display: grid; grid-template-columns: 1fr 1fr; }
}

/* 移动：tab切换 */
@media (max-width: 767px) {
    .workspace { display: block; }
    .tab-bar { display: flex; }  /* [流程] [聊天] */
}
```

### 6.6 文件预览/下载

```
┌─────────────────────────────────────┐
│  ✓ 项目完成！                        │
│                                     │
│  生成文件：                          │
│  📄 main.py          [预览] [下载]   │
│  📄 index.html       [预览] [下载]   │
│  📄 style.css        [预览] [下载]   │
│  📄 test_main.py     [预览] [下载]   │
│                                     │
│  [打包下载全部]                       │
└─────────────────────────────────────┘
```

---

## 7. WebSocket协议

### 7.1 消息类型

```typescript
// 后端 → 前端
type ServerMessage =
  | { type: "agent_start", agent: string }
  | { type: "agent_thinking", agent: string, content: string }
  | { type: "agent_update", agent: string, data: object }
  | { type: "agent_done", agent: string }
  | { type: "interrupt", data: {
      type: "confirm" | "clarify",
      message: string,
      payload: object
    }}
  | { type: "error", message: string }
  | { type: "project_done", files: Record<string, string> }
  | { type: "state_sync", state: ProjectState }

// 前端 → 后端
type ClientMessage =
  | { type: "start_project", requirement: string }
  | { type: "resume", thread_id: string, response: {
      approved?: boolean,
      clarification?: string
    }}
  | { type: "rethink", thread_id: string, node: string, feedback: string }
  | { type: "cancel" }
  | { type: "reconnect", thread_id: string }
```

### 7.2 interrupt→resume流程

```
后端                              前端
 │                                 │
 │  ┌─ 图执行到 human_confirm ──┐  │
 │  │  interrupt() 暂停         │  │
 │  └───────────────────────────┘  │
 │                                 │
 │── interrupt {type:"confirm"} ──→│
 │                                 │── 弹出确认对话框
 │                                 │── 展示架构设计
 │                                 │── 用户点击"批准"
 │                                 │
 │←───── resume {approved:true} ───│
 │                                 │
 │  ┌─ 图从 interrupt 恢复 ─────┐  │
 │  │  继续执行                  │  │
 │  └───────────────────────────┘  │
```

### 7.3 流式推送实现

```python
async def run_project(requirement: str, websocket: WebSocket):
    project_id = str(uuid4())
    config = {"configurable": {"thread_id": project_id}}
    initial_state = {
        "project_id": project_id,
        "requirement": requirement,
        "iteration": 0,
        "max_iterations": 3,
        "status": "running",
        "messages": []
    }

    current_agent = None
    async for event in app.stream(initial_state, config):
        agent_name = list(event.keys())[0]
        agent_output = event[agent_name]

        if agent_name != current_agent:
            await websocket.send_json({
                "type": "agent_start",
                "agent": agent_name
            })
            current_agent = agent_name

        await websocket.send_json({
            "type": "agent_update",
            "agent": agent_name,
            "data": agent_output
        })

        if agent_output.get("status") == "delivered":
            await websocket.send_json({
                "type": "project_done",
                "files": agent_output.get("files", {})
            })

    # 检查是否被interrupt暂停
    snapshot = app.get_state(config)
    if snapshot.next:
        interrupt_data = snapshot.tasks[-1].interrupts[0].value
        await websocket.send_json({
            "type": "interrupt",
            "data": interrupt_data
        })
```

### 7.4 断线重连

```javascript
let currentThreadId = null;

ws.onclose = () => {
    setTimeout(() => {
        if (currentThreadId) {
            connectWebSocket(currentThreadId);
        }
    }, 2000);
};

ws.onmessage = (event) => {
    if (event.type === "state_sync") {
        restoreFlowPanel(event.state);
        restoreMessages(event.state.messages);
    }
};
```

---

## 8. API设计

### 8.1 REST API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/projects | 创建新项目 |
| GET | /api/projects | 获取项目列表 |
| GET | /api/projects/{id} | 获取项目详情 |
| POST | /api/resume | 恢复interrupt的图执行 |
| POST | /api/rethink | 触发重新审查（用户反馈） |
| POST | /api/cancel | 取消当前项目 |
| GET | /api/projects/{id}/files | 获取项目生成的文件 |
| GET | /api/projects/{id}/download | 打包下载项目文件 |
| POST | /api/auth/login | 登录 |
| POST | /api/auth/register | 注册 |
| GET | /api/settings | 获取用户设置 |
| PUT | /api/settings | 更新用户设置 |

#### /api/rethink 请求体

```json
{
  "thread_id": "项目ID",
  "node": "pm",           // 要重新审查的节点
  "feedback": "用户反馈内容"
}
```

#### /api/rethink 后端处理

```python
@app.post("/api/rethink")
async def rethink(req: RethinkRequest):
    config = {"configurable": {"thread_id": req.thread_id}}
    snapshot = app.get_state(config)

    # 更新state：设置用户反馈，清除该节点的输出强制重跑
    app.update_state(config, {
        "user_feedback": req.feedback,
        **clear_node_output(snapshot.values, req.node)
    })

    # 从该节点重新开始stream
    async for event in app.stream(None, config):
        # 推送WebSocket...
        pass
```

### 8.2 WebSocket

| 路径 | 说明 |
|------|------|
| /ws/project | 项目执行的WebSocket连接 |

---

## 9. 复用RAGv3模块

| 模块 | 路径 | 复用方式 |
|------|------|---------|
| JWT认证 | rag/auth.py | 直接复用 |
| 用户系统 | rag/user_db.py | 直接复用 |
| 对话记忆 | rag/memory.py | 改造为项目历史存储 |
| 容错层 | rag/resilience.py | 直接复用（retry, circuit_breaker） |
| 安全防护 | rag/guard.py | 直接复用 |
| 前端CSS变量 | static/index.html | 复用暗黑科技风样式 |
| 配置管理 | config.py | 扩展Blueprint配置项 |
| 日志 | rag/logging_config.py | 直接复用 |

---

## 10. 实现计划

详见 [2026-06-04-Blueprint-implementation-plan.md](./2026-06-04-Blueprint-implementation-plan.md)

**总计：约9天**（前端与后端并行，实际墙钟时间约7天）

---

## 11. 面试价值

| 亮点 | 面试能讲的 |
|------|-----------|
| 双层保障架构 | "Agent质量靠两层保障：Prompt层引导思考（角色定义+推理策略），代码层保障执行（Pydantic schema校验+resilience重试+路径安全检查）。不是靠prompt让LLM'听话'，而是用代码强制校验输出" |
| Proposer-Critic对抗 | "我用了双Agent对抗模式，PM/Architect内部讨论3轮再输出，但不是盲目3轮——根据阶段特性配置：PM/Architect用full模式深度讨论，Developer用post_review模式快速迭代，Tester/Reviewer本身就是质量关卡不需要再套一层。全流程从30次调用优化到12次" |
| Pydantic Schema | "每个Agent的输出都有严格的Pydantic模型定义，LLM输出必须通过schema校验才能进入下一个节点，不会出现字段缺失或类型错误" |
| 图架构 | "我用了LangGraph的StateGraph编排，条件分支+循环，测试失败自动回开发，审查不通过自动修改，最多循环3次防止死循环" |
| 条件分支+循环 | "测试失败自动回开发，审查不通过自动修改，最多循环3次防止死循环" |
| interrupt机制 | "关键节点用LangGraph的interrupt暂停，等人工确认后继续，防止Agent跑偏" |
| 状态持久化 | "用LangGraph的checkpoint，任何节点中断都能恢复，支持断点续做" |
| 流式输出 | "前端实时展示每个Agent的思考过程，用WebSocket推送" |
| 本地沙箱 | "参考扣子的云端沙箱思路，实现了本地版受限执行环境" |

---

## 12. 后续扩展（MVP不做）

| 功能 | 说明 | 面试话术 |
|------|------|---------|
| **并行开发** | 开发阶段拆分为前端/后端并行，结果合并回state | "架构预留了并行扩展点" |
| **代码模板** | 预置Flask/React/Vue等常见项目模板 | "支持模板扩展，减少重复生成" |
| **版本控制** | deliver_node集成Git，每次修改自动commit | "设计了可插拔的交付策略" |
| **多模型支持** | 除DeepSeek外支持GPT/Claude等模型 | "LLM层抽象，可热切换" |

---

## 13. 部署注意事项

### JWT Secret管理

**当前方案（开发阶段）：** 自动生成+持久化到`.Blueprint_secret`文件

**问题：** 以下场景会导致secret变化，旧token全部失效：
- 删除`.Blueprint_secret`文件
- 多实例部署（每个实例有自己的secret）
- 换机器部署（新机器没有secret文件）
- `git clean -fd`清掉secret文件

**部署时必须改为：**
```python
# 方案1：环境变量（推荐）
JWT_SECRET = os.environ.get("Blueprint_JWT_SECRET")

# 方案2：密钥管理服务
JWT_SECRET = load_from_vault("Blueprint/jwt-secret")
```

### LLM API Key管理

**当前方案：** `.env`文件或`config.py`默认值

**部署时必须改为：**
```python
# 环境变量注入，不写入代码或配置文件
Blueprint_LLM_API_KEY = os.environ.get("Blueprint_LLM_API_KEY")
```

### 数据持久化

| 数据 | 当前存储 | 部署建议 |
|------|---------|---------|
| 用户数据 | SQLite (`Blueprint/data/Blueprint_memory.db`) | PostgreSQL |
| 项目文件 | 本地目录 (`Blueprint/projects/`) | 对象存储(S3/MinIO) |
| 设置 | JSON文件 (`Blueprint/data/settings.json`) | 数据库 |
| JWT Secret | 文件 (`Blueprint/.Blueprint_secret`) | 环境变量/密钥管理 |
