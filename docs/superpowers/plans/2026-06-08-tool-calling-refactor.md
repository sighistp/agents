# Blueprint 工具调用重构实现计划（TDD）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 Developer/Tester/Reviewer 从"LLM 输出 JSON → 解析"改为"LLM 调用工具 → 执行 → 循环"。

**Architecture:** OpenAI function calling 工具循环。LLM 自己决定调什么工具、什么时候完成。工具执行结果回传 LLM，LLM 看到结果后决定下一步。

**Tech Stack:** LangChain bind_tools, OpenAI function calling, Pydantic, 既有沙箱执行器

**Design Spec:** `docs/superpowers/specs/2026-06-08-tool-calling-refactor-design.md`

---

## 文件结构

```
Blueprint/
├── agents/
│   ├── tools.py              ← 新建：工具定义 + 工具集分组
│   ├── tool_executor.py      ← 新建：execute_tool + 路径校验
│   ├── developer.py          ← 重写：JSON输出 → 工具循环
│   ├── tester.py             ← 重写：JSON输出 → 工具循环
│   ├── reviewer.py           ← 重写：JSON输出 → 工具循环
│   └── graph.py              ← 微调：路由适配新返回值
├── utils/
│   └── llm.py                ← 加函数：call_llm_with_tools
├── tests/
│   ├── test_tools.py         ← 新建
│   ├── test_tool_executor.py ← 新建
│   ├── test_developer.py     ← 重写
│   ├── test_tester.py        ← 重写
│   └── test_reviewer.py      ← 重写
└── frontend/src/
    └── components/
        └── ChatPanel.vue     ← 加消息渲染逻辑
```

---

### Task 1: 工具定义（TDD）

**Files:**
- Create: `Blueprint/agents/tools.py`
- Create: `Blueprint/tests/test_tools.py`

- [ ] **Step 1: 写失败的测试**

```python
# Blueprint/tests/test_tools.py
import json
import pytest
from Blueprint.agents.tools import (
    FILE_WRITE, FILE_READ, EXECUTE_PYTHON, DONE,
    DEVELOPER_TOOLS, TESTER_TOOLS, REVIEWER_TOOLS,
    serialize_call,
)


def test_file_write_schema():
    """file_write 工具应有正确的 JSON Schema"""
    assert FILE_WRITE["type"] == "function"
    assert FILE_WRITE["function"]["name"] == "file_write"
    params = FILE_WRITE["function"]["parameters"]
    assert "path" in params["properties"]
    assert "content" in params["properties"]
    assert params["required"] == ["path", "content"]


def test_file_read_schema():
    """file_read 工具应有正确的 JSON Schema"""
    assert FILE_READ["function"]["name"] == "file_read"
    params = FILE_READ["function"]["parameters"]
    assert "path" in params["properties"]
    assert params["required"] == ["path"]


def test_execute_python_schema():
    """execute_python 工具应有正确的 JSON Schema"""
    assert EXECUTE_PYTHON["function"]["name"] == "execute_python"
    params = EXECUTE_PYTHON["function"]["parameters"]
    assert "code" in params["properties"]
    assert params["required"] == ["code"]


def test_done_schema():
    """done 工具应有 summary、files_modified、key_decisions 字段"""
    assert DONE["function"]["name"] == "done"
    params = DONE["function"]["parameters"]
    assert "summary" in params["properties"]
    assert "files_modified" in params["properties"]
    assert "key_decisions" in params["properties"]
    assert params["required"] == ["summary"]


def test_developer_tools():
    """Developer 应有 file_write, file_read, execute_python, done"""
    names = [t["function"]["name"] for t in DEVELOPER_TOOLS]
    assert names == ["file_write", "file_read", "execute_python", "done"]


def test_tester_tools():
    """Tester 应有 file_read, execute_python, done"""
    names = [t["function"]["name"] for t in TESTER_TOOLS]
    assert names == ["file_read", "execute_python", "done"]


def test_reviewer_tools():
    """Reviewer 应有 file_read, done"""
    names = [t["function"]["name"] for t in REVIEWER_TOOLS]
    assert names == ["file_read", "done"]


def test_serialize_call():
    """serialize_call 应将 LangChain tool_call 转为 OpenAI 格式"""
    # 模拟 LangChain tool_call 对象
    class MockCall:
        id = "call_123"
        class function:
            name = "file_write"
            arguments = '{"path": "main.py", "content": "print(1)"}'

    result = serialize_call(MockCall())
    assert result["id"] == "call_123"
    assert result["type"] == "function"
    assert result["function"]["name"] == "file_write"
    assert "main.py" in result["function"]["arguments"]
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd "c:/Users/lahm/Desktop/Many AgentS" && python -m pytest Blueprint/tests/test_tools.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'Blueprint.agents.tools'`

- [ ] **Step 3: 写最小实现**

```python
# Blueprint/agents/tools.py
"""工具定义：OpenAI function calling 格式"""
import json
from typing import Any


# ── 工具 Schema ─────────────────────────────────────────────────────────

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
                "code": {"type": "string", "description": "要执行的 Python 代码"},
                "timeout": {"type": "integer", "description": "超时秒数（默认15，最大30）"}
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
                    "description": "关键决策"
                }
            },
            "required": ["summary"]
        }
    }
}


# ── 工具集分组 ──────────────────────────────────────────────────────────

DEVELOPER_TOOLS = [FILE_WRITE, FILE_READ, EXECUTE_PYTHON, DONE]
TESTER_TOOLS = [FILE_READ, EXECUTE_PYTHON, DONE]
REVIEWER_TOOLS = [FILE_READ, DONE]


# ── 辅助函数 ────────────────────────────────────────────────────────────

def serialize_call(call: Any) -> dict:
    """将 LangChain tool_call 转为 OpenAI 协议格式"""
    return {
        "id": call.id,
        "type": "function",
        "function": {
            "name": call.function.name,
            "arguments": call.function.arguments,
        }
    }
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
cd "c:/Users/lahm/Desktop/Many AgentS" && python -m pytest Blueprint/tests/test_tools.py -v
```

Expected: 8 tests passed

---

### Task 2: 工具执行引擎（TDD）

**Files:**
- Create: `Blueprint/agents/tool_executor.py`
- Create: `Blueprint/tests/test_tool_executor.py`

- [ ] **Step 1: 写失败的测试**

```python
# Blueprint/tests/test_tool_executor.py
import json
import os
import pytest
import tempfile
from Blueprint.agents.tool_executor import execute_tool, _validate_path


class MockCall:
    def __init__(self, name, arguments):
        self.id = "call_test"
        self.function = type("F", (), {"name": name, "arguments": json.dumps(arguments)})()


def test_file_write(tmp_path):
    """file_write 应创建文件并返回成功"""
    call = MockCall("file_write", {"path": "main.py", "content": "print('hello')"})
    result = json.loads(execute_tool(call, str(tmp_path)))
    assert result["success"] is True
    assert (tmp_path / "main.py").read_text() == "print('hello')"


def test_file_write_nested_path(tmp_path):
    """file_write 应创建嵌套目录"""
    call = MockCall("file_write", {"path": "src/utils.py", "content": "x=1"})
    result = json.loads(execute_tool(call, str(tmp_path)))
    assert result["success"] is True
    assert (tmp_path / "src" / "utils.py").read_text() == "x=1"


def test_file_read(tmp_path):
    """file_read 应读取已有文件"""
    (tmp_path / "test.txt").write_text("hello world")
    call = MockCall("file_read", {"path": "test.txt"})
    result = json.loads(execute_tool(call, str(tmp_path)))
    assert result["content"] == "hello world"


def test_file_read_not_found(tmp_path):
    """file_read 文件不存在应返回错误"""
    call = MockCall("file_read", {"path": "nonexistent.py"})
    result = json.loads(execute_tool(call, str(tmp_path)))
    assert "error" in result


def test_execute_python(tmp_path):
    """execute_python 应执行代码并返回输出"""
    call = MockCall("execute_python", {"code": "print(1+1)"})
    result = json.loads(execute_tool(call, str(tmp_path)))
    assert result["returncode"] == 0
    assert "2" in result["stdout"]


def test_execute_python_with_timeout(tmp_path):
    """execute_python 应支持自定义超时"""
    call = MockCall("execute_python", {"code": "import time; time.sleep(1)", "timeout": 5})
    result = json.loads(execute_tool(call, str(tmp_path)))
    assert result["returncode"] == 0


def test_done():
    """done 应返回结构化结果"""
    call = MockCall("done", {"summary": "完成了", "files_modified": ["a.py"]})
    result = json.loads(execute_tool(call, "/tmp"))
    assert result["status"] == "completed"
    assert result["summary"] == "完成了"


def test_unknown_tool():
    """未知工具应返回错误"""
    call = MockCall("unknown_tool", {})
    result = json.loads(execute_tool(call, "/tmp"))
    assert "error" in result


def test_validate_path_rejects_dotdot():
    """.. 路径应被拒绝"""
    with pytest.raises(ValueError, match="不安全"):
        _validate_path("../etc/passwd", "/tmp")


def test_validate_path_rejects_absolute():
    """绝对路径应被拒绝"""
    with pytest.raises(ValueError, match="不安全"):
        _validate_path("/etc/passwd", "/tmp")


def test_validate_path_rejects_empty():
    """空路径应被拒绝"""
    with pytest.raises(ValueError, match="不安全"):
        _validate_path("", "/tmp")
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd "c:/Users/lahm/Desktop/Many AgentS" && python -m pytest Blueprint/tests/test_tool_executor.py -v
```

Expected: FAIL

- [ ] **Step 3: 写最小实现**

```python
# Blueprint/agents/tool_executor.py
"""工具执行引擎：执行 LLM 返回的 tool_call，返回 JSON 结果"""
import json
import os


def execute_tool(call, project_dir: str) -> str:
    """执行 tool_call，返回 JSON 字符串。失败不抛异常，返回错误信息。"""
    name = call.function.name
    args = json.loads(call.function.arguments)

    try:
        if name == "file_write":
            return _file_write(args, project_dir)
        elif name == "file_read":
            return _file_read(args, project_dir)
        elif name == "execute_python":
            return _execute_python(args)
        elif name == "done":
            return json.dumps({"status": "completed", **args})
        else:
            return json.dumps({"error": f"未知工具: {name}"})
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


def _file_write(args: dict, project_dir: str) -> str:
    path = os.path.join(project_dir, args["path"])
    _validate_path(args["path"], project_dir)
    dirname = os.path.dirname(path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(args["content"])
    return json.dumps({"success": True, "path": args["path"]})


def _file_read(args: dict, project_dir: str) -> str:
    path = os.path.join(project_dir, args["path"])
    _validate_path(args["path"], project_dir)
    if not os.path.exists(path):
        return json.dumps({"error": f"文件不存在: {args['path']}"})
    with open(path, "r", encoding="utf-8") as f:
        return json.dumps({"content": f.read()})


def _execute_python(args: dict) -> str:
    from Blueprint.sandbox.executor import execute_python as sandbox_exec
    timeout = min(args.get("timeout", 15), 30)
    result = sandbox_exec(args["code"], timeout=timeout)
    return json.dumps(result)


def _validate_path(path: str, project_dir: str):
    """防止路径注入和符号链接逃逸"""
    if not path or ".." in path or path.startswith(("/", "\\")):
        raise ValueError(f"不安全的文件路径: {path}")
    real = os.path.realpath(os.path.join(project_dir, path))
    if not real.startswith(os.path.realpath(project_dir)):
        raise ValueError(f"路径逃逸: {path}")
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
cd "c:/Users/lahm/Desktop/Many AgentS" && python -m pytest Blueprint/tests/test_tool_executor.py -v
```

Expected: 11 tests passed

---

### Task 3: LLM 工具调用封装（TDD）

**Files:**
- Modify: `Blueprint/utils/llm.py`
- Create: `Blueprint/tests/test_llm_tools.py`

- [ ] **Step 1: 写失败的测试**

```python
# Blueprint/tests/test_llm_tools.py
import pytest
from unittest.mock import MagicMock, patch


def test_call_llm_with_tools_exists():
    """call_llm_with_tools 应可导入"""
    from Blueprint.utils.llm import call_llm_with_tools
    assert callable(call_llm_with_tools)


def test_call_llm_with_tools_binds_tools():
    """call_llm_with_tools 应调用 llm.bind_tools"""
    from Blueprint.utils.llm import call_llm_with_tools
    from Blueprint.agents.tools import DEVELOPER_TOOLS

    mock_llm = MagicMock()
    mock_llm_with_tools = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm_with_tools
    mock_llm_with_tools.invoke.return_value = MagicMock(content="ok", tool_calls=[])

    with patch("Blueprint.utils.llm._get_llm", return_value=mock_llm):
        result = call_llm_with_tools([{"role": "user", "content": "test"}], DEVELOPER_TOOLS)

    mock_llm.bind_tools.assert_called_once_with(DEVELOPER_TOOLS)
    mock_llm_with_tools.invoke.assert_called_once()
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd "c:/Users/lahm/Desktop/Many AgentS" && python -m pytest Blueprint/tests/test_llm_tools.py -v
```

Expected: FAIL — `ImportError: cannot import name 'call_llm_with_tools'`

- [ ] **Step 3: 写最小实现**

在 `Blueprint/utils/llm.py` 末尾加：

```python
def call_llm_with_tools(messages: list, tools: list):
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

- [ ] **Step 4: 运行测试，验证通过**

```bash
cd "c:/Users/lahm/Desktop/Many AgentS" && python -m pytest Blueprint/tests/test_llm_tools.py -v
```

Expected: 2 tests passed

---

### Task 4: Developer Agent 重写（TDD）

**Files:**
- Modify: `Blueprint/agents/developer.py`
- Modify: `Blueprint/tests/test_developer.py`

- [ ] **Step 1: 写失败的测试**

```python
# Blueprint/tests/test_developer.py
import json
import pytest
from unittest.mock import patch, MagicMock


def _make_tool_call(name, arguments, call_id="call_1"):
    """构造模拟的 tool_call 对象"""
    call = MagicMock()
    call.id = call_id
    call.function.name = name
    call.function.arguments = json.dumps(arguments)
    return call


def _make_response(content="", tool_calls=None):
    """构造模拟的 LLM response"""
    resp = MagicMock()
    resp.content = content
    resp.tool_calls = tool_calls or []
    return resp


def test_developer_uses_tools():
    """Developer 应使用工具循环而非 JSON 输出"""
    from Blueprint.agents.developer import developer_agent
    from Blueprint.agents.state import create_initial_state

    state = create_initial_state("test-dev", "Build a calculator")

    # 模拟 LLM：第一次调 file_write，第二次调 done
    responses = [
        _make_response("", [_make_tool_call("file_write", {"path": "main.py", "content": "print(1)"})]),
        _make_response("", [_make_tool_call("done", {"summary": "完成"})]),
    ]

    with patch("Blueprint.agents.developer.call_llm_with_tools", side_effect=responses):
        with patch("Blueprint.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"success": True, "path": "main.py"})
            result = developer_agent(state)

    assert "files" in result
    assert "main.py" in result["files"]
    assert result.get("error") is None


def test_developer_returns_key_decisions():
    """Developer done 工具的 key_decisions 应传入返回值"""
    from Blueprint.agents.developer import developer_agent
    from Blueprint.agents.state import create_initial_state

    state = create_initial_state("test-dev", "Build a calculator")

    responses = [
        _make_response("", [_make_tool_call("file_write", {"path": "a.py", "content": "x=1"})]),
        _make_response("", [_make_tool_call("done", {"summary": "完成", "key_decisions": ["用Flask"]})]),
    ]

    with patch("Blueprint.agents.developer.call_llm_with_tools", side_effect=responses):
        with patch("Blueprint.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"success": True, "path": "a.py"})
            result = developer_agent(state)

    assert "key_decisions" in result
    assert "用Flask" in result["key_decisions"]


def test_developer_handles_no_tool_calls():
    """LLM 不调工具时应当作隐式完成"""
    from Blueprint.agents.developer import developer_agent
    from Blueprint.agents.state import create_initial_state

    state = create_initial_state("test-dev", "Build a calculator")

    responses = [
        _make_response("", [_make_tool_call("file_write", {"path": "a.py", "content": "x=1"})]),
        _make_response("我完成了"),  # 没有 tool_calls
    ]

    with patch("Blueprint.agents.developer.call_llm_with_tools", side_effect=responses):
        with patch("Blueprint.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"success": True, "path": "a.py"})
            result = developer_agent(state)

    assert "files" in result
    assert result.get("error") is None


def test_developer_max_steps():
    """超过最大步数应返回错误"""
    from Blueprint.agents.developer import developer_agent
    from Blueprint.agents.state import create_initial_state

    state = create_initial_state("test-dev", "Build a calculator")

    # 每次都返回 file_write，永不 done
    always_write = _make_response("", [_make_tool_call("file_write", {"path": "a.py", "content": "x=1"})])

    with patch("Blueprint.agents.developer.call_llm_with_tools", return_value=always_write):
        with patch("Blueprint.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"success": True, "path": "a.py"})
            result = developer_agent(state)

    assert result.get("error") is not None
    assert "最大步数" in result["error"]
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd "c:/Users/lahm/Desktop/Many AgentS" && python -m pytest Blueprint/tests/test_developer.py -v
```

Expected: FAIL

- [ ] **Step 3: 重写 developer.py**

```python
# Blueprint/agents/developer.py
"""Developer Agent: 用工具循环生成代码"""
import json
import logging
from typing import Any

from Blueprint.agents.tools import DEVELOPER_TOOLS, serialize_call
from Blueprint.agents.tool_executor import execute_tool
from Blueprint.utils.llm import call_llm_with_tools

logger = logging.getLogger(__name__)

DEVELOPER_SYSTEM_PROMPT = """你是高级程序员。用工具逐步完成编码任务。

规则：
- 用 file_write 写文件，用 execute_python 验证代码能跑
- 发现 bug 就修，最多修 3 次
- 每个文件职责单一，命名清晰
- 完成后调 done 工具，summary 里说明做了什么，files_modified 里列出修改的文件"""


def build_developer_task(state: dict) -> str:
    """构建 Developer 的任务描述"""
    requirement = state.get("requirement", "")
    architecture = state.get("architecture", {})
    api_defs = state.get("api_definitions", [])
    iteration = state.get("iteration", 0)

    task = f"需求：{requirement}\n"
    if architecture:
        task += f"架构：{json.dumps(architecture, ensure_ascii=False)}\n"
    if api_defs:
        task += "API：\n"
        for api in api_defs:
            task += f"- {api.get('method', 'GET')} {api.get('path', '')}: {api.get('description', '')}\n"
    task += f"当前迭代：第{iteration + 1}次\n"

    feedback = state.get("user_feedback")
    if feedback:
        task += f"用户反馈：{feedback}\n"

    return task


def developer_agent(state: dict) -> dict[str, Any]:
    """Developer agent: 工具循环模式"""
    messages = [
        {"role": "system", "content": DEVELOPER_SYSTEM_PROMPT},
        {"role": "user", "content": build_developer_task(state)}
    ]

    project_dir = f"projects/{state.get('project_id', 'default')}"
    collected_files = {}
    done_result = None
    max_steps = 10

    for step in range(max_steps):
        try:
            response = call_llm_with_tools(messages, DEVELOPER_TOOLS)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return {
                "files": collected_files,
                "iteration": state.get("iteration", 0) + 1,
                "error": str(e),
                "messages": messages,
            }

        # LLM 没调工具 → 隐式完成或出错
        if not response.tool_calls:
            if response.content:
                break
            continue

        # 一条 assistant 消息，包含所有 tool_calls
        messages.append({
            "role": "assistant",
            "content": response.content or "",
            "tool_calls": [serialize_call(call) for call in response.tool_calls]
        })

        # 每个 tool_call 一条 tool 消息
        for call in response.tool_calls:
            args = json.loads(call.function.arguments)
            result = execute_tool(call, project_dir)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": result
            })

            if call.function.name == "done":
                done_result = args
            elif call.function.name == "file_write":
                collected_files[args["path"]] = args["content"]

        if done_result:
            return {
                "files": collected_files,
                "iteration": state.get("iteration", 0) + 1,
                "key_decisions": done_result.get("key_decisions", []),
                "messages": messages,
            }

    # 超过最大步数
    return {
        "files": collected_files,
        "iteration": state.get("iteration", 0) + 1,
        "error": "超过最大步数" if not collected_files else None,
        "messages": messages,
    }
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
cd "c:/Users/lahm/Desktop/Many AgentS" && python -m pytest Blueprint/tests/test_developer.py -v
```

Expected: 4 tests passed

---

### Task 5: Tester Agent 重写（TDD）

**Files:**
- Modify: `Blueprint/agents/tester.py`
- Modify: `Blueprint/tests/test_tester.py`

- [ ] **Step 1: 写失败的测试**

```python
# Blueprint/tests/test_tester.py
import json
import pytest
from unittest.mock import patch, MagicMock


def _make_tool_call(name, arguments, call_id="call_1"):
    call = MagicMock()
    call.id = call_id
    call.function.name = name
    call.function.arguments = json.dumps(arguments)
    return call


def _make_response(content="", tool_calls=None):
    resp = MagicMock()
    resp.content = content
    resp.tool_calls = tool_calls or []
    return resp


def test_tester_uses_tools():
    """Tester 应使用工具循环"""
    from Blueprint.agents.tester import tester_agent
    from Blueprint.agents.state import create_initial_state

    state = create_initial_state("test-test", "Build a calculator")
    state["files"] = {"main.py": "print(1)"}

    responses = [
        _make_response("", [_make_tool_call("execute_python", {"code": "print(1)"})]),
        _make_response("", [_make_tool_call("done", {"summary": "1 passed, 0 failed"})]),
    ]

    with patch("Blueprint.agents.tester.call_llm_with_tools", side_effect=responses):
        with patch("Blueprint.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"returncode": 0, "stdout": "1\n", "stderr": ""})
            result = tester_agent(state)

    assert "test_passed" in result
    assert "messages" in result


def test_tester_only_has_read_and_execute_tools():
    """Tester 不应有 file_write 工具"""
    from Blueprint.agents.tools import TESTER_TOOLS
    names = [t["function"]["name"] for t in TESTER_TOOLS]
    assert "file_write" not in names
    assert "file_read" in names
    assert "execute_python" in names
    assert "done" in names
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd "c:/Users/lahm/Desktop/Many AgentS" && python -m pytest Blueprint/tests/test_tester.py -v
```

Expected: FAIL

- [ ] **Step 3: 重写 tester.py**

结构同 developer_agent，区别：
- 工具集：TESTER_TOOLS
- system prompt：测试工程师角色
- 最大步数：8
- 返回值：`test_passed`, `test_results`

- [ ] **Step 4: 运行测试，验证通过**

```bash
cd "c:/Users/lahm/Desktop/Many AgentS" && python -m pytest Blueprint/tests/test_tester.py -v
```

Expected: 2 tests passed

---

### Task 6: Reviewer Agent 重写（TDD）

**Files:**
- Modify: `Blueprint/agents/reviewer.py`
- Modify: `Blueprint/tests/test_reviewer.py`

- [ ] **Step 1: 写失败的测试**

```python
# Blueprint/tests/test_reviewer.py
import json
import pytest
from unittest.mock import patch, MagicMock


def _make_tool_call(name, arguments, call_id="call_1"):
    call = MagicMock()
    call.id = call_id
    call.function.name = name
    call.function.arguments = json.dumps(arguments)
    return call


def _make_response(content="", tool_calls=None):
    resp = MagicMock()
    resp.content = content
    resp.tool_calls = tool_calls or []
    return resp


def test_reviewer_uses_tools():
    """Reviewer 应使用工具循环"""
    from Blueprint.agents.reviewer import reviewer_agent
    from Blueprint.agents.state import create_initial_state

    state = create_initial_state("test-review", "Build a calculator")
    state["files"] = {"main.py": "print(1)"}

    responses = [
        _make_response("", [_make_tool_call("file_read", {"path": "main.py"})]),
        _make_response("", [_make_tool_call("done", {"summary": "代码质量良好，无critical问题"})]),
    ]

    with patch("Blueprint.agents.reviewer.call_llm_with_tools", side_effect=responses):
        with patch("Blueprint.agents.tool_executor.execute_tool") as mock_exec:
            mock_exec.return_value = json.dumps({"content": "print(1)"})
            result = reviewer_agent(state)

    assert "review_approved" in result
    assert "messages" in result


def test_reviewer_only_has_read_tool():
    """Reviewer 不应有 file_write 或 execute_python"""
    from Blueprint.agents.tools import REVIEWER_TOOLS
    names = [t["function"]["name"] for t in REVIEWER_TOOLS]
    assert "file_write" not in names
    assert "execute_python" not in names
    assert "file_read" in names
    assert "done" in names
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd "c:/Users/lahm/Desktop/Many AgentS" && python -m pytest Blueprint/tests/test_reviewer.py -v
```

Expected: FAIL

- [ ] **Step 3: 重写 reviewer.py**

结构同 developer_agent，区别：
- 工具集：REVIEWER_TOOLS
- system prompt：代码审查专家角色
- 最大步数：5
- 返回值：`review_approved`, `review_comments`

- [ ] **Step 4: 运行测试，验证通过**

```bash
cd "c:/Users/lahm/Desktop/Many AgentS" && python -m pytest Blueprint/tests/test_reviewer.py -v
```

Expected: 2 tests passed

---

### Task 7: Graph 集成（TDD）

**Files:**
- Modify: `Blueprint/agents/graph.py`
- Modify: `Blueprint/tests/test_graph.py`

- [ ] **Step 1: 更新路由函数**

Developer 返回值变了（不再有 `current_agent`），路由函数需要适配：

```python
def route_after_developer(state: ProjectState) -> str:
    error = state.get("error")
    if error:
        if "security" in error.lower() or "path" in error.lower():
            return END
        retry_count = state.get("_developer_retry_count", 0)
        if retry_count >= 2:
            return END
        return "developer"
    return "reviewer"
```

- [ ] **Step 2: 运行图测试**

```bash
cd "c:/Users/lahm/Desktop/Many AgentS" && python -m pytest Blueprint/tests/test_graph.py -v
```

Expected: 15 tests passed（图结构不变，路由函数逻辑不变）

- [ ] **Step 3: 运行全部测试**

```bash
cd "c:/Users/lahm/Desktop/Many AgentS" && python -m pytest Blueprint/tests/ -q
```

Expected: ALL tests passed

---

### Task 8: 前端 ChatPanel 适配

**Files:**
- Modify: `frontend/src/components/ChatPanel.vue`

- [ ] **Step 1: 加 tool_calls 渲染**

在 ChatPanel.vue 的消息渲染逻辑里，加 tool_calls 和 tool 消息的处理：

```javascript
// 在 renderMessage 或 addMessage 逻辑里加
function formatMessageContent(msg) {
    // tool 消息：显示执行结果
    if (msg.role === 'tool') {
        try {
            const result = JSON.parse(msg.content);
            if (result.stdout) return `📤 ${result.stdout.slice(0, 200)}`;
            if (result.error) return `❌ ${result.error}`;
            if (result.success) return `✅ 已写入 ${result.path}`;
            if (result.content) return result.content.slice(0, 200);
            return msg.content.slice(0, 200);
        } catch {
            return msg.content.slice(0, 200);
        }
    }

    // assistant 消息带 tool_calls：显示操作描述
    if (msg.tool_calls && msg.tool_calls.length > 0) {
        const actions = msg.tool_calls.map(tc => {
            const name = tc.function?.name || tc.name;
            try {
                const args = JSON.parse(tc.function?.arguments || '{}');
                if (name === 'file_write') return `📝 写入 ${args.path}`;
                if (name === 'file_read') return `📖 读取 ${args.path}`;
                if (name === 'execute_python') return '▶️ 执行代码';
                if (name === 'done') return '✅ 完成';
                return `🔧 ${name}`;
            } catch { return `🔧 ${name}`; }
        });
        return actions.join('，');
    }

    return msg.content;
}
```

- [ ] **Step 2: 在 addMessage 里使用 formatMessageContent**

```javascript
// 修改 msg-content 的渲染
<div class="msg-content">{{ formatMessageContent(msg) }}</div>
```

- [ ] **Step 3: 重新构建前端**

```bash
cd "c:/Users/lahm/Desktop/Many AgentS/frontend" && npm run build
```

- [ ] **Step 4: 运行前端测试**

```bash
cd "c:/Users/lahm/Desktop/Many AgentS/frontend" && npx vitest run
```

Expected: 48 tests passed

---

## 依赖关系

```
Task 1 (工具定义) → Task 2 (工具执行) → Task 3 (LLM封装)
                                            ↓
                    Task 4 (Developer) ←───┘
                    Task 5 (Tester)    ←───┘
                    Task 6 (Reviewer)  ←───┘
                         ↓
                    Task 7 (Graph集成)
                         ↓
                    Task 8 (前端适配)
```

## 预计工时

| Task | 内容 | 工时 |
|------|------|------|
| 1-3 | 工具定义 + 执行引擎 + LLM 封装 | 1 小时 |
| 4-6 | Developer/Tester/Reviewer 重写 | 1.5 小时 |
| 7 | Graph 集成 | 30 分钟 |
| 8 | 前端适配 | 30 分钟 |

**总计：约 3.5 小时**
