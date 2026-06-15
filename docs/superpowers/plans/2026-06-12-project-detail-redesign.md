# 项目详情页重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 存储完整 Agent 对话历史 + 项目详情页卡片布局 + 操作按钮（重新运行/编辑需求/导出）

**Architecture:** 三层存储（精简摘要/结构化摘要/完整对话），API 懒加载（/state 轻量 + /conversations + /executions 按需），前端卡片布局 + Pinia 跨页传参

**Tech Stack:** SQLite + FastAPI + Vue 3 + Pinia + JSZip

---

## 文件结构

### 新增文件

无

### 修改文件

| 文件 | 改动 |
|------|------|
| `devteam/utils/memory.py` | 新增 `agent_conversations` 表 + `save_conversation()` / `get_conversations()`；`save_execution` 新增 `tool_calls` 参数 |
| `devteam/api/websocket.py` | 存完整对话到 `agent_conversations`（过滤 system，BaseMessage→dict）；`save_execution` 传 tool_calls |
| `devteam/api/projects.py` | `GET /state` 返回 name；新增 `GET /conversations`、`GET /executions`、`GET /export` |
| `frontend/src/pages/ProjectDetailPage.vue` | 重写为卡片布局 + 懒加载 + 操作按钮 |
| `frontend/src/stores/project.js` | 新增 `pendingRequirement` 字段 |
| `frontend/src/components/ChatPanel.vue` | onMounted 检查 `pendingRequirement` 并自动发送 |
| `frontend/src/api/index.js` | 新增 API 方法 |

---

### Task 1: memory.py — agent_conversations 表 + save_execution tool_calls

**Files:**
- Modify: `devteam/utils/memory.py`
- Modify: `devteam/tests/test_memory.py`

- [ ] **Step 1: 写失败测试**

```python
# devteam/tests/test_memory.py — 新增测试

def test_save_and_get_conversation(memory_instance):
    """save_conversation 存入对话，get_conversations 读出"""
    mem = memory_instance
    mem.save_conversation("proj-1", "developer", 1, [
        {"role": "assistant", "content": "写入 main.py"},
        {"role": "tool", "content": '{"success": true}'}
    ])
    convs = mem.get_conversations("proj-1")
    assert len(convs) == 1
    assert convs[0]["agent_name"] == "developer"
    assert convs[0]["iteration"] == 1
    msgs = json.loads(convs[0]["messages"])
    assert len(msgs) == 2
    assert msgs[0]["role"] == "assistant"

def test_get_conversations_empty(memory_instance):
    """无对话时返回空列表"""
    mem = memory_instance
    convs = mem.get_conversations("nonexistent")
    assert convs == []

def test_save_execution_with_tool_calls(memory_instance):
    """save_execution 可存 tool_calls 字段"""
    mem = memory_instance
    mem.save_execution("proj-1", "developer", 1, "写入 3 个文件", "success",
                       tool_calls='[{"name": "file_write", "args_summary": "main.py"}]')
    execs = mem.get_executions("proj-1")
    assert len(execs) == 1
    assert execs[0]["tool_calls"] is not None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "c:\Users\lahm\Desktop\Many AgentS" && python -m pytest devteam/tests/test_memory.py -v
```

- [ ] **Step 3: 实现**

在 `memory.py` 中：

1. `_init_db` 新增 `agent_conversations` 表（CREATE TABLE IF NOT EXISTS）
2. 新增 `save_conversation(project_id, agent_name, iteration, messages_list)` 方法 — `messages_list` 是 list[dict]，`json.dumps` 存入
3. 新增 `get_conversations(project_id)` 方法 — 返回 `[{agent_name, iteration, messages(str), created_at}]`，按 `created_at ASC` 排序（前端按时间正序展示）
4. 修改 `save_execution` — 新增 `tool_calls` 可选参数，存入 `agent_executions.tool_calls` 列
5. 新增 `get_executions(project_id)` 方法 — 返回 `[{agent_name, iteration, result_summary, tool_calls, status, created_at}]`，按 `created_at ASC` 排序

- [ ] **Step 4: 运行测试确认通过**

```bash
cd "c:\Users\lahm\Desktop\Many AgentS" && python -m pytest devteam/tests/test_memory.py -v
```

- [ ] **Step 5: 运行全量测试**

```bash
cd "c:\Users\lahm\Desktop\Many AgentS" && python -m pytest devteam/tests/ -q
```

- [ ] **Step 6: 提交**

```bash
git add devteam/utils/memory.py devteam/tests/test_memory.py
git commit -m "feat: add agent_conversations table + tool_calls in save_execution"
```

---

### Task 2: websocket.py — 存完整对话 + tool_calls

**Files:**
- Modify: `devteam/api/websocket.py`

- [ ] **Step 1: 修改消息存储逻辑**

在 `_run_graph_sync` 的 Agent 完成处理中：

1. BaseMessage→dict 转换：`dict_msgs = [m.dict() if hasattr(m, 'dict') else m for m in raw_msgs]`
2. 过滤 system 消息存入 `agent_conversations`：`filtered = [m for m in dict_msgs if m.get("role") in ("assistant", "tool")]`
3. 从 messages 提取 tool_calls：遍历 dict_msgs，收集所有 `m.get("tool_calls")`
4. `save_execution` 传入 tool_calls_json

- [ ] **Step 2: 运行后端测试**

```bash
cd "c:\Users\lahm\Desktop\Many AgentS" && python -m pytest devteam/tests/ -q
```

- [ ] **Step 3: 提交**

```bash
git add devteam/api/websocket.py
git commit -m "feat: save full conversations + tool_calls to memory"
```

---

### Task 3: projects.py — 新增 API 端点

**Files:**
- Modify: `devteam/api/projects.py`

- [ ] **Step 1: 修改 GET /state 返回 name**

在 `get_project_state` 返回值中新增 `name` 字段（从 meta.json 读取，可能为 None）。

- [ ] **Step 2: 新增 GET /conversations**

```python
@router.get("/projects/{project_id}/conversations")
def get_project_conversations(project_id: str):
    _validate_project_id(project_id)
    mem = get_memory()
    convs = mem.get_conversations(project_id)
    # 解析 messages JSON string 为 list
    for c in convs:
        if isinstance(c.get("messages"), str):
            c["messages"] = json.loads(c["messages"])
    return {"conversations": convs}
```

- [ ] **Step 3: 新增 GET /executions**

```python
@router.get("/projects/{project_id}/executions")
def get_project_executions(project_id: str):
    _validate_project_id(project_id)
    mem = get_memory()
    execs = mem.get_executions(project_id)
    # tool_calls 是 JSON string，parse 为 list 给前端
    for e in execs:
        tc = e.get("tool_calls")
        if isinstance(tc, str):
            try:
                e["tool_calls"] = json.loads(tc)
            except json.JSONDecodeError:
                e["tool_calls"] = []
    return {"executions": execs}
```

- [ ] **Step 4: 新增 GET /export**

```python
@router.get("/projects/{project_id}/export")
def export_project(project_id: str):
    _validate_project_id(project_id)
    pdir = _project_dir(project_id)
    if not pdir.exists():
        raise HTTPException(404, "Project not found")

    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    buf = io.BytesIO()
    skipped = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 项目文件（用 read_bytes 兼容二进制）
        for fpath in sorted(pdir.rglob("*")):
            if fpath.is_file():
                if fpath.stat().st_size > MAX_FILE_SIZE:
                    skipped.append(str(fpath.relative_to(pdir)))
                    continue
                zf.write(fpath, fpath.relative_to(pdir))
        # 跳过的文件列表
        if skipped:
            zf.writestr("skipped_files.txt", "\n".join(skipped))
        # 元数据
        meta = _read_meta(project_id)
        zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
        # 对话历史
        mem = get_memory()
        convs = mem.get_conversations(project_id)
        for c in convs:
            if isinstance(c.get("messages"), str):
                c["messages"] = json.loads(c["messages"])
        zf.writestr("conversations.json", json.dumps(convs, ensure_ascii=False, indent=2))
        # 执行摘要
        execs = mem.get_executions(project_id)
        zf.writestr("executions.json", json.dumps(execs, ensure_ascii=False, indent=2))

    buf.seek(0)
    content = buf.getvalue()
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{project_id}.zip"',
            "Content-Length": str(len(content)),
        },
    )
```

- [ ] **Step 5: 写新端点测试**

```python
# devteam/tests/test_file_api.py — 新增

def test_get_conversations(client, tmp_projects):
    """GET /api/projects/{id}/conversations 返回对话历史"""
    _create_project(tmp_projects, "conv-proj")
    resp = client.get("/api/projects/conv-proj/conversations")
    assert resp.status_code == 200
    assert "conversations" in resp.json()

def test_get_executions(client, tmp_projects):
    """GET /api/projects/{id}/executions 返回执行摘要"""
    _create_project(tmp_projects, "exec-proj")
    resp = client.get("/api/projects/exec-proj/executions")
    assert resp.status_code == 200
    assert "executions" in resp.json()

def test_export_project(client, tmp_projects):
    """GET /api/projects/{id}/export 返回 zip 文件"""
    _create_project(tmp_projects, "export-proj")
    resp = client.get("/api/projects/export-proj/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"

def test_get_state_returns_name(client, tmp_projects):
    """GET /api/projects/{id}/state 返回 name 字段"""
    _create_project(tmp_projects, "name-proj")
    resp = client.get("/api/projects/name-proj/state")
    assert resp.status_code == 200
    assert "name" in resp.json()
```

- [ ] **Step 6: 运行全部后端测试**

```bash
cd "c:\Users\lahm\Desktop\Many AgentS" && python -m pytest devteam/tests/ -q
```

- [ ] **Step 7: 提交**

```bash
git add devteam/api/projects.py devteam/tests/test_file_api.py
git commit -m "feat: add /conversations, /executions, /export endpoints + name in /state"
```

---

### Task 4: 前端 API 方法 + store 字段

**Files:**
- Modify: `frontend/src/api/index.js`
- Modify: `frontend/src/stores/project.js`

- [ ] **Step 1: api/index.js 新增方法**

```js
export const api = {
  // ... 现有方法 ...
  getProjectConversations: (id) => request(`/projects/${id}/conversations`),
  getProjectExecutions: (id) => request(`/projects/${id}/executions`),
  exportProject: (id) => `/api/projects/${id}/export`,  // 返回 URL，前端用 window.open
}
```

- [ ] **Step 2: project.js 新增 pendingRequirement**

```js
state: () => ({
  // ... 现有字段 ...
  pendingRequirement: null,  // 跨页传参：重新运行/编辑需求
})
```

在 `reset()` 中加 `this.pendingRequirement = null`。

在 ProjectDetailPage 设置 pendingRequirement 时，同时存 sessionStorage 兜底（防刷新丢失）：
```js
projectStore.pendingRequirement = req
sessionStorage.setItem('pendingRequirement', req)
```

在 ChatPanel onMounted 读取时，先检查 store，再检查 sessionStorage：
```js
const req = projectStore.pendingRequirement || sessionStorage.getItem('pendingRequirement')
if (req) {
  projectStore.pendingRequirement = null
  sessionStorage.removeItem('pendingRequirement')
  inputText.value = req
  nextTick(() => sendMessage())
}
```

- [ ] **Step 3: 运行前端测试**

```bash
cd frontend && npx vitest run
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/index.js frontend/src/stores/project.js
git commit -m "feat: add conversation/execution/export API methods + pendingRequirement store"
```

---

### Task 5: ProjectDetailPage 重写

**Files:**
- Modify: `frontend/src/pages/ProjectDetailPage.vue`

- [ ] **Step 1: 重写为卡片布局**

页面结构：
- 操作栏：返回按钮 + 项目名称 + 🔄 重新运行 + ✏️ 编辑需求 + 📤 导出
- 卡片 1：📋 项目信息（名称、时间、状态、迭代、需求）— 立即加载
- 卡片 2：📁 生成文件（文件列表 + 预览）— 立即加载
- 卡片 3：💬 开发日志（展开时懒加载 GET /conversations）
- 卡片 4：📊 执行摘要（展开时懒加载 GET /executions）

每个卡片可折叠。懒加载用 `loaded` 标记 + `v-if`，展开时检查是否已加载，已加载不重复请求。Loading 用骨架屏，Error 用红色提示+重试，Empty 用"暂无数据"。旧项目无 conversations 数据时显示"暂无历史对话数据"。

- [ ] **Step 2: 实现操作按钮**

- 🔄 重新运行：确认弹窗 → `projectStore.pendingRequirement = requirement` → `router.push('/')`
- ✏️ 编辑需求：弹窗（textarea 预填需求）→ 确认 → `projectStore.pendingRequirement = editedText` → `router.push('/')`
- 📤 导出：`window.open(api.exportProject(projectId))`

- [ ] **Step 3: 运行前端测试**

```bash
cd frontend && npx vitest run
```

- [ ] **Step 4: 构建**

```bash
cd frontend && npm run build
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/ProjectDetailPage.vue
git commit -m "feat: rewrite ProjectDetailPage with card layout, lazy loading, and action buttons"
```

---

### Task 6: ChatPanel pendingRequirement 自动发送

**Files:**
- Modify: `frontend/src/components/ChatPanel.vue`

- [ ] **Step 1: onMounted 检查 pendingRequirement**

在 WorkbenchPage 中，通过 store 传递需求到 ChatPanel。ChatPanel 的 `sendMessage` 从 `projectStore.pendingRequirement` 读取并自动发送：

```vue
<!-- WorkbenchPage.vue -->
<script setup>
import { onMounted } from 'vue'
import { useProjectStore } from '../stores/project.js'
import FlowPanel from '../components/FlowPanel.vue'
import ChatPanel from '../components/ChatPanel.vue'

const projectStore = useProjectStore()

// 不需要额外逻辑 — ChatPanel 自己检查 pendingRequirement
</script>
```

在 ChatPanel.vue 的 `onMounted` 中加：

```js
onMounted(() => {
  if (projectStore.pendingRequirement) {
    const req = projectStore.pendingRequirement
    projectStore.pendingRequirement = null
    inputText.value = req
    nextTick(() => sendMessage())
  }
})
```

这样 WorkbenchPage 不需要改动，逻辑全在 ChatPanel 内部。

- [ ] **Step 2: 运行前端测试**

```bash
cd frontend && npx vitest run
```

- [ ] **Step 3: 构建 + 提交**

```bash
cd frontend && npm run build
git add frontend/src/components/ChatPanel.vue
git commit -m "feat: auto-send pending requirement from project detail page"
```

---

### Task 7: 集成测试

- [ ] **Step 1: 启动手动测试**

```bash
cd "c:\Users\lahm\Desktop\Many AgentS" && python -m devteam.start
```

测试清单：
1. 运行一个项目 → 保存 → 打开项目详情页
2. 项目信息卡片显示名称、时间、状态
3. 文件卡片显示生成的文件 + 预览
4. 展开"开发日志"→ 懒加载完整对话
5. 展开"执行摘要"→ 懒加载结构化摘要
6. 点击"重新运行"→ 确认弹窗 → 跳转工作台 → 自动发送需求
7. 点击"导出"→ 下载 zip 包 → 解压验证内容
8. 刷新页面 → 消息完整恢复

- [ ] **Step 2: 运行全量测试**

```bash
cd "c:\Users\lahm\Desktop\Many AgentS" && python -m pytest devteam/tests/ -q
cd frontend && npx vitest run
```

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "feat: project detail page redesign with 3-layer storage and card layout"
```

---

## 实现注意事项

### 🔴 必须处理

**#1 sendMessage 读 inputText.value** — 已确认，`inputText.value = req` + `sendMessage()` 可行。无需改。

**#2 tool_calls JSON string 解析** — Task 3 的 GET /executions 端点已加 `json.loads`。GET /conversations 的 messages 也已在端点内 parse。前端拿到的都是已解析的数组/对象。

### 🟡 体验优化

**#3 项目 ID 格式** — 当前两种格式混用（`uuid[:12]` 和 `proj-{timestamp}`）。统一用 `proj-{timestamp}` 即可，前端生成的 ID 就是这个格式，后端 `create_project` 接受任意 `project_id`。不改。

**#4 pendingRequirement 刷新丢失** — 低概率。在 project.js 的 `saveProject` 里同时存 `sessionStorage.setItem('pendingRequirement', req)` 兜底。ChatPanel onMounted 先检查 store，再检查 sessionStorage。

**#6 懒加载机制** — 用 `loaded` 标记 + `v-if`：
```js
const conversationsLoaded = ref(false)
const conversations = ref([])

async function toggleConversations() {
  if (!conversationsLoaded.value) {
    conversations.value = await api.getProjectConversations(id)
    conversationsLoaded.value = true
  }
}
```
展开时检查 `loaded`，已加载不重复请求。折叠后再展开用缓存。

### 🟢 边缘处理

**#5 导出文件大小** — `GET /export` 跳过超过 5MB 的单文件，zip 内加 `skipped_files.txt` 说明。

**#7 旧项目兼容** — 旧项目无 `agent_conversations` 数据，"开发日志"卡片显示"暂无历史对话数据"。

**#8 排序方向** — `get_conversations` 和 `get_executions` 用 `ORDER BY created_at ASC`（正序）。前端按时间顺序展示（PM → Architect → Developer → Tester → Reviewer）。

**#9 并发写入** — 当前已有 `save_execution` 并发写入，加 `save_conversation` 不改变并发模式。SQLite WAL 模式 + `threading.local()` 连接，两个项目同时跑不会锁死。无需改动。
