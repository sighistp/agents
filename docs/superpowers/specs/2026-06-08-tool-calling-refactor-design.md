# Blueprint Agent 工具调用重构设计文档

> **日期：** 2026-06-08
> **状态：** 设计定稿
> **目标：** 将 Developer/Tester/Reviewer 从"LLM 输出 JSON → 解析"改为"LLM 调用工具 → 执行 → 循环"

---

## 1. 背景

### 当前问题

| 问题 | 表现 |
|------|------|
| Agent 没有"做事"的能力 | Developer 让 LLM 一次性输出所有文件的 JSON，质量差 |
| 错误处理靠代码 if/else | Developer 报错 → graph 路由回 Developer → 死循环 |
| Tester 编造测试结果 | LLM 输出 `test_passed: true` 但代码根本没跑 |
| token 浪费 | 一次输出所有文件内容，大部分是废话 |

### 根因

当前每个 Agent 节点 = 一次 LLM 调用 + JSON 解析。Agent 没有工具，不能逐步执行、不能自我修正。

### 目标

- Developer/Tester/Reviewer 改用 OpenAI function calling 工具循环
- LLM 自己决定调什么工具、什么时候完成
- PM/Architect 保持不变（纯推理，JSON 输出够用）

---

## 2. 工具定义

### 工具集

| 工具 | 说明 | Developer | Tester | Reviewer |
|------|------|:---------:|:------:|:--------:|
| `file_write` | 写文件到项目目录 | ✅ | ❌ | ❌ |
| `file_read` | 读取项目目录中的文件 | ✅ | ✅ | ✅ |
| `execute_python` | 执行 Python 代码 | ✅ | ✅ | ❌ |
| `done` | 标记任务完成 | ✅ | ✅ | ✅ |

### 工具 JSON Schema

```python
# agents/tools.py

FILE_WRITE = {
    "type": "function",
    "function": {
        "name": "file_write",
        "description": "写入文件到项目目录",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径，如 main.py"},
                "content": {"type": "string", "description": "文件内容"}
            },
            "required": ["path", "content"]
        }
    }
}

FILE_READ = {
    "type": "function",
    "function": {
        "name": "file_read",
        "description": "读取项目目录中的文件",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"}
            },
            "required": ["path"]
        }
    }
}

EXECUTE_PYTHON = {
    "type": "function",
    "function": {
        "name": "execute_python",
        "description": "执行 Python 代码并返回输出",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "要执行的 Python 代码"}
            },
            "required": ["code"]
        }
    }
}

DONE = {
    "type": "function",
    "function": {
        "name": "done",
        "description": "标记任务完成，输出结构化结果",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "完成总结"},
                "files_modified": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "修改的文件列表"
                },
                "key_decisions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "关键决策（架构选型、技术选择等）"
                }
            },
            "required": ["summary"]
        }
    }
}

# 工具集分组
DEVELOPER_TOOLS = [FILE_WRITE, FILE_READ, EXECUTE_PYTHON, DONE]
TESTER_TOOLS = [FILE_READ, EXECUTE_PYTHON, DONE]
REVIEWER_TOOLS = [FILE_READ, DONE]
```

---

## 3. 工具执行引擎

```python
# agents/tool_executor.py

import os
import json
from Blueprint.sandbox.executor import execute_python as sandbox_execute_python

def execute_tool(call, project_dir: str) -> str:
    """执行 LLM 返回的 tool_call，返回 JSON 字符串结果。
    
    工具失败不抛异常，返回错误信息让 LLM 自己决定怎么处理。
    """
    name = call.function.name
    args = json.loads(call.function.arguments)

    if name == "file_write":
        path = os.path.join(project_dir, args["path"])
        # 路径安全校验
        _validate_path(args["path"], project_dir)
        dirname = os.path.dirname(path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(args["content"])
        return json.dumps({"success": True, "path": args["path"]})

    elif name == "file_read":
        path = os.path.join(project_dir, args["path"])
        _validate_path(args["path"], project_dir)
        if not os.path.exists(path):
            return json.dumps({"error": f"文件不存在: {args['path']}"})
        with open(path, "r", encoding="utf-8") as f:
            return json.dumps({"content": f.read()})

    elif name == "execute_python":
        timeout = args.get("timeout", 15)
        result = sandbox_execute_python(args["code"], timeout=min(timeout, 30))
        return json.dumps(result)

    elif name == "done":
        return json.dumps({"status": "completed", **args})

    else:
        return json.dumps({"error": f"未知工具: {name}"})


def _validate_path(path: str, project_dir: str):
    """防止路径注入和符号链接逃逸"""
    if not path or ".." in path or path.startswith(("/", "\\")):
        raise ValueError(f"不安全的文件路径: {path}")
    # 解析真实路径，防止符号链接逃逸
    real = os.path.realpath(os.path.join(project_dir, path))
    if not real.startswith(os.path.realpath(project_dir)):
        raise ValueError(f"路径逃逸: {path}")
```

---

## 4. LLM 工具调用封装

```python
# utils/llm.py — 新增函数

def call_llm_with_tools(messages: list, tools: list) -> Any:
    """调用 LLM 并绑定工具，返回完整 response（含 tool_calls）。
    
    Args:
        messages: 消息列表
        tools: OpenAI function calling 格式的工具列表
    
    Returns:
        LangChain AIMessage，包含 .content 和 .tool_calls
    """
    llm = _get_llm()
    llm_with_tools = llm.bind_tools(tools)
    return llm_with_tools.invoke(messages)
```

DeepSeek 和 MIMO 都支持 OpenAI 兼容的 tool calling，`bind_tools()` 直接能用。

---

## 5. Agent 节点重构

### Developer（工具循环模式）

```python
# agents/developer.py

DEVELOPER_SYSTEM_PROMPT = """你是高级程序员。用工具逐步完成编码任务。

规则：
- 用 file_write 写文件，用 execute_python 验证代码能跑
- 发现 bug 就修，最多修 3 次
- 每个文件职责单一
- 完成后调 done 工具，summary 里说明做了什么，files_modified 里列出修改的文件
"""

def serialize_call(call) -> dict:
    """将 LangChain tool_call 转为 OpenAI 协议格式"""
    return {
        "id": call.id,
        "type": "function",
        "function": {
            "name": call.function.name,
            "arguments": call.function.arguments,
        }
    }

def developer_agent(state: ProjectState) -> dict:
    from Blueprint.agents.tools import DEVELOPER_TOOLS
    from Blueprint.agents.tool_executor import execute_tool

    messages = [
        {"role": "system", "content": DEVELOPER_SYSTEM_PROMPT},
        {"role": "user", "content": build_developer_task(state)}
    ]

    project_dir = f"projects/{state['project_id']}"
    collected_files = {}
    done_result = None
    max_steps = 10

    for step in range(max_steps):
        response = call_llm_with_tools(messages, DEVELOPER_TOOLS)

        # LLM 没调工具 → 隐式完成或出错
        if not response.tool_calls:
            if response.content:
                # LLM 输出了文本但没调工具，当作隐式完成
                break
            continue

        # 一条 assistant 消息，包含所有 tool_calls（OpenAI 协议）
        messages.append({
            "role": "assistant",
            "content": response.content or "",
            "tool_calls": [serialize_call(call) for call in response.tool_calls]
        })

        # 每个 tool_call 一条 tool 消息
        for call in response.tool_calls:
            args = json.loads(call.function.arguments)

            # 执行工具
            result = execute_tool(call, project_dir)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": result
            })

            # done → 记录结果，继续处理剩余 tool_calls
            if call.function.name == "done":
                done_result = args

            # file_write → 记录到 collected_files
            if call.function.name == "file_write":
                collected_files[args["path"]] = args["content"]

        # 所有 tool_calls 处理完后，如果有 done 就返回
        if done_result:
            return {
                "files": collected_files,
                "iteration": state.get("iteration", 0) + 1,
                "key_decisions": done_result.get("key_decisions", []),
                "messages": messages,
            }

    # 超过最大步数或隐式完成
    return {
        "files": collected_files,
        "iteration": state.get("iteration", 0) + 1,
        "error": "超过最大步数" if not collected_files else None,
        "messages": messages,
    }
```

### Tester（工具循环模式）

```python
TESTER_SYSTEM_PROMPT = """你是测试工程师。用工具验证代码的正确性。

规则：
- 用 file_read 读取代码
- 用 execute_python 执行测试
- 覆盖正常路径、边界条件、错误处理
- 完成后调 done 工具，summary 里写测试结果（X passed, Y failed）
"""

# 结构同 Developer，工具集改为 TESTER_TOOLS，最大步数 8
```

### Reviewer（工具循环模式）

```python
REVIEWER_SYSTEM_PROMPT = """你是代码审查专家。用工具读取代码并审查。

规则：
- 用 file_read 读取代码，逐文件审查
- 检查：安全漏洞、逻辑错误、代码风格、边界条件
- 每个问题指出具体文件和行号
- 完成后调 done 工具，summary 里写审查结论
"""

# 结构同 Developer，工具集改为 REVIEWER_TOOLS，最大步数 5
```

### PM 和 Architect（不变）

继续用 JSON 输出 + Pydantic Schema 校验。纯推理任务不需要工具。

---

## 6. 改动范围

| 文件 | 操作 | 说明 |
|------|------|------|
| `agents/tools.py` | 新建 | 工具定义 + 工具集分组 |
| `agents/tool_executor.py` | 新建 | execute_tool + 路径校验 |
| `agents/developer.py` | 重写 | JSON 输出 → 工具循环 |
| `agents/tester.py` | 重写 | JSON 输出 → 工具循环 |
| `agents/reviewer.py` | 重写 | JSON 输出 → 工具循环 |
| `utils/llm.py` | 加函数 | call_llm_with_tools() |
| `agents/graph.py` | 微调 | Developer 返回值结构变了 |

**不改的：** pm.py, architect.py, discussion.py, schemas.py, state.py, sandbox/executor.py, 前端

---

## 7. 风险和应对

| 风险 | 应对 |
|------|------|
| LLM 不调工具，直接输出文本 | 检测 `not tool_calls`，有 content 则当作隐式完成 |
| LLM 调工具但参数格式错 | execute_tool 里 try/except，返回错误信息给 LLM |
| 工具循环超过最大步数 | 强制退出，返回已收集的结果 |
| file_write 路径注入 | _validate_path + realpath 防符号链接逃逸 |
| file_write 空目录 | dirname 为空时跳过 makedirs |
| LLM 说 done 但文件没写 | 检查 collected_files 是否为空，空则报错 |
| execute_python 卡死 | 沙箱默认 15 秒超时，硬上限 30 秒 |
| 消息协议违规 | 一条 assistant 消息包含所有 tool_calls，每条 tool_call 对应一条 tool 消息 |
| token 消耗比以前高 | 工具循环每步只输出一个文件，总 token 应该更低 |

---

## 8. 与现有设计的关系

| 现有设计 | 保留/改 |
|---------|---------|
| LangGraph 图结构 | 保留，节点函数签名不变 |
| Proposer-Critic | 保留，PM/Architect 继续用 |
| Pydantic Schema | 保留，PM/Architect 继续用 |
| 沙箱执行器 | 保留，execute_python 直接复用 |
| 前端 | 保留，WebSocket 消息格式不变 |
| interrupt 机制 | 保留，human_confirm 不变 |
| rethink 机制 | 保留，user_feedback 传入 Developer 的 task |

---

## 9. 预期效果

| 指标 | 改前 | 改后 |
|------|------|------|
| Developer 调用次数 | 1 次 LLM（输出所有文件 JSON） | 5-10 次 LLM（每次一个工具调用） |
| 错误处理 | 代码 if/else + 重试 | LLM 看到错误信息自己修 |
| 测试执行 | LLM 编造结果 | 真正跑代码 |
| token 消耗 | 一次输出所有文件 | 逐步输出，每步更少 |
| 代码质量 | 一次性生成，质量差 | 写→跑→修，质量高 |
