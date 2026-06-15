# 项目详情页重构 + 三层存储设计

> 日期：2026-06-12
> 范围：后端存储层 + API + 前端 ProjectDetailPage
> 策略：功能优先，UI 美化后期迭代

## 一、目标

当前项目详情页只有平铺的文本消息和文件列表，无法查看完整开发过程和执行摘要。需要：

1. 存储完整 Agent 对话历史（不只是精简摘要）
2. 项目详情页改为卡片布局，分类展示信息
3. 支持重新运行、编辑需求、导出项目操作

## 二、三层数据存储

| 层 | 存什么 | 表 | 写入时机 | 读取时机 |
|---|--------|-----|---------|---------|
| 精简摘要 | 每 Agent 1 条用户可见消息（截断 2000 字符） | project_messages（已有） | Agent 完成时 | 聊天显示、刷新恢复 |
| 结构化摘要 | result_summary + tool_calls JSON | agent_executions（已有） | Agent 完成时 | 执行摘要卡片 |
| 完整对话 | Agent 的 LLM 对话（过滤 system 消息） | agent_conversations（新增） | Agent 完成时 | 开发日志卡片（懒加载） |

**说明：** project_messages 的 2000 字符截断不影响功能 — 完整数据在 agent_conversations，精简摘要仅供聊天显示和刷新恢复使用。

### agent_conversations 表结构

```sql
CREATE TABLE IF NOT EXISTS agent_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    messages TEXT NOT NULL,       -- JSON: 过滤后的 LLM 对话 [{role, content, tool_calls, ...}]
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_conv ON agent_conversations(project_id, agent_name, iteration);
```

**存储过滤规则：** 只存 `role=assistant` 和 `role=tool` 的消息，不存 `role=system`（system prompt 体积大且含内部逻辑）。

**空间估算：** 5 Agent × 4 轮 × 3KB（过滤后）= 60KB/项目，100 个项目 = 6MB

## 三、API 改动

### 修改 GET /api/projects/{id}/state

返回值精简为 meta + files + messages（不含 conversations/executions）：

```json
{
  "project_id": "...",
  "name": "紫色计算器",
  "requirement": "...",
  "status": "delivered",
  "iteration": 3,
  "files": {"main.py": "...", "index.html": "..."},
  "messages": [
    {"role": "assistant", "name": "developer", "content": "写入 3 个文件..."},
    {"role": "assistant", "name": "tester", "content": "测试通过..."}
  ]
}
```

**注意：** `name` 字段可能为 `None`（旧项目或未命名项目）。前端显示时兜底：`name || requirement || project_id`。

### 新增 GET /api/projects/{id}/conversations

懒加载完整对话历史：

```json
{
  "conversations": [
    {
      "agent_name": "developer",
      "iteration": 1,
      "messages": [
        {"role": "assistant", "content": "...", "tool_calls": [...]},
        {"role": "tool", "content": "..."}
      ]
    }
  ]
}
```

### 新增 GET /api/projects/{id}/executions

懒加载执行摘要：

```json
{
  "executions": [
    {
      "agent_name": "developer",
      "iteration": 1,
      "result_summary": "写入 3 个文件: main.py, index.html, style.css",
      "tool_calls": "[{\"name\": \"file_write\", \"args_summary\": \"main.py\"}]",
      "status": "success",
      "created_at": "2026-06-12T00:39:40"
    }
  ]
}
```

### 新增 GET /api/projects/{id}/export

打包下载：
- 所有项目文件（用 `read_bytes` 读取，兼容二进制文件如图片）
- meta.json（含 name 字段）
- conversations.json（完整对话历史）
- executions.json（执行摘要）

**注意：** 不能用 `read_text` 读项目文件，二进制文件会 UnicodeDecodeError。必须用 `read_bytes`。

返回 `application/zip`，Content-Disposition 带文件名。

## 四、前端 ProjectDetailPage 重构

### 卡片布局

页面结构：
```
┌─────────────────────────────────────┐
│ ← 返回    项目名称    🔄 ✏️ 📤      │  ← 操作栏
├─────────────────────────────────────┤
│ 📋 项目信息                         │  ← 卡片 1（立即加载）
│ 名称 | 时间 | 状态 | 迭代 | 需求    │
├─────────────────────────────────────┤
│ 💬 开发日志            [展开/折叠]  │  ← 卡片 2（展开时懒加载）
│ Agent 对话历史（按迭代分组）         │
├─────────────────────────────────────┤
│ 📁 生成文件                         │  ← 卡片 3（立即加载）
│ 文件列表 + 预览 + 下载              │
├─────────────────────────────────────┤
│ 📊 执行摘要                         │  ← 卡片 4（展开时懒加载）
│ 每 Agent 的结构化结果               │
└─────────────────────────────────────┘
```

### 懒加载策略

| 卡片 | 加载时机 | 数据来源 |
|------|---------|---------|
| 📋 项目信息 | 页面打开立即加载 | GET /state（轻量） |
| 📁 生成文件 | 页面打开立即加载 | GET /state（含文件内容） |
| 💬 开发日志 | 用户点击展开时 | GET /conversations（按需） |
| 📊 执行摘要 | 用户点击展开时 | GET /executions（按需） |

### Loading / Error / Empty 状态

| 状态 | 显示 |
|------|------|
| 加载中 | 骨架屏（灰色占位条） |
| 加载失败 | 红色错误提示 + 重试按钮 |
| 数据为空 | "暂无数据"占位文字 |

### 操作按钮

| 按钮 | 功能 | 实现 |
|------|------|------|
| 🔄 重新运行 | 用同一个需求新建项目 | 确认弹窗 → project store 设 `pendingRequirement` → `router.push('/')` → WorkbenchPage onMounted 自动发送 |
| ✏️ 编辑需求 | 编辑后新建项目 | 弹窗编辑需求 → 同上流程 |
| 📤 导出 | 下载 zip 包 | `window.open('/api/projects/{id}/export')` |

**跨页传参：** project store 新增 `pendingRequirement` 字段。WorkbenchPage `onMounted` 检查该字段，非空时自动调用 `sendMessage(pendingRequirement)` 并清空。

**重新运行安全检查：**
- 显示确认弹窗："将用相同需求创建新项目，是否继续？"
- 不覆盖原项目（新建 proj-{timestamp}）
- 不检查是否有运行中项目（用户可以同时跑多个）

**编辑需求：** 新建项目，不覆盖原项目。原项目保留。

## 五、websocket.py 改动

### 存储完整对话

在 `_run_graph_sync` 的 Agent 完成处理中，把完整对话存入 `agent_conversations`：

```python
# LangGraph messages 是 BaseMessage 对象，需要先转 dict
raw_msgs = node_output.get("messages", [])
dict_msgs = [m.dict() if hasattr(m, 'dict') else m for m in raw_msgs]

# 过滤掉 system 消息，只存 assistant 和 tool
filtered_msgs = [m for m in dict_msgs if m.get("role") in ("assistant", "tool")]
mem.save_conversation(project_id, node_name, iteration, filtered_msgs)
```

### 填充 tool_calls 字段

tool_calls 嵌在 messages 里面（AIMessage.tool_calls），不是顶层字段。从 messages 中提取：

```python
all_tool_calls = []
for m in dict_msgs:
    if isinstance(m, dict) and m.get("tool_calls"):
        all_tool_calls.extend(m["tool_calls"])
    elif hasattr(m, 'tool_calls') and m.tool_calls:
        all_tool_calls.extend(m.tool_calls)

tool_calls_json = json.dumps([
    {"name": get_call_name(tc), "args_summary": str(get_call_args(tc))[:200]}
    for tc in all_tool_calls
], ensure_ascii=False)
mem.save_execution(project_id, node_name, iteration, result_summary, status, tool_calls=tool_calls_json)
```

## 六、改动范围

| 文件 | 改什么 |
|------|--------|
| memory.py | 新增 `agent_conversations` 表 + `save_conversation()` / `get_conversations()`；`save_execution` 新增 `tool_calls` 参数；BaseMessage→dict 转换 |
| websocket.py | 存完整对话到 `agent_conversations`（过滤 system）；`save_execution` 传 tool_calls |
| projects.py | `GET /state` 返回 name；新增 `GET /conversations`、`GET /executions`、`GET /export` |
| ProjectDetailPage.vue | 重写为卡片布局 + 懒加载 + 操作按钮 |
| stores/project.js | 新增 `pendingRequirement` 字段 |
| pages/WorkbenchPage.vue | onMounted 检查 `pendingRequirement` 并自动发送 |
| api/index.js | 新增 `getProjectConversations()` / `getProjectExecutions()` / `exportProject()` |

## 七、不做的事

- ❌ 通讯页面 💾 保存按钮不动
- ❌ project_messages 精简存储逻辑不动（截断 2000 字符可接受，完整数据在 conversations）
- ❌ 项目列表页不动
- ❌ UI 美化后期再做（先功能后样式）

## 八、测试策略

| 测试类型 | 覆盖内容 |
|----------|---------|
| 后端测试 | agent_conversations 表读写、过滤 system 消息、GET /conversations、GET /executions、GET /export 打包 |
| 前端测试 | ProjectDetailPage 卡片渲染、懒加载、操作按钮事件、pendingRequirement 跨页传参 |
| 集成测试 | 完整流程：运行项目 → 保存 → 打开详情页 → 展开开发日志/执行摘要 → 导出 |
