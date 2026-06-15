# DevTeam 通讯页面 UX 改进设计

> 日期：2026-06-11
> 范围：WorkbenchPage（通讯页面）+ ChatPanel + FlowPanel
> 策略：组件拆分（方案 B），不改整体布局

## 一、目标

当前通讯页面存在以下问题：
1. Agent 输出混在纯文本聊天中，无法快速区分文件/测试/审查
2. 左侧 Agent 卡片只是状态显示，不可交互
3. 保存项目无命名功能，无反馈
4. 无法暂停正在运行的任务
5. 代码文件不能在页面内预览

## 二、组件结构

### 现有结构
```
WorkbenchPage
├── FlowPanel（28 行，4 个子组件）
└── ChatPanel（145 行，消息渲染+输入+操作全混在一起）
```

### 目标结构
```
WorkbenchPage
├── FlowPanel（改进）
│   ├── AgentCard（可交互，点击展开详情）
│   ├── IterationInfo（进度条更醒目）
│   ├── OutputPanel（文件可预览）
│   └── DiscussionPanel
└── ChatPanel（拆分）
    ├── ChatHeader（操作栏：暂停/继续/保存/清空/新建）
    ├── SaveDialog（保存命名弹窗）
    ├── MessageList（消息列表）
    │   └── AgentOutputCard（结构化 Agent 输出卡片）
    └── ChatInput（输入框 + 发送）
```

### 新增组件

| 组件 | 文件 | 职责 |
|------|------|------|
| SaveDialog.vue | components/SaveDialog.vue | 保存命名弹窗 |
| AgentOutputCard.vue | components/AgentOutputCard.vue | Agent 输出结构化卡片 |
| ChatHeader.vue | components/ChatHeader.vue | 从 ChatPanel 拆出的操作栏 |

### 新增 composable

| Composable | 文件 | 职责 |
|------------|------|------|
| useFilePreview.js | composables/useFilePreview.js | 文件预览逻辑（OutputPanel 和 ProjectDetailPage 共用） |

## 三、数据流 + 状态管理

### project store 新增字段

```js
// 暂停/继续状态
isPaused: false,
isRunning: false,

// 保存相关
saveDialogVisible: false,
autoSaveName: '',  // 从需求自动生成
```

### WebSocket 新增消息类型

| 方向 | 类型 | 说明 |
|------|------|------|
| 前端→后端 | `pause` | 暂停当前任务 |
| 前端→后端 | `resume_execution` | 继续执行 |
| 前端→后端 | `stop` | 停止任务（不可恢复） |
| 后端→前端 | `paused` | 确认已暂停 |
| 后端→前端 | `resumed` | 确认已继续 |
| 后端→前端 | `stopped` | 确认已停止 |

### 暂停实现

**暂停粒度：每个 Agent 完成后检查。** 不是每个迭代结束后，也不是在 LLM 调用中途。具体位置：`_run_async` 中 `async for event in app.astream(...)` 的循环体内，每次处理完一个节点的输出后检查 `stop_event`。

流程：
1. 前端发 `{type: "pause"}` 到 WebSocket
2. 后端 websocket.py 设 `stop_event`（per-connection，不影响其他用户）
3. graph 线程在当前 Agent 完成后检查 `stop_event`，发现已设 → 暂停
4. 后端发 `{type: "paused"}` 到前端
5. 前端设 `isPaused = true`
6. 用户点继续 → 前端发 `{type: "resume_execution"}`
7. 后端清除 `stop_event`，graph 从下一个 Agent 继续执行
8. 后端发 `{type: "resumed"}` 到前端

**示例：** PM 跑完 → Architect 跑完 → 用户点暂停 → Developer 不会启动 → 暂停在 Developer 之前。用户点继续 → Developer 开始执行。

### 停止实现

停止是不可恢复的取消操作：
1. 前端发 `{type: "stop"}` 到 WebSocket
2. 后端设 `stop_event` + 设 `cancelled = True`
3. graph 线程在当前 Agent 完成后检查 `stop_event` → 停止
4. 后端发 `{type: "stopped"}` 到前端
5. 前端设 `isRunning = false`、`isPaused = false`
6. 前端显示"任务已停止"系统消息

**与 cancel 的区别：** 现有的 `cancel` 消息会清空 graph 状态。`stop` 保留当前已生成的文件和消息，只是不再继续执行。两者可以合并（stop = cancel + 保留状态），在实现时统一处理。

### 保存命名

1. 前端 POST /api/projects 新增 `name` 字段
2. 后端 meta.json 存入 `name`
3. GET /api/projects 返回 `name`
4. ProjectsPage 显示 `name` 作为标题

## 四、功能详细设计

### 4.1 Agent 输出结构化

**AgentOutputCard 组件**根据 `msg.name` 渲染不同卡片：

| Agent | 卡片内容 | 颜色 |
|-------|---------|------|
| PM | 用户故事数 + 功能特性数 | 蓝 #3B82F6 |
| Architect | API 数 + 数据模型数 | 紫 #8B5CF6 |
| Developer | 写入文件列表 + 执行结果 | 绿 #10B981 |
| Tester | 通过/失败数 + 测试摘要 | 橙 #F59E0B |
| Reviewer | 审查结论 + 问题列表 | 粉 #EC4899 |

**实现方式：** ChatPanel 的消息渲染改为判断 `msg.name`，如果是 Agent 消息就用 AgentOutputCard，否则用普通文本。

**消息数据来源：** WebSocket 的 `agent_update` 消息中，`data.data` 包含该 Agent 的完整输出。

**各 Agent 的 `agent_update` 数据结构：**

```json
// Developer 的 agent_update
{
  "type": "agent_update",
  "agent": "developer",
  "data": {
    "files": {"main.py": "print('hello')", "index.html": "<html>..."},
    "iteration": 2,
    "key_decisions": ["使用 FastAPI", "前后端分离"],
    "test_passed": true,
    "error": null,
    "messages": [{"role": "assistant", "name": "developer", "content": "..."}]
  }
}

// Tester 的 agent_update
{
  "type": "agent_update",
  "agent": "tester",
  "data": {
    "test_passed": false,
    "test_results": [{"summary": "2 passed, 1 failed: test_divide_by_zero"}],
    "error": null,
    "messages": [{"role": "assistant", "name": "tester", "content": "..."}]
  }
}

// Reviewer 的 agent_update
{
  "type": "agent_update",
  "agent": "reviewer",
  "data": {
    "review_approved": false,
    "review_comments": [
      {"file": "main.py", "line": 15, "severity": "important", "description": "未处理除零", "suggestion": "加 if 检查"}
    ],
    "error": null,
    "messages": [{"role": "assistant", "name": "reviewer", "content": "..."}]
  }
}
```

**兜底逻辑：** 如果 `data.data` 中没有预期字段（如 Agent 输出格式变化），AgentOutputCard 退化为显示 `msg.content` 纯文本。不崩溃，不丢失信息。

**前端防御性取值：**
```js
// AgentOutputCard 内部
const files = computed(() => props.msg.data?.data?.files ?? {})
const testResults = computed(() => props.msg.data?.data?.test_results ?? [])
const reviewComments = computed(() => props.msg.data?.data?.review_comments ?? [])
const keyDecisions = computed(() => props.msg.data?.data?.key_decisions ?? [])
```
万一后端某个 Agent 分支返回格式变了，前端不会白屏。

### 4.2 Agent 卡片可交互

**AgentCard 改造：**
- 点击展开/折叠详情区域
- 详情区显示该 Agent 最近一次执行的摘要
- 执行中显示耗时（从 `agent_start` 到 `agent_done` 计时）
- 用 `v-model` 控制展开状态

**计时实现：** project store 新增 `agentStartTime: {}` 记录每个 Agent 的开始时间。

### 4.3 进度可视化

**IterationInfo 改造：**
- 进度条加粗（4px → 8px）
- 接近上限时变色：
  - <50%：绿色 #4caf50
  - 50-80%：黄色 #ff9800
  - >80%：红色 #f44336
- 当前执行的 Agent 卡片加脉冲动画

### 4.4 代码文件预览

**OutputPanel 改造：**
- 点击文件名展开内联预览
- 预览区最大高度 400px，可滚动
- 复制按钮（navigator.clipboard.writeText）
- 再次点击折叠预览

**语法高亮：** 使用 highlight.js（轻量，~40KB gzip）。在 composable 中根据文件扩展名检测语言：

```js
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import javascript from 'highlight.js/lib/languages/javascript'
import css from 'highlight.js/lib/languages/css'
import xml from 'highlight.js/lib/languages/xml'
import json from 'highlight.js/lib/languages/json'

hljs.registerLanguage('python', python)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('css', css)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('json', json)

const LANG_MAP = { '.py': 'python', '.js': 'javascript', '.css': 'css', '.html': 'html', '.json': 'json' }

export function useFilePreview() {
  const previewFile = ref(null)
  const previewContent = ref('')
  const highlightedContent = ref('')

  function openPreview(path, content) {
    previewFile.value = path
    previewContent.value = content
    const ext = '.' + path.split('.').pop()
    const lang = LANG_MAP[ext]
    if (lang) {
      highlightedContent.value = hljs.highlight(content, { language: lang }).value
    } else {
      highlightedContent.value = hljs.highlightAuto(content).value
    }
  }
  function closePreview() {
    previewFile.value = null
    previewContent.value = ''
    highlightedContent.value = ''
  }
  async function copyContent() {
    await navigator.clipboard.writeText(previewContent.value)
  }

  return { previewFile, previewContent, highlightedContent, openPreview, closePreview, copyContent }
}
```

预览区使用 `<code>` + `v-html` 渲染高亮内容，配合 highlight.js CSS 主题。

### 4.5 保存命名弹窗

**SaveDialog.vue：**
- Props: `visible`（v-model）、`defaultName`（自动命名）
- 自动填入需求前 20 字，超过 20 字加 "..."
- 输入框可编辑，最大 50 字
- 确认后 emit `save(name)`
- 取消后 emit `update:visible` = false
- 保存成功后 router.push 到 `/projects/{id}`

**自动命名逻辑：**
```js
function autoGenerateName(requirement) {
  if (!requirement) return '未命名项目'
  // 中文取前 15 字，英文取前 30 字符
  const isChinese = /[一-鿿]/.test(requirement)
  const maxLen = isChinese ? 15 : 30
  if (requirement.length <= maxLen) return requirement
  return requirement.slice(0, maxLen) + '...'
}
```
示例：
- "做一个web应用能加减乘除的计算器,紫色样式" → "做一个web应用能加减乘除的计..."
- "Build a calculator web app with purple theme" → "Build a calculator web app with..."

### 4.6 暂停/继续

**ChatHeader 根据状态显示不同按钮：**

| 状态 | 按钮 |
|------|------|
| 运行中 | ⏸ 暂停 · 💾 保存 · 🗑️ · ✚ |
| 已暂停 | ▶ 继续 · ⏹ 停止 · 💾 保存 |
| 空闲 | 💾 保存 · 🗑️ · ✚ |

**暂停 vs 停止：**
- 暂停：保留当前状态，可继续执行
- 停止：取消任务，不可恢复

### 4.7 异常状态处理

| 异常场景 | 处理方式 |
|----------|---------|
| WebSocket 断连 | ChatHeader 显示"连接断开"提示，暂停/继续按钮禁用，自动重连后恢复 |
| 保存失败（网络错误） | SaveDialog 内显示红色错误提示，不关闭弹窗，可重试 |
| 保存失败（后端报错） | 同上，显示后端返回的错误信息 |
| 文件预览内容为空 | 显示"文件内容为空"占位符 |
| 文件预览加载失败 | 显示"无法加载文件内容"占位符 + 重试按钮 |
| Agent 执行超时 | 前端 120 秒无 agent_update → 显示"Agent 响应超时"提示，暂停按钮可用 |
| 项目状态恢复失败 | ProjectsPage 显示"加载失败" + 重试按钮，不崩溃 |

## 五、后端详细设计

### 5.1 暂停/停止/恢复机制

**核心思路：** 利用现有的 `stop_event`（per-connection 的 `threading.Event`）控制 graph 执行。graph 在每个节点完成后检查 `stop_event`，发现已设则暂停。

#### websocket.py 改动

**新增共享状态：**
```python
# ws_project 函数内，现有变量旁边新增：
paused = False  # 是否处于暂停状态
```

**处理 pause 消息：**
```python
elif msg_type == "pause":
    stop_event.set()
    paused = True
    await websocket.send_json({"type": "paused", "project_id": project_id})
    # 启动心跳任务，保存引用方便 stop 时取消
    heartbeat_task = asyncio.create_task(_send_heartbeat(websocket, project_id, lambda: paused))
```

**处理 resume_execution 消息：**
```python
elif msg_type == "resume_execution":
    stop_event.clear()
    paused = False
    await websocket.send_json({"type": "resumed", "project_id": project_id})
```

**处理 stop 消息：**
```python
elif msg_type == "stop":
    stop_event.set()
    paused = False
    cancelled = True
    # 取消心跳任务
    if heartbeat_task and not heartbeat_task.done():
        heartbeat_task.cancel()
    if drainer_task and not drainer_task.done():
        drainer_task.cancel()
    await websocket.send_json({
        "type": "stopped", "project_id": project_id,
        "data": {"status": "stopped", "current_agent": "done"}
    })
```

**心跳函数：**
```python
async def _send_heartbeat(ws, project_id, is_paused_fn):
    """暂停期间每 10 秒发心跳，保持 WebSocket 连接。"""
    while is_paused_fn():
        try:
            await asyncio.sleep(10)
            if is_paused_fn():
                await ws.send_json({"type": "heartbeat", "project_id": project_id})
        except Exception:
            break
```

#### _run_graph_sync 改动

**节点边界检查 stop_event：** 在 `_run_async` 的 `async for event in app.astream(...)` 循环体内，每个节点输出处理完后检查：

```python
async for event in app.astream(input_data, config=config):
    for node_name, node_output in event.items():
        # ... 现有的消息发送逻辑 ...

    # 节点边界：检查是否需要暂停
    if stop_event.is_set():
        _put({"type": "paused", "project_id": project_id})
        # 等待 stop_event 被清除（用户点继续）
        while stop_event.is_set():
            await _asyncio.sleep(0.5)
        _put({"type": "resumed", "project_id": project_id})
```

**关键：** 暂停时 graph 线程阻塞在 `while stop_event.is_set()` 循环中，不消耗 CPU。恢复后从下一个节点继续执行，不丢失状态。

**async/sync 说明：** `_run_graph_sync` 是 sync 函数（在线程中运行），但它内部调用 `_asyncio.run(_run_async())` 创建了独立的 event loop。`_run_async` 是 async 函数，可以正常使用 `await asyncio.sleep(0.5)`。`stop_event` 是 `threading.Event`，但 `stop_event.is_set()` 是同步调用，在 async 上下文中安全使用。

#### 状态机

```
          pause                resume
RUNNING -------> PAUSED -------> RUNNING
   |                               |
   | stop                    stop  |
   v                               v
STOPPED <------------------------ STOPPED
```

### 5.2 保存命名 API

#### POST /api/projects 请求格式

```json
{
  "requirement": "做一个web应用能加减乘除的计算器",
  "project_id": "proj-1781140380176",
  "name": "紫色计算器 Web 应用"
}
```

**字段说明：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| requirement | string | 是 | 原始需求文本 |
| project_id | string | 否 | 已有项目 ID（upsert 时传） |
| name | string | 否 | 项目名称（前端命名弹窗提供），最大 50 字 |

**校验规则：**
- `name` 最大 50 字，超过截断
- `name` 为空时自动从 `requirement` 生成（中文前 15 字 / 英文前 30 字符 + "..."）
- `project_id` 格式校验（`^[a-zA-Z0-9_-]+$`）

#### meta.json 结构（更新后）

```json
{
  "project_id": "proj-1781140380176",
  "name": "紫色计算器 Web 应用",
  "requirement": "做一个web应用能加减乘除的计算器,紫色样式",
  "status": "delivered",
  "iteration": 3,
  "created_at": "2026-06-11T19:30:00"
}
```

#### GET /api/projects 返回格式（更新后）

```json
[
  {
    "project_id": "proj-1781140380176",
    "name": "紫色计算器 Web 应用",
    "requirement": "做一个web应用能加减乘除的计算器,紫色样式",
    "status": "delivered",
    "iteration": 3
  }
]
```

**改动点：** 返回结果新增 `name` 字段。ProjectsPage 优先显示 `name`，无 `name` 时 fallback 到 `requirement`。

### 5.3 Agent 输出数据结构

**目标：** 让前端 AgentOutputCard 能拿到结构化数据，而不是只有纯文本消息。

**现状：** websocket.py 发送 `agent_update` 时，`data` 是节点的完整返回值。各 Agent 返回的字段不同。

**改动：** 在 `_run_graph_sync` 的 `agent_update` 消息中，确保包含前端需要的结构化字段。

#### Developer 的 agent_update

```python
# 现有代码（_run_graph_sync 第 143 行附近）
_put({"type": "agent_update", "project_id": project_id, "agent": node_name, "data": node_output})
```

`node_output` 已经包含 `files`、`key_decisions`、`test_passed`、`error`。**无需改动**，数据已存在。

#### Tester 的 agent_update

`node_output` 已经包含 `test_passed`、`test_results`、`error`。**无需改动**。

#### Reviewer 的 agent_update

`node_output` 已经包含 `review_approved`、`review_comments`、`error`。**无需改动**。

#### PM 和 Architect 的 agent_update

`node_output` 包含 `user_stories`、`features`、`architecture`、`api_definitions`、`data_models`。**无需改动**。

**结论：** Agent 输出数据结构不需要后端改动。现有 `agent_update` 消息已经包含所有需要的字段。前端 AgentOutputCard 直接从 `data.data` 提取即可。

**但需要一个改动：** 确保 `agent_update` 消息在 Agent 执行完成后才发送（不是在执行开始时）。当前代码已经这样做了（先执行完节点，再发消息），所以**后端无需额外改动**。

### 5.4 后端改动汇总

| 文件 | 改动 | 复杂度 |
|------|------|--------|
| websocket.py | 新增 pause/resume_execution/stop 消息处理 + 心跳 + 节点边界检查 | 中 |
| websocket.py | 新增 `_send_heartbeat` 函数 | 低 |
| projects.py | POST 新增 name 字段 + 校验 | 低 |
| projects.py | GET 返回 name 字段 | 低 |
| memory.py | save_snapshot 支持 name 字段 | 低 |
| Agent 输出数据 | 无需改动 | 无 |

## 六、测试策略

| 测试类型 | 覆盖内容 |
|----------|---------|
| 前端组件测试 | SaveDialog 渲染/交互/错误提示、AgentOutputCard 各 Agent 类型 + 兜底逻辑、ChatHeader 状态切换 |
| 前端 composable 测试 | useFilePreview 打开/关闭/复制/语法高亮/空文件/加载失败 |
| 后端测试 | pause/stop/resume WebSocket 消息处理、name 字段存取、stop_event 行为 |
| 集成测试 | 完整流程：发送需求 → Agent 执行 → 暂停 → 继续 → 保存（命名）→ 项目列表显示 |
| 异常测试 | WebSocket 断连恢复、保存失败重试、文件预览失败兜底 |

## 七、依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| highlight.js | ^11.x | 代码语法高亮（~40KB gzip） |

## 八、实施顺序

优化后的 Task 顺序（可并行的标注 `||`）：

| Task | 内容 | 依赖 |
|------|------|------|
| 1 || useFilePreview composable（含 highlight.js） | 无 |
| 2 || AgentOutputCard 组件 | 无 |
| 3 || SaveDialog 组件 | 无 |
| 4 || AgentCard 可交互 | 无 |
| 5 || IterationInfo 进度可视化 | 无 |
| 6 || 后端 WebSocket pause/stop/resume 处理 | 无 |
| 7 | ChatPanel 拆分 + 暂停/停止/继续（ChatHeader + MessageList + ChatInput） | Task 2, 3 |
| 8 | 保存命名（前端 + 后端 name 字段） | Task 3, 7 |
| 9 | OutputPanel 文件预览 | Task 1 |
| 10 | 异常状态处理（各组件兜底） | Task 1-9 |
| 11 | 集成测试 | Task 1-10 |

**说明：** Task 1-6 无依赖，可以完全并行开发。Task 7（ChatPanel 拆分 + 暂停 UI）依赖 Task 2（AgentOutputCard）和 Task 3（SaveDialog）。Task 6（后端 WebSocket）标注 `||`，和前端 Task 1-5 同步进行。
