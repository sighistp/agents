# Blueprint P0 功能设计（v2 — 审查修正版）

> **日期:** 2026-06-16
> **状态:** 设计完成，待实施
> **范围:** 3 个 P0 功能（实时进度 / 费用追踪 / Tester 结构化解析）
> **修正来源:** P0 设计冲突与问题审查报告

---

## 1. 实时工具进度

### 1.1 方案

模块级回调，不改 Agent 签名。tool_executor 执行前触发回调，websocket.py 在 graph 启动前设置回调。

### 1.2 改动

**tool_executor.py（加 5 行）：**
```python
_progress_callback = None

def set_progress_callback(cb):
    global _progress_callback
    _progress_callback = cb

def execute_tool(call, project_dir: str) -> str:
    name = get_call_name(call)
    args = get_call_args(call)
    if _progress_callback:
        try:
            _progress_callback(tool=name, args_summary=f"执行 {name}")
        except Exception:
            pass  # 回调失败不影响工具执行
    # 执行逻辑不变
    ...
```

**websocket.py（加 2 行）：**
```python
# _start_graph 前
from blueprint.agents.tool_executor import set_progress_callback
set_progress_callback(lambda **kw: _put({"type": "tool_progress", "project_id": project_id, "data": kw}))
```

**新增 ToolProgress.vue 组件（嵌入 FlowPanel，不影响现有布局）：**

```vue
<!-- FlowPanel.vue 顶部加 1 行 -->
<ToolProgress v-if="toolProgress" :progress="toolProgress" />
```

### 1.3 错误处理

- tool_progress 发送失败（WS 断连）→ 跳过，不影响工具执行
- 回调异常 → try/except 静默

### 1.4 配置开关

```python
# config.py
tool_progress_enabled: bool = True  # 设为 False 关闭实时进度
```

### 1.5 改动文件

| 文件 | 改动 |
|------|------|
| `blueprint/agents/tool_executor.py` | 加模块级回调 + set_progress_callback |
| `blueprint/api/websocket.py` | 设置回调 + 转发 tool_progress |
| `blueprint/config.py` | 新增 tool_progress_enabled |
| `frontend/src/components/ToolProgress.vue` | **新增** |
| `frontend/src/components/FlowPanel.vue` | 加 1 行 import + 渲染 |
| `frontend/src/composables/useWebSocket.js` | 处理 tool_progress |

---

## 2. 费用追踪

### 2.1 方案

side effect 记录（不改 llm.py 返回值）+ contextvars 并发隔离。

### 2.2 改动

**新增 cost_tracker.py：**
```python
import contextvars
import json
import os
from pathlib import Path

_current_project_id = contextvars.ContextVar('project_id', default='')

def set_project_context(project_id: str):
    _current_project_id.set(project_id)

def record_cost(response):
    """从 LLM response 中提取 token 并记录（side effect）"""
    project_id = _current_project_id.get()
    if not project_id:
        return
    try:
        usage = getattr(response, 'usage_metadata', None)
        if not usage:
            return
        input_tokens = usage.get('input_tokens', 0) or 0
        output_tokens = usage.get('output_tokens', 0) or 0
        # 写入 cost 文件
        cost_dir = Path("blueprint/data/costs")
        cost_dir.mkdir(parents=True, exist_ok=True)
        cost_file = cost_dir / f"{project_id}.json"
        # 读取现有数据或初始化
        data = _load_cost(cost_file)
        data["total_input_tokens"] += input_tokens
        data["total_output_tokens"] += output_tokens
        data["total_calls"] += 1
        # 计算费用（DeepSeek 定价）
        data["estimated_cost_usd"] = round(
            data["total_input_tokens"] / 1_000_000 * 0.27 +
            data["total_output_tokens"] / 1_000_000 * 1.10, 6
        )
        _save_cost(cost_file, data)
    except Exception:
        pass  # 记录失败不影响 LLM 调用
```

**llm.py 改动（4 个函数各加 1 行）：**
```python
from blueprint.utils.cost_tracker import record_cost

# call_llm / call_llm_async / call_llm_with_tools / call_llm_with_tools_async
# 每个函数在 return 前加:
record_cost(response)  # side effect，不改返回值
```

**websocket.py 改动：**
```python
# _run_async 开头
from blueprint.utils.cost_tracker import set_project_context
set_project_context(project_id)
```

### 1.3 并发安全

- `_current_project_id` 用 contextvars，每个 graph 线程独立
- cost 文件按 project_id 隔离，不同项目不互相覆盖
- 同一项目的并发调用（理论上不存在）用 JSON 原子写入保护

### 1.4 错误处理

| 场景 | 兜底 |
|------|------|
| record_cost 失败 | try/except，不影响 LLM 调用 |
| cost 文件损坏 | 返回空数据，不影响详情页 |
| 多用户并发 | contextvars 隔离 |

---

## 2. Tester 结构化解析

### 2.1 问题

`_extract_test_passed` 靠 LLM 文本摘要判断，"0失败"被误判为失败。

### 2.2 方案

从 Tester 的 execute_python 输出中提取结构化数据：

```python
def _extract_test_passed(summary: str, had_execution_errors: bool) -> bool:
    """从 summary 和执行结果中提取 test_passed"""
    # 优先：检查实际执行结果
    if had_execution_errors:
        return False

    # 从 summary 中提取数字
    import re
    passed = re.search(r'(\d+)\s*passed', summary.lower())
    failed = re.search(r'(\d+)\s*failed', summary.lower())
    errors = re.search(r'(\d+)\s*error', summary.lower())

    if passed and not failed and not errors:
        return True
    if failed and int(failed.group(1)) > 0:
        return False
    if errors and int(errors.group(1)) > 0:
        return False

    # 兜底：用关键词判断
    pass_keywords = ["全部通过", "all passed", "0 fail", "0 error", "0失败"]
    for kw in pass_keywords:
        if kw in summary.lower():
            return True
    return True  # 默认通过
```

### 2.3 改动

- `tester.py`：修改 `_extract_test_passed` 函数
- 不改路由逻辑、不改 Agent 节点、不改 graph.py

---

## 3. 配置开关（回滚方案）

**config.py 新增：**
```python
tool_progress_enabled: bool = True
cost_tracking_enabled: bool = True
auto_fix_enabled: bool = True
```

每个新功能检查对应开关，出问题时设为 False 即可回退。

---

## 4. 实施顺序（修正后）

```
1. cost_tracker.py（纯新增，零风险）
   - contextvars 隔离
   - 配置开关
   - try/except 兜底

2. llm.py 改造（加 record_cost side effect，低风险）
   - 4 个函数各加 1 行
   - 不改返回值

3. tool_executor.py 改造（加模块级回调，低风险）
   - 加 set_progress_callback + 执行前触发
   - 不改 Agent 签名

4. websocket.py 改造（接收新消息类型，低风险）
   - _start_graph 前设置回调
   - 发 tool_progress 和 cost_update 消息

5. tester.py 结构化解析（改 _extract_test_passed，低风险）
   - 从 pytest output 提取 passed/failed/skipped
   - 不改路由逻辑

6. config.py 新增配置开关

7. 前端集成（ToolProgress.vue + useWebSocket + ChatPanel）
```

**预计工作量：** 3 天（比原来省 1 天，因为不改 graph.py 路由）

---

## 5. 验证清单

- [ ] 实时进度：Developer 执行时前端显示工具调用进度
- [ ] 实时进度：WebSocket 断连时 tool_progress 不崩溃
- [ ] 费用追踪：项目完成后聊天显示费用报告
- [ ] 费用追踪：多用户并发时不互相覆盖（contextvars）
- [ ] 费用追踪：LLM 调用失败时不崩溃（try/except）
- [ ] Tester 解析：pytest output 正确提取 passed/failed/skipped
- [ ] Tester 解析：现有 191 个测试全部通过
- [ ] 回归：现有 341 个测试全部通过
- [ ] 回滚：每个新功能有配置开关，可单独关闭
