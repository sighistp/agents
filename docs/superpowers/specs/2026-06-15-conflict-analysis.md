# Blueprint — 冲突分析与规避方案

> **日期:** 2026-06-15
> **原则:** 核心链路（PM→Architect→Developer→Tester→Reviewer）不动，所有新功能追加式实现

---

## 1. 核心原则

**链路设计是根基。** 只要 LangGraph 图结构、Agent 返回值、State 字段、WebSocket 消息协议这四层不变，整个软件就不会出大问题。所有新功能都是在链路**外围**加模块，不触碰链路内部。

```
                    ┌─────────────────────────────────┐
                    │     核心链路（不动）              │
                    │  PM → Architect → human_confirm  │
                    │  → Developer → Tester → Reviewer │
                    │  → Deliver → END                 │
                    └─────────────────────────────────┘
                              ↑ 不触碰
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────┴────┐          ┌────┴────┐          ┌────┴────┐
   │ 质量评分 │          │ 安全扫描 │          │ 文档生成 │
   │ 变更对比 │          │ 知识库   │          │ 部署配置 │
   │ 思考可视化│         │ Webhook  │          │ 模板市场 │
   └─────────┘          └─────────┘          └─────────┘
        追加式模块，通过 API 层或 deliver_node 扩展
```

---

## 2. 冲突清单与规避方案

### P0 — 必须处理（否则必出 Bug）

#### 冲突 1：ProjectState 字段缺失 → LangGraph 静默丢弃

**根因：** LangGraph 严格按 TypedDict schema 合并 Agent 返回值，未声明的字段会被丢弃。

**影响：** 新功能想在 Agent 间传递数据（如安全扫描结果、质量评分），如果不加字段 → 数据丢失。

**规避方案：**

```python
# state.py — 扩展字段（不影响现有字段）
class ProjectState(TypedDict):
    # ... 现有 30+ 字段不变 ...

    # ── Blueprint 扩展字段 ──
    quality_score: dict          # {total, dimensions, grade, suggestions}
    security_issues: list[dict]  # [{file, line, severity, description}]
    deploy_files: dict[str, str] # {Dockerfile: "...", "docker-compose.yml": "..."}
    documentation: dict          # {readme, api_docs, architecture}
    agent_traces: list[dict]     # [{agent, prompt, response, tools_called, duration_ms}]
```

**实施顺序：** 改 state.py → 改 create_initial_state 加默认值 → 再实现功能

---

#### 冲突 2：deliver_node 路径冲突 → 快照/文档/部署文件混入项目目录

**根因：** deliver_node 将所有文件写入 `projects/{project_id}/`，新功能的文件也会写到这里。

**影响：**
- DiffEngine 的 `.snapshots/` 目录在项目内 → Developer 的 file_write 可能误读
- 文档生成的 README.md 覆盖 Developer 已写的 README.md
- 部署配置与源码混在一起

**规避方案：**

| 文件类型 | 存储位置 | 说明 |
|----------|---------|------|
| Developer 生成的代码 | `projects/{id}/` | 不变 |
| 快照数据 | `blueprint/data/snapshots/{id}/` | **项目外部**，不污染项目 |
| 质量评分 | `blueprint/data/scores/{id}.json` | 独立文件，deliver 后缓存 |
| 安全扫描 | `blueprint/data/security/{id}.json` | 独立文件，deliver 后缓存 |
| 文档/部署配置 | `projects/{id}/_blueprint/` | 下划线前缀，前端过滤 |
| Agent Trace | `blueprint/data/traces/{id}/` | 独立目录 |

**deliver_node 改动（hook 链模式）：**

```python
def deliver_node(state):
    # ... 现有逻辑不变（写 Developer 生成的文件 + meta.json） ...

    # hook 链：每个功能是独立函数，按顺序执行，失败不影响交付
    hooks = [
        save_snapshot_hook,      # 保存快照（到项目外部目录）
        quality_score_hook,      # 计算质量评分并缓存
        security_scan_hook,      # 执行安全扫描并缓存
        generate_docs_hook,      # 生成文档（到 _blueprint/ 子目录）
        generate_deploy_hook,    # 生成部署配置（到 _blueprint/ 子目录）
    ]
    for hook in hooks:
        try:
            hook(state, project_dir)
        except Exception as e:
            logger.warning(f"Hook {hook.__name__} failed: {e}")

    return { ... }  # 返回值不变
```

**回归测试：** 追加 hook 后必须验证返回值结构不变（status/files/current_agent/messages 字段）。

---

#### 冲突 3：tool_executor 路径安全 → 知识库/模板无法通过工具访问

**根因：** `_resolve_safe_path` 阻止访问 `data/`、`.git/` 等目录。

**影响：** Agent 如果想用 file_read 读知识库文件 → 被阻止。

**规避方案：** 知识库和模板**不走 Agent 工具**，走后端 API 层。

```
知识库注入路径：
  用户上传文档 → API /api/knowledge/upload → 存入 ChromaDB
  Developer Agent 启动 → 后端代码调用 KnowledgeBase.get_context()
  → 将相关文档拼入 Developer 的 prompt → Developer 不知道知识库存在

模板使用路径：
  用户选择模板 → API /api/templates/:id → 返回模板文件内容
  → 后端将模板内容写入项目目录 → Developer 在已有代码基础上继续开发
```

**结论：** tool_executor 的路径安全逻辑**完全不动**，新功能绕过工具层。

---

### P1 — 需要适配（否则功能异常）

#### 冲突 4：WebSocket 消息协议 → 新消息类型前后端必须同步

**根因：** 前端 `useWebSocket.js` 按 `type` 字段分发处理，未知类型被忽略。

**规避方案：** 允许新增消息类型，但前端必须同步注册 handler。

| 新数据 | 消息类型 | 前端处理 |
|--------|---------|---------|
| 质量评分 | `quality_score`（新增） | messageHandlers 新增 |
| 安全扫描 | `security_scan`（新增） | messageHandlers 新增 |
| Agent Trace | 附在 `agent_update.data.traces` | 现有 handler 扩展 |

**规则：** 新消息类型必须在 `useWebSocket.js` 的 `messageHandlers` 中注册，否则前端静默丢弃。

---

#### 冲突 5：deliver_node 返回值 → 前端文件预览/下载依赖

**根因：** 前端 `OutputPanel.vue` 解析 `project_done.data.files` 渲染文件列表。

**规避方案：** 新交付物用 `_blueprint/` 前缀，前端过滤：

```javascript
// OutputPanel.vue — 过滤逻辑
const sourceFiles = Object.entries(files).filter(
  ([path]) => !path.startsWith('_blueprint/')
)
const blueprintFiles = Object.entries(files).filter(
  ([path]) => path.startsWith('_blueprint/')
)
```

前端显示：源码文件 + 「查看文档/部署配置」折叠区域（只显示 `_blueprint/` 下的文件）。

---

#### 冲突 6：_extract_agent_summary 硬编码

**根因：** `websocket.py` 只处理 5 种 node_name。

**规避方案：** 新功能不新增 Agent 节点。质量评分、安全扫描、文档生成都在 `deliver_node` 的 hook 链中执行（或通过 API 按需调用），不经过 Agent 链路。

```
现有链路：PM → Architect → Developer → Tester → Reviewer → Deliver
                                                    ↓
                                          deliver_node 内部追加：
                                          1. 质量评分
                                          2. 安全扫描
                                          3. 文档生成
                                          4. 部署配置生成
                                          5. 快照保存
```

---

#### 冲突 7：memory.save_execution 调用时机

**根因：** `websocket.py` 在 Agent 节点完成后调用 `save_execution`，数据来自 `node_output`。

**规避方案：** Agent Trace 在 Agent 内部直接写入独立 SQLite 表，不通过 memory.save_execution：

```python
# developer.py — 在工具循环中记录 trace
async def developer_agent(state):
    # ... 现有逻辑 ...
    
    # 记录 trace（失败不影响主流程）
    try:
        trace_db = TraceDB(state["project_id"])
        trace_db.save(
            agent="developer",
            iteration=state.get("iteration", 0),
            prompt=messages[1]["content"],  # user message
            response=messages[-1].get("content", ""),
            tools_called=[serialize_call(tc) for tc in all_tool_calls],
            duration_ms=elapsed,
        )
    except Exception:
        pass
    
    return { ... }  # 返回值不变
```

---

### P2 — 低风险（可安全添加）

#### 冲突 8：API 端点命名

**结论：** 所有新端点命名安全，不与现有冲突。

#### 冲突 9：前端组件

**结论：** 新组件全部是独立文件，唯一例外是 ProjectDetailPage 拆分（高风险重构，先写测试）。

#### 冲突 10：配置系统

**结论：** 新配置写入 `data/settings.json` 或用新 env_prefix，不与现有冲突。

---

## 3. 实施安全守则

### 必须遵守

1. **改 state.py 前先看 graph.py** — 确认新字段在链路中不会被误用
2. **deliver_node 只追加，不修改** — 不改现有返回值结构，只在内部追加逻辑
3. **新文件用独立目录** — 快照、评分、扫描结果、trace 都不写入项目目录
4. **WebSocket 不新增消息类型** — 新数据附在现有类型中
5. **Agent 工具集不变** — 新功能走 API 层，不给 Agent 加新工具
6. **try/except 包裹所有新逻辑** — 失败只打日志，不影响链路

### 禁止操作

1. ❌ 修改 `create_graph()` 的节点列表
2. ❌ 修改 `route_after_*` 函数的路由逻辑
3. ❌ 修改 Agent 的返回值结构（只允许追加新字段）
4. ❌ 修改 `tool_executor.py` 的路径安全逻辑
5. ❌ 在 Agent 内部引入新的外部依赖（知识库/模板走 API 层）
6. ❌ deliver_node 直接写入项目目录的快照/评分/扫描结果（必须用外部目录）

### 测试验证

每个新功能实施后，必须运行：

```bash
# 后端测试
cd Blueprint && python -m pytest tests/ -v

# 前端测试
cd frontend && npm test

# 集成测试（手动）
# 输入"做一个计算器"，验证完整流程：PM → Architect → interrupt → Developer → Tester → Reviewer → 交付
```

---

## 4. 文件变更安全矩阵

| 文件 | 新功能允许改动 | 禁止改动 |
|------|--------------|---------|
| agents/state.py | 追加新字段 | 删除/重命名现有字段 |
| agents/graph.py | deliver_node hook 链（每个功能是独立函数） | 节点列表、路由函数、返回值结构 |
| agents/developer.py | 追加 trace 记录（try/except） | 工具循环逻辑、返回值结构 |
| agents/tester.py | 同上 | 同上 |
| agents/reviewer.py | 同上 | 同上 |
| agents/pm.py | 追加 trace 记录 | 返回值结构 |
| agents/architect.py | 追加 trace 记录 | 返回值结构 |
| agents/tools.py | 不改 | 任何改动 |
| agents/tool_executor.py | 不改 | 任何改动 |
| api/websocket.py | project_done handler 追加字段解析 | 消息类型分发逻辑 |
| api/projects.py | 追加新端点 | 现有端点逻辑 |
| utils/memory.py | 追加新表/方法 | 现有表结构 |
| config.py | 追加新配置项 | 现有配置项 |
| 前端所有文件 | 追加新组件/新路由 | 现有组件逻辑 |
