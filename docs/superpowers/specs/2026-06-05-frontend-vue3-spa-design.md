# Blueprint 前端重构设计文档

> **日期：** 2026-06-05
> **状态：** 设计定稿
> **目标：** 将多页面 HTML 前端重构为 Vue 3 SPA，解决状态丢失和代码混乱问题

---

## 1. 背景

### 当前问题

| 问题 | 表现 |
|------|------|
| 页面跳转丢状态 | 工作台执行到一半去设置，回来全没了 |
| 代码混乱 | 5 个 HTML 文件共 5562 行，CSS/JS 混在一起 |
| WebSocket 断连 | 页面跳转时 WebSocket 断开，Agent 进度丢失 |
| 难以扩展 | 想加功能只能往 1000+ 行的 HTML 里塞 |

### 目标

1. 页面切换不丢状态、不断 WebSocket
2. 组件化，每个功能独立，易维护
3. 白色清新风格，替换 Mission Control 暗黑风格
4. 支持以后扩展功能

---

## 2. 技术选型

| 技术 | 用途 | 理由 |
|------|------|------|
| Vue 3 | 前端框架 | 组件化、响应式、生态成熟 |
| Vite | 构建工具 | 快速热更新、开箱即用 |
| Vue Router | 路由 | SPA 标准方案，页面切换不刷新 |
| Pinia | 状态管理 | Vue 3 官方推荐，轻量 |
| 原生 CSS | 样式 | 简单直接，以后可加 Tailwind |

**未来扩展：** Tailwind CSS（写入待办，不急）

---

## 3. 项目结构

```
frontend/
├── index.html
├── package.json
├── vite.config.js
├── src/
│   ├── main.js                 ← Vue 初始化
│   ├── App.vue                 ← 主布局（导航栏 + 路由出口）
│   ├── router.js               ← 路由配置
│   ├── stores/
│   │   └── project.js          ← Pinia 状态管理
│   ├── composables/
│   │   └── useWebSocket.js     ← WebSocket 全局连接
│   ├── api/
│   │   └── index.js            ← REST API 封装
│   ├── pages/
│   │   ├── LoginPage.vue       ← 登录/注册
│   │   ├── WorkbenchPage.vue   ← 主工作台
│   │   ├── ProjectsPage.vue    ← 项目列表
│   │   ├── ProjectDetailPage.vue ← 项目详情
│   │   └── SettingsPage.vue    ← 设置
│   ├── components/
│   │   ├── ChatPanel.vue       ← 聊天消息 + 输入框
│   │   ├── FlowPanel.vue       ← Agent 流程面板
│   │   ├── AgentCard.vue       ← 单个 Agent 卡片
│   │   ├── AgentStatusBar.vue  ← 顶部 Agent 状态概览
│   │   ├── IterationInfo.vue   ← 迭代轮次显示
│   │   ├── DiscussionPanel.vue ← Proposer-Critic 讨论
│   │   ├── InterruptDialog.vue ← 确认对话框
│   │   ├── OutputPanel.vue     ← 文件列表 + 代码预览 + 下载
│   │   └── LoadingBar.vue      ← 顶部进度条
│   └── styles/
│       └── main.css            ← 全局样式
```

---

## 4. 路由设计

```javascript
routes: [
  { path: '/login', component: LoginPage },
  { path: '/', component: WorkbenchPage, meta: { requiresAuth: true } },
  { path: '/projects', component: ProjectsPage, meta: { requiresAuth: true } },
  { path: '/projects/:id', component: ProjectDetailPage, meta: { requiresAuth: true } },
  { path: '/settings', component: SettingsPage, meta: { requiresAuth: true } },
]
```

**路由守卫：**

```javascript
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore();
  const isLoggedIn = !!authStore.token;

  if (to.meta.requiresAuth && !isLoggedIn) return next('/login');
  if (to.path === '/login' && isLoggedIn) return next('/');
  next();
});
```

**边界处理：**
- token 过期 → API 返回 401 → 清理 authStore → 跳登录页
- WebSocket 401 → 清理 authStore → 跳登录页
- 已登录访问 /login → 重定向到 /
- 页面刷新 → authStore 从 localStorage 恢复 token

---

## 5. 状态管理（Pinia）

拆分为 3 个 store，职责分离：

```javascript
// stores/auth.js — 登录态
export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || null,
    username: localStorage.getItem('username') || null,
  }),
  actions: {
    setAuth(token, username) {
      this.token = token;
      this.username = username;
      localStorage.setItem('token', token);
      localStorage.setItem('username', username);
    },
    clearAuth() {
      this.token = null;
      this.username = null;
      localStorage.removeItem('token');
      localStorage.removeItem('username');
    },
  },
})

// stores/project.js — 项目数据
export const useProjectStore = defineStore('project', {
  state: () => ({
    messages: [],              // 聊天消息列表
    agentStatus: {},           // { pm: 'waiting', architect: 'running', ... }
    currentProject: null,      // 当前项目信息
    iteration: 0,              // 迭代计数
    maxIterations: 3,
    files: {},                 // 生成的文件 {path: content}
    interrupt: null,           // interrupt 状态
  }),
  actions: {
    reset() { /* 重置所有状态 */ },
  },
})

// stores/websocket.js — 连接状态
export const useWsStore = defineStore('ws', {
  state: () => ({
    isConnected: false,
    reconnecting: false,
    lastError: null,
  }),
})
```

**核心设计：** 状态全局持有，页面切换不销毁。WebSocket 收到消息时更新 projectStore，所有页面自动响应。

---

## 6. WebSocket 设计

```javascript
// composables/useWebSocket.js
// 模块顶层创建实例（全局单例）
let ws = null;
let reconnectTimer = null;

// composable 只返回引用，不创建新实例
export function useWebSocket() {
  const wsStore = useWsStore();
  const authStore = useAuthStore();
  const projectStore = useProjectStore();

  function connect() {
    const token = authStore.token;
    if (!token) return;
    ws = new WebSocket(`ws://${location.host}/ws/project?token=${token}`);

    ws.onopen = () => { wsStore.isConnected = true; wsStore.reconnecting = false; };
    ws.onmessage = (e) => { handleMessage(JSON.parse(e.data), projectStore); };
    ws.onclose = (e) => {
      wsStore.isConnected = false;
      if (e.code === 4001) { authStore.clearAuth(); router.push('/login'); return; }
      wsStore.reconnecting = true;
      reconnectTimer = setTimeout(connect, 2000);
    };
  }

  function send(msg) { if (ws?.readyState === 1) ws.send(JSON.stringify(msg)); }
  function disconnect() { clearTimeout(reconnectTimer); ws?.close(); }

  return { connect, send, disconnect };
}
```

**连接生命周期：**
1. App.vue 挂载时 → `connect()`
2. 收到消息 → 更新 projectStore
3. 页面切换 → 连接不变，store 不变
4. 断连 → 自动重连（2秒后），wsStore.reconnecting = true（UI 显示重连中）
5. 认证失败（4001）→ 清理 authStore → 跳登录页

### 消息协议（后端已实现，前端对接）

**前端 → 后端：**

| type | 字段 | 说明 |
|------|------|------|
| start_project | requirement, project_id | 开始新项目 |
| resume | thread_id, decision | interrupt 后恢复 |
| rethink | thread_id, feedback | 触发重新审查 |
| cancel | — | 取消执行 |
| reconnect | project_id | 断线重连，请求状态恢复 |

**后端 → 前端：**

| type | 说明 |
|------|------|
| agent_start | Agent 开始执行 |
| agent_thinking | Agent 思考中（loading） |
| agent_update | Agent 输出更新 |
| agent_done | Agent 执行完成 |
| interrupt | 需要人工确认/澄清 |
| error | 执行错误 |
| project_done | 项目完成（含 files） |
| state_sync | 状态同步（reconnect 后推送） |

---

## 7. 视觉设计

### 配色

| 元素 | 颜色 |
|------|------|
| 背景 | #FFFFFF（白） |
| 面板 | #F8F9FA（浅灰） |
| 边框 | #E5E7EB |
| 主色 | #3B82F6（蓝） |
| 文字 | #1F2937（深灰） |
| 辅助文字 | #6B7280 |
| 成功 | #10B981（绿） |
| 错误 | #EF4444（红） |
| 警告 | #F59E0B（黄） |

### Agent 卡片配色

| Agent | 左侧条颜色 |
|-------|-----------|
| PM | #3B82F6（蓝） |
| 架构师 | #8B5CF6（紫） |
| 开发者 | #10B981（绿） |
| 测试员 | #F59E0B（橙） |
| 审查员 | #EC4899（粉） |

### 布局

- 顶部导航栏：白色背景，底部分隔线
- 工作台：左侧流程面板 + 右侧聊天面板
- 卡片：白色背景 + 圆角（8px）+ 轻微阴影
- 字体：系统默认（-apple-system, BlinkMacSystemFont, sans-serif）

---

## 8. 后端 API 对接

前端通过 REST API 和 WebSocket 与后端通信：

| 通信方式 | 用途 |
|---------|------|
| REST API | 登录/注册、获取设置、保存设置、获取项目列表、获取项目详情 |
| WebSocket | Agent 执行、实时消息、interrupt/resume |

**后端不需要改动。** 前端只是换了实现方式，API 接口不变。

### API 错误处理

```javascript
// api/index.js — 统一拦截
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      authStore.clearAuth();
      router.push('/login');
    }
    return Promise.reject(err);
  }
);
```

| 状态码 | 处理 |
|--------|------|
| 401 | 清 token，跳登录 |
| 403 | 提示无权限 |
| 500 | 提示服务器错误 |
| 网络断开 | 提示网络异常 |

### 加载状态

- 页面切换 → 路由级 loading（顶部进度条）
- API 请求 → 按钮 loading 状态
- WebSocket 重连 → 顶部黄色提示条"正在重连..."

---

## 9. 迁移策略

| 步骤 | 内容 |
|------|------|
| 1 | 初始化 Vue 3 + Vite 项目 |
| 2 | 实现 App.vue 主布局 + 路由 |
| 3 | 实现 useWebSocket composable |
| 4 | 实现 Pinia store |
| 5 | 迁移登录页 |
| 6 | 迁移工作台（ChatPanel + FlowPanel） |
| 7 | 迁移项目列表 + 详情 |
| 8 | 迁移设置页 |
| 9 | 删除旧 HTML 文件 |

**旧文件保留到迁移完成后再删。**

### 数据持久化

| 场景 | 处理方式 |
|------|---------|
| 页面刷新 | authStore 从 localStorage 恢复 token；projectStore 清空，从后端 API 重新加载项目数据 |
| WebSocket 断连重连 | 发送 reconnect 消息，后端推送 state_sync 恢复当前状态 |
| 浏览器关闭再打开 | 需要重新开始项目（WebSocket 状态不持久化） |

### 新旧并行期

迁移期间新旧前端共存：

| 阶段 | 前端 | 后端 |
|------|------|------|
| 迁移中 | 旧 HTML 在 `Blueprint/static/`，新 Vue 在 `frontend/` | FastAPI serve 旧 HTML |
| 迁移完成 | Vue build 产物复制到 `Blueprint/static/` | FastAPI serve 新前端 |

开发时 Vite 跑在 `localhost:5173`，配置代理转发 `/api` 和 `/ws` 到 `localhost:8080`。

---

## 10. 不做的事

| 功能 | 为什么不做 |
|------|-----------|
| Tailwind CSS | 写入待办，以后再加 |
| 移动端适配 | MVP 只做桌面端 |
| SSR | 不需要 SEO，SPA 够用 |
| 单元测试 | 先跑通，以后加 |
| PWA | 不需要离线功能 |
