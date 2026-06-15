# Blueprint 前端 Vue 3 SPA 重构实现计划（TDD）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将多页面 HTML 前端重构为 Vue 3 SPA，解决状态丢失和代码混乱问题。

**Architecture:** Vue 3 SPA + Pinia 状态管理 + 全局 WebSocket composable。页面切换不刷新浏览器，WebSocket 连接全局保持，状态存 Pinia store。

**Tech Stack:** Vue 3, Vite, Vue Router, Pinia, Vitest, @vue/test-utils, 原生 CSS

**TDD 规则：** 每个 Task 先写测试，看它失败，再写实现，看它通过。纯红-绿-重构循环。

**Design Spec:** `docs/superpowers/specs/2026-06-05-frontend-vue3-spa-design.md`

---

## 文件结构

```
frontend/src/
├── main.js                        ← Vue + Pinia + Router 初始化
├── App.vue                        ← 主布局（导航栏 + 路由出口 + LoadingBar）
├── router.js                      ← 路由配置 + 守卫
├── stores/
│   ├── auth.js                    ← 登录态（token, username）
│   ├── project.js                 ← 项目数据（messages, agentStatus, files）
│   └── websocket.js               ← 连接状态（isConnected, reconnecting）
├── composables/
│   └── useWebSocket.js            ← WebSocket 全局单例
├── api/
│   └── index.js                   ← REST API 封装 + 错误拦截
├── pages/
│   ├── LoginPage.vue              ← 登录/注册
│   ├── WorkbenchPage.vue          ← 主工作台
│   ├── ProjectsPage.vue           ← 项目列表
│   ├── ProjectDetailPage.vue      ← 项目详情
│   └── SettingsPage.vue           ← 设置
├── components/
│   ├── ChatPanel.vue              ← 聊天消息 + 输入框
│   ├── FlowPanel.vue              ← Agent 流程面板
│   ├── AgentCard.vue              ← 单个 Agent 卡片
│   ├── AgentStatusBar.vue         ← 顶部 Agent 状态概览
│   ├── IterationInfo.vue          ← 迭代轮次显示
│   ├── DiscussionPanel.vue        ← Proposer-Critic 讨论
│   ├── InterruptDialog.vue        ← 确认/澄清对话框
│   ├── OutputPanel.vue            ← 文件列表 + 代码预览 + 下载
│   └── LoadingBar.vue             ← 顶部进度条
├── styles/
│   └── main.css                   ← 全局样式（白色清新风格）
└── __tests__/                     ← 测试文件
    ├── stores/
    │   ├── auth.test.js
    │   ├── project.test.js
    │   └── websocket.test.js
    ├── composables/
    │   └── useWebSocket.test.js
    ├── api/
    │   └── index.test.js
    ├── components/
    │   ├── AgentCard.test.js
    │   ├── ChatPanel.test.js
    │   ├── FlowPanel.test.js
    │   ├── InterruptDialog.test.js
    │   └── OutputPanel.test.js
    └── pages/
        ├── LoginPage.test.js
        └── WorkbenchPage.test.js
```

---

### Task 1: 项目初始化 + 测试框架

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.js`
- Create: `frontend/src/styles/main.css`
- Create: `frontend/vitest.config.js`

- [ ] **Step 1: 安装依赖**

```bash
cd frontend
npm install vue-router@4 pinia
npm install -D vitest @vue/test-utils jsdom
```

- [ ] **Step 2: 配置 Vitest**

```javascript
// frontend/vitest.config.js
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
```

- [ ] **Step 3: 添加 test 脚本到 package.json**

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

- [ ] **Step 4: 写第一个测试（验证测试框架工作）**

```javascript
// frontend/src/__tests__/smoke.test.js
import { describe, it, expect } from 'vitest'

describe('smoke test', () => {
  it('vitest works', () => {
    expect(1 + 1).toBe(2)
  })
})
```

- [ ] **Step 5: 运行测试，验证它通过**

```bash
cd frontend && npm test
```

Expected: 1 test passed

- [ ] **Step 6: 配置 Vite 代理**

```javascript
// frontend/vite.config.js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:8080', ws: true },
    },
  },
  build: {
    outDir: '../Blueprint/static',
    emptyOutDir: true,
  },
})
```

- [ ] **Step 7: 创建全局样式**

```css
/* frontend/src/styles/main.css */
:root {
  --bg: #FFFFFF;
  --bg-panel: #F8F9FA;
  --border: #E5E7EB;
  --primary: #3B82F6;
  --text: #1F2937;
  --text-dim: #6B7280;
  --success: #10B981;
  --error: #EF4444;
  --warning: #F59E0B;
  --radius: 8px;
  --shadow: 0 1px 3px rgba(0,0,0,0.1);
  --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: var(--font); background: var(--bg); color: var(--text); }

.agent-pm { --agent-color: #3B82F6; }
.agent-architect { --agent-color: #8B5CF6; }
.agent-developer { --agent-color: #10B981; }
.agent-tester { --agent-color: #F59E0B; }
.agent-reviewer { --agent-color: #EC4899; }
```

- [ ] **Step 8: 清理 Vite 默认文件**

删除 `frontend/src/components/HelloWorld.vue` 和 `frontend/src/assets/`。

---

### Task 2: authStore（TDD）

**Files:**
- Create: `frontend/src/__tests__/stores/auth.test.js`
- Create: `frontend/src/stores/auth.js`

- [ ] **Step 1: 写失败的测试**

```javascript
// frontend/src/__tests__/stores/auth.test.js
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../../stores/auth.js'

describe('authStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('默认未登录', () => {
    const store = useAuthStore()
    expect(store.isLoggedIn).toBe(false)
    expect(store.token).toBeNull()
    expect(store.username).toBeNull()
  })

  it('setAuth 保存 token 和 username 到 state 和 localStorage', () => {
    const store = useAuthStore()
    store.setAuth('test-token', 'testuser')

    expect(store.token).toBe('test-token')
    expect(store.username).toBe('testuser')
    expect(store.isLoggedIn).toBe(true)
    expect(localStorage.getItem('token')).toBe('test-token')
    expect(localStorage.getItem('username')).toBe('testuser')
  })

  it('clearAuth 清除 state 和 localStorage', () => {
    const store = useAuthStore()
    store.setAuth('test-token', 'testuser')
    store.clearAuth()

    expect(store.token).toBeNull()
    expect(store.username).toBeNull()
    expect(store.isLoggedIn).toBe(false)
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('从 localStorage 恢复 token', () => {
    localStorage.setItem('token', 'saved-token')
    localStorage.setItem('username', 'saved-user')

    const store = useAuthStore()
    expect(store.token).toBe('saved-token')
    expect(store.username).toBe('saved-user')
    expect(store.isLoggedIn).toBe(true)
  })
})
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd frontend && npm test -- auth.test.js
```

Expected: FAIL — `Cannot find module '../../stores/auth.js'`

- [ ] **Step 3: 写最小实现**

```javascript
// frontend/src/stores/auth.js
import { defineStore } from 'pinia'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || null,
    username: localStorage.getItem('username') || null,
  }),
  getters: {
    isLoggedIn: (state) => !!state.token,
  },
  actions: {
    setAuth(token, username) {
      this.token = token
      this.username = username
      localStorage.setItem('token', token)
      localStorage.setItem('username', username)
    },
    clearAuth() {
      this.token = null
      this.username = null
      localStorage.removeItem('token')
      localStorage.removeItem('username')
    },
  },
})
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
cd frontend && npm test -- auth.test.js
```

Expected: 4 tests passed

---

### Task 3: projectStore（TDD）

**Files:**
- Create: `frontend/src/__tests__/stores/project.test.js`
- Create: `frontend/src/stores/project.js`

- [ ] **Step 1: 写失败的测试**

```javascript
// frontend/src/__tests__/stores/project.test.js
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useProjectStore } from '../../stores/project.js'

describe('projectStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认状态正确', () => {
    const store = useProjectStore()
    expect(store.messages).toEqual([])
    expect(store.agentStatus).toEqual({})
    expect(store.iteration).toBe(0)
    expect(store.maxIterations).toBe(3)
    expect(store.files).toEqual({})
    expect(store.interrupt).toBeNull()
  })

  it('addMessage 添加消息并附加 timestamp', () => {
    const store = useProjectStore()
    store.addMessage({ role: 'user', name: 'user', content: 'hello' })

    expect(store.messages).toHaveLength(1)
    expect(store.messages[0].content).toBe('hello')
    expect(store.messages[0].timestamp).toBeDefined()
  })

  it('setAgentStatus 更新指定 Agent 状态', () => {
    const store = useProjectStore()
    store.setAgentStatus('pm', 'running')

    expect(store.agentStatus.pm).toBe('running')

    store.setAgentStatus('pm', 'done')
    expect(store.agentStatus.pm).toBe('done')
  })

  it('agentList 按固定顺序返回 Agent 列表', () => {
    const store = useProjectStore()
    store.setAgentStatus('pm', 'done')
    store.setAgentStatus('developer', 'running')

    const list = store.agentList
    expect(list).toHaveLength(5)
    expect(list[0]).toEqual({ name: 'pm', status: 'done' })
    expect(list[1]).toEqual({ name: 'architect', status: 'waiting' })
    expect(list[2]).toEqual({ name: 'developer', status: 'running' })
    expect(list[3]).toEqual({ name: 'tester', status: 'waiting' })
    expect(list[4]).toEqual({ name: 'reviewer', status: 'waiting' })
  })

  it('reset 清空所有状态', () => {
    const store = useProjectStore()
    store.addMessage({ role: 'user', name: 'user', content: 'test' })
    store.setAgentStatus('pm', 'done')
    store.iteration = 3

    store.reset()

    expect(store.messages).toEqual([])
    expect(store.agentStatus).toEqual({})
    expect(store.iteration).toBe(0)
    expect(store.files).toEqual({})
    expect(store.interrupt).toBeNull()
  })
})
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd frontend && npm test -- project.test.js
```

Expected: FAIL — `Cannot find module '../../stores/project.js'`

- [ ] **Step 3: 写最小实现**

```javascript
// frontend/src/stores/project.js
import { defineStore } from 'pinia'

export const useProjectStore = defineStore('project', {
  state: () => ({
    messages: [],
    agentStatus: {},
    currentProject: null,
    iteration: 0,
    maxIterations: 3,
    files: {},
    interrupt: null,
  }),
  getters: {
    agentList: (state) => {
      const order = ['pm', 'architect', 'developer', 'tester', 'reviewer']
      return order.map(name => ({
        name,
        status: state.agentStatus[name] || 'waiting',
      }))
    },
  },
  actions: {
    reset() {
      this.messages = []
      this.agentStatus = {}
      this.currentProject = null
      this.iteration = 0
      this.files = {}
      this.interrupt = null
    },
    addMessage(msg) {
      this.messages.push({ ...msg, timestamp: Date.now() })
    },
    setAgentStatus(agent, status) {
      this.agentStatus = { ...this.agentStatus, [agent]: status }
    },
  },
})
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
cd frontend && npm test -- project.test.js
```

Expected: 5 tests passed

---

### Task 4: wsStore（TDD）

**Files:**
- Create: `frontend/src/__tests__/stores/websocket.test.js`
- Create: `frontend/src/stores/websocket.js`

- [ ] **Step 1: 写失败的测试**

```javascript
// frontend/src/__tests__/stores/websocket.test.js
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWsStore } from '../../stores/websocket.js'

describe('wsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认状态正确', () => {
    const store = useWsStore()
    expect(store.isConnected).toBe(false)
    expect(store.reconnecting).toBe(false)
    expect(store.lastError).toBeNull()
  })

  it('可以更新连接状态', () => {
    const store = useWsStore()
    store.isConnected = true
    store.reconnecting = false

    expect(store.isConnected).toBe(true)
  })
})
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd frontend && npm test -- websocket.test.js
```

Expected: FAIL

- [ ] **Step 3: 写最小实现**

```javascript
// frontend/src/stores/websocket.js
import { defineStore } from 'pinia'

export const useWsStore = defineStore('ws', {
  state: () => ({
    isConnected: false,
    reconnecting: false,
    lastError: null,
  }),
})
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
cd frontend && npm test -- websocket.test.js
```

Expected: 2 tests passed

---

### Task 5: main.js + Pinia 注册

**Files:**
- Create: `frontend/src/main.js`
- Create: `frontend/src/App.vue`（最小占位）
- Create: `frontend/src/__tests__/main.test.js`

- [ ] **Step 1: 写失败的测试**

```javascript
// frontend/src/__tests__/main.test.js
import { describe, it, expect } from 'vitest'
import { createApp } from 'vue'
import { createPinia } from 'pinia'

describe('main.js setup', () => {
  it('Pinia 可以注册到 Vue', () => {
    const app = createApp({})
    const pinia = createPinia()
    app.use(pinia)
    // 不报错即成功
    expect(true).toBe(true)
  })
})
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd frontend && npm test -- main.test.js
```

Expected: FAIL — `createPinia` import error (pinia 未安装或 main.js 不存在)

- [ ] **Step 3: 写最小实现**

```javascript
// frontend/src/main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './styles/main.css'

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
```

```vue
<!-- frontend/src/App.vue -->
<template>
  <div id="app">Blueprint</div>
</template>
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
cd frontend && npm test -- main.test.js
```

Expected: 1 test passed

---

### Task 6: Router + 路由守卫（TDD）

**Files:**
- Create: `frontend/src/router.js`
- Create: `frontend/src/__tests__/router.test.js`
- Create: `frontend/src/pages/LoginPage.vue`（占位）
- Create: `frontend/src/pages/WorkbenchPage.vue`（占位）
- Create: `frontend/src/pages/ProjectsPage.vue`（占位）
- Create: `frontend/src/pages/ProjectDetailPage.vue`（占位）
- Create: `frontend/src/pages/SettingsPage.vue`（占位）

- [ ] **Step 1: 写失败的测试**

```javascript
// frontend/src/__tests__/router.test.js
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../stores/auth.js'

describe('router guard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('未登录时访问受保护路由应重定向到 /login', async () => {
    const { default: router } = await import('../router.js')
    const authStore = useAuthStore()
    expect(authStore.isLoggedIn).toBe(false)

    await router.push('/')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('已登录时访问 /login 应重定向到 /', async () => {
    const { default: router } = await import('../router.js')
    const authStore = useAuthStore()
    authStore.setAuth('test-token', 'testuser')

    await router.push('/login')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/')
  })

  it('已登录时可以访问受保护路由', async () => {
    const { default: router } = await import('../router.js')
    const authStore = useAuthStore()
    authStore.setAuth('test-token', 'testuser')

    await router.push('/projects')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/projects')
  })
})
```

- [ ] **Step 2: 写占位页面**

```vue
<!-- frontend/src/pages/LoginPage.vue -->
<template><div>Login Page</div></template>

<!-- frontend/src/pages/WorkbenchPage.vue -->
<template><div>Workbench Page</div></template>

<!-- frontend/src/pages/ProjectsPage.vue -->
<template><div>Projects Page</div></template>

<!-- frontend/src/pages/ProjectDetailPage.vue -->
<template><div>Project Detail Page</div></template>

<!-- frontend/src/pages/SettingsPage.vue -->
<template><div>Settings Page</div></template>
```

- [ ] **Step 3: 运行测试，验证失败**

```bash
cd frontend && npm test -- router.test.js
```

Expected: FAIL — `Cannot find module '../router.js'`

- [ ] **Step 4: 写最小实现**

```javascript
// frontend/src/router.js
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './stores/auth.js'

const routes = [
  { path: '/login', component: () => import('./pages/LoginPage.vue') },
  { path: '/', component: () => import('./pages/WorkbenchPage.vue'), meta: { requiresAuth: true } },
  { path: '/projects', component: () => import('./pages/ProjectsPage.vue'), meta: { requiresAuth: true } },
  { path: '/projects/:id', component: () => import('./pages/ProjectDetailPage.vue'), meta: { requiresAuth: true } },
  { path: '/settings', component: () => import('./pages/SettingsPage.vue'), meta: { requiresAuth: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  if (to.meta.requiresAuth && !authStore.isLoggedIn) return next('/login')
  if (to.path === '/login' && authStore.isLoggedIn) return next('/')
  next()
})

export default router
```

- [ ] **Step 5: 更新 main.js 加入 router**

```javascript
// frontend/src/main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router.js'
import './styles/main.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

- [ ] **Step 6: 运行测试，验证通过**

```bash
cd frontend && npm test -- router.test.js
```

Expected: 3 tests passed

---

### Task 7: API 模块（TDD）

**Files:**
- Create: `frontend/src/api/index.js`
- Create: `frontend/src/__tests__/api/index.test.js`

- [ ] **Step 1: 写失败的测试**

```javascript
// frontend/src/__tests__/api/index.test.js
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { api } from '../../api/index.js'

describe('api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('login 发送 POST 请求到 /api/auth/login', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ token: 'abc', username: 'user' }),
    })

    const result = await api.login('user', 'pass')

    expect(fetchSpy).toHaveBeenCalledWith('/api/auth/login', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ username: 'user', password: 'pass' }),
    }))
    expect(result.token).toBe('abc')
  })

  it('请求带 Authorization header', async () => {
    localStorage.setItem('token', 'my-token')
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    })

    await api.getSettings()

    expect(fetchSpy).toHaveBeenCalledWith('/api/settings', expect.objectContaining({
      headers: expect.objectContaining({
        'Authorization': 'Bearer my-token',
      }),
    }))
  })

  it('401 响应应清除 token', async () => {
    localStorage.setItem('token', 'expired')
    vi.spyOn(global, 'fetch').mockResolvedValue({
      status: 401,
      ok: false,
      json: () => Promise.resolve({}),
    })

    await expect(api.getSettings()).rejects.toThrow('Unauthorized')
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('非 ok 响应应抛出错误', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: 'Server Error' }),
    })

    await expect(api.getSettings()).rejects.toThrow('Server Error')
  })
})
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd frontend && npm test -- api/index.test.js
```

Expected: FAIL

- [ ] **Step 3: 写最小实现**

```javascript
// frontend/src/api/index.js
const BASE = '/api'

async function request(path, options = {}) {
  const token = localStorage.getItem('token')
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...options, headers })

  if (res.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || data.message || `HTTP ${res.status}`)
  }

  return res.json()
}

export const api = {
  login: (username, password) => request('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  register: (username, password) => request('/auth/register', { method: 'POST', body: JSON.stringify({ username, password }) }),
  getSettings: () => request('/settings'),
  updateSettings: (data) => request('/settings', { method: 'PUT', body: JSON.stringify(data) }),
  getProjects: () => request('/projects'),
  getProject: (id) => request(`/projects/${id}`),
  deleteProject: (id) => request(`/projects/${id}`, { method: 'DELETE' }),
  getProjectFiles: (id) => request(`/projects/${id}/files`),
  downloadProject: (id) => `/api/projects/${id}/download`,
}
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
cd frontend && npm test -- api/index.test.js
```

Expected: 4 tests passed

---

### Task 8: AgentCard 组件（TDD）

**Files:**
- Create: `frontend/src/components/AgentCard.vue`
- Create: `frontend/src/__tests__/components/AgentCard.test.js`

- [ ] **Step 1: 写失败的测试**

```javascript
// frontend/src/__tests__/components/AgentCard.test.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AgentCard from '../../components/AgentCard.vue'

describe('AgentCard', () => {
  it('显示 Agent 名称和状态', () => {
    const wrapper = mount(AgentCard, { props: { name: 'pm', status: 'waiting' } })

    expect(wrapper.text()).toContain('PM')
    expect(wrapper.text()).toContain('等待中')
  })

  it('执行中状态显示正确文字', () => {
    const wrapper = mount(AgentCard, { props: { name: 'developer', status: 'running' } })

    expect(wrapper.text()).toContain('开发者')
    expect(wrapper.text()).toContain('执行中')
    expect(wrapper.classes()).toContain('running')
  })

  it('完成状态显示绿色', () => {
    const wrapper = mount(AgentCard, { props: { name: 'tester', status: 'done' } })

    expect(wrapper.text()).toContain('已完成')
    expect(wrapper.classes()).toContain('done')
  })

  it('默认状态为 waiting', () => {
    const wrapper = mount(AgentCard, { props: { name: 'pm' } })

    expect(wrapper.text()).toContain('等待中')
  })
})
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd frontend && npm test -- AgentCard.test.js
```

Expected: FAIL

- [ ] **Step 3: 写最小实现**

```vue
<!-- frontend/src/components/AgentCard.vue -->
<template>
  <div :class="['agent-card', `agent-${name}`, status]">
    <div class="agent-bar"></div>
    <div class="agent-body">
      <div class="agent-icon">{{ icon }}</div>
      <div class="agent-info">
        <div class="agent-name">{{ label }}</div>
        <div class="agent-status-text">{{ statusText }}</div>
      </div>
      <div class="agent-dot" :class="status"></div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ name: String, status: { type: String, default: 'waiting' } })

const labels = { pm: 'PM', architect: '架构师', developer: '开发者', tester: '测试员', reviewer: '审查员' }
const icons = { pm: '👤', architect: '🏗️', developer: '💻', tester: '🧪', reviewer: '🔍' }
const statusTexts = { waiting: '等待中', running: '执行中', done: '已完成', error: '错误', paused: '暂停' }

const label = computed(() => labels[props.name] || props.name)
const icon = computed(() => icons[props.name] || '🤖')
const statusText = computed(() => statusTexts[props.status] || props.status)
</script>

<style scoped>
.agent-card { background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; transition: all 0.2s; }
.agent-card.running { border-color: var(--agent-color); box-shadow: 0 0 12px rgba(59,130,246,0.15); }
.agent-bar { height: 3px; background: var(--agent-color); opacity: 0.4; }
.agent-card.running .agent-bar { opacity: 1; }
.agent-body { display: flex; align-items: center; gap: 12px; padding: 14px 16px; }
.agent-icon { font-size: 24px; }
.agent-info { flex: 1; }
.agent-name { font-size: 13px; font-weight: 600; color: var(--text); }
.agent-status-text { font-size: 12px; color: var(--text-dim); margin-top: 2px; }
.agent-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--border); }
.agent-dot.running { background: var(--primary); animation: pulse 1.5s infinite; }
.agent-dot.done { background: var(--success); }
.agent-dot.error { background: var(--error); }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
</style>
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
cd frontend && npm test -- AgentCard.test.js
```

Expected: 4 tests passed

---

### Task 9: FlowPanel + IterationInfo（TDD）

**Files:**
- Create: `frontend/src/components/FlowPanel.vue`
- Create: `frontend/src/components/IterationInfo.vue`
- Create: `frontend/src/__tests__/components/FlowPanel.test.js`

- [ ] **Step 1: 写失败的测试**

```javascript
// frontend/src/__tests__/components/FlowPanel.test.js
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useProjectStore } from '../../stores/project.js'
import FlowPanel from '../../components/FlowPanel.vue'

describe('FlowPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('显示 5 个 Agent 卡片', () => {
    const wrapper = mount(FlowPanel)
    const cards = wrapper.findAll('.agent-card')
    expect(cards).toHaveLength(5)
  })

  it('Agent 状态变化时卡片自动更新', async () => {
    const store = useProjectStore()
    const wrapper = mount(FlowPanel)

    store.setAgentStatus('pm', 'running')
    await wrapper.vm.$nextTick()

    const pmCard = wrapper.find('.agent-pm')
    expect(pmCard.classes()).toContain('running')
  })

  it('iteration > 0 时显示迭代信息', async () => {
    const store = useProjectStore()
    store.iteration = 2
    store.maxIterations = 3

    const wrapper = mount(FlowPanel)
    expect(wrapper.text()).toContain('迭代进度')
    expect(wrapper.text()).toContain('2 / 3')
  })
})
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd frontend && npm test -- FlowPanel.test.js
```

Expected: FAIL

- [ ] **Step 3: 写最小实现**

```vue
<!-- frontend/src/components/IterationInfo.vue -->
<template>
  <div v-if="projectStore.iteration > 0" class="iteration-info">
    <div class="iteration-label">迭代进度</div>
    <div class="iteration-bar">
      <div class="iteration-fill" :style="{ width: `${(projectStore.iteration / projectStore.maxIterations) * 100}%` }"></div>
    </div>
    <div class="iteration-count">{{ projectStore.iteration }} / {{ projectStore.maxIterations }}</div>
  </div>
</template>

<script setup>
import { useProjectStore } from '../stores/project.js'
const projectStore = useProjectStore()
</script>

<style scoped>
.iteration-info { margin-top: 20px; padding: 16px; background: var(--bg); border-radius: var(--radius); border: 1px solid var(--border); }
.iteration-label { font-size: 12px; color: var(--text-dim); margin-bottom: 8px; }
.iteration-bar { height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; }
.iteration-fill { height: 100%; background: var(--primary); border-radius: 2px; transition: width 0.3s; }
.iteration-count { font-size: 12px; color: var(--text-dim); margin-top: 6px; text-align: right; }
</style>
```

```vue
<!-- frontend/src/components/FlowPanel.vue -->
<template>
  <div class="flow-panel">
    <div class="flow-title">Agent 协作流程</div>
    <div class="agents-grid">
      <AgentCard v-for="agent in projectStore.agentList" :key="agent.name" :name="agent.name" :status="agent.status" />
    </div>
    <IterationInfo />
  </div>
</template>

<script setup>
import { useProjectStore } from '../stores/project.js'
import AgentCard from './AgentCard.vue'
import IterationInfo from './IterationInfo.vue'

const projectStore = useProjectStore()
</script>

<style scoped>
.flow-panel { padding: 24px; background: var(--bg-panel); border-right: 1px solid var(--border); min-width: 280px; }
.flow-title { font-size: 14px; font-weight: 600; color: var(--text-dim); margin-bottom: 16px; text-transform: uppercase; letter-spacing: 1px; }
.agents-grid { display: flex; flex-direction: column; gap: 10px; }
</style>
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
cd frontend && npm test -- FlowPanel.test.js
```

Expected: 3 tests passed

---

### Task 10: ChatPanel（TDD）

**Files:**
- Create: `frontend/src/components/ChatPanel.vue`
- Create: `frontend/src/__tests__/components/ChatPanel.test.js`

- [ ] **Step 1: 写失败的测试**

```javascript
// frontend/src/__tests__/components/ChatPanel.test.js
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useProjectStore } from '../../stores/project.js'
import ChatPanel from '../../components/ChatPanel.vue'

vi.mock('../../composables/useWebSocket.js', () => ({
  useWebSocket: () => ({ send: vi.fn(), connect: vi.fn(), disconnect: vi.fn() }),
}))

describe('ChatPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('显示已有消息', () => {
    const store = useProjectStore()
    store.addMessage({ role: 'user', name: 'user', content: '做一个计算器' })
    store.addMessage({ role: 'assistant', name: 'pm', content: '收到需求' })

    const wrapper = mount(ChatPanel)
    expect(wrapper.text()).toContain('做一个计算器')
    expect(wrapper.text()).toContain('收到需求')
  })

  it('输入框回车发送消息', async () => {
    const store = useProjectStore()
    const wrapper = mount(ChatPanel)

    const textarea = wrapper.find('textarea')
    await textarea.setValue('测试需求')
    await textarea.trigger('keydown.enter')

    expect(store.messages.some(m => m.content === '测试需求')).toBe(true)
  })

  it('空消息不发送', async () => {
    const store = useProjectStore()
    const wrapper = mount(ChatPanel)

    const textarea = wrapper.find('textarea')
    await textarea.setValue('   ')
    await textarea.trigger('keydown.enter')

    expect(store.messages).toHaveLength(0)
  })

  it('发送后清空输入框', async () => {
    const store = useProjectStore()
    const wrapper = mount(ChatPanel)

    const textarea = wrapper.find('textarea')
    await textarea.setValue('测试需求')
    await textarea.trigger('keydown.enter')

    expect(textarea.element.value).toBe('')
  })
})
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd frontend && npm test -- ChatPanel.test.js
```

Expected: FAIL

- [ ] **Step 3: 写最小实现**

```vue
<!-- frontend/src/components/ChatPanel.vue -->
<template>
  <div class="chat-panel">
    <div class="chat-header">
      <span class="chat-title">通讯频道</span>
    </div>
    <div class="messages" ref="messagesRef">
      <div v-for="(msg, i) in projectStore.messages" :key="i" :class="['message', `msg-${msg.name || msg.role}`]">
        <div class="msg-avatar">{{ avatar(msg.name || msg.role) }}</div>
        <div class="msg-body">
          <div class="msg-header">
            <span class="msg-name" :style="{ color: color(msg.name) }">{{ label(msg.name) }}</span>
            <span class="msg-time">{{ time(msg.timestamp) }}</span>
          </div>
          <div class="msg-content">{{ msg.content }}</div>
        </div>
      </div>
    </div>
    <div class="chat-input">
      <textarea v-model="inputText" @keydown.enter.exact.prevent="sendMessage" placeholder="描述你的需求..." rows="1"></textarea>
      <button @click="sendMessage" :disabled="!inputText.trim()">▶</button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { useProjectStore } from '../stores/project.js'
import { useWebSocket } from '../composables/useWebSocket.js'

const projectStore = useProjectStore()
const { send } = useWebSocket()
const inputText = ref('')
const messagesRef = ref(null)

const avatarMap = { pm: '👤', architect: '🏗️', developer: '💻', tester: '🧪', reviewer: '🔍', system: '🤖', user: '👤', pm_proposer: '👤', pm_critic: '🔍', arch_proposer: '🏗️', arch_critic: '🔍', developer_critic: '🔍' }
const colorMap = { pm: '#3B82F6', architect: '#8B5CF6', developer: '#10B981', tester: '#F59E0B', reviewer: '#EC4899', system: '#6B7280', user: '#3B82F6', pm_proposer: '#3B82F6', pm_critic: '#EC4899', arch_proposer: '#8B5CF6', arch_critic: '#EC4899', developer_critic: '#EC4899' }
const labelMap = { pm: 'PM', architect: '架构师', developer: '开发者', tester: '测试员', reviewer: '审查员', system: '系统', user: '用户', pm_proposer: 'PM·方案', pm_critic: 'PM·审查', arch_proposer: '架构师·方案', arch_critic: '架构师·审查', developer_critic: '开发·审查' }

function avatar(name) { return avatarMap[name] || '🤖' }
function color(name) { return colorMap[name] || '#6B7280' }
function label(name) { return labelMap[name] || name }
function time(ts) { return ts ? new Date(ts).toLocaleTimeString() : '' }

function sendMessage() {
  const text = inputText.value.trim()
  if (!text) return
  projectStore.addMessage({ role: 'user', name: 'user', content: text })
  send({ type: 'start_project', requirement: text, project_id: 'proj-' + Date.now() })
  inputText.value = ''
}

watch(() => projectStore.messages.length, () => {
  nextTick(() => { if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight })
})
</script>

<style scoped>
.chat-panel { display: flex; flex-direction: column; height: 100%; }
.chat-header { padding: 12px 16px; border-bottom: 1px solid var(--border); }
.chat-title { font-size: 14px; font-weight: 600; color: var(--text-dim); }
.messages { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.message { display: flex; gap: 10px; }
.msg-avatar { width: 32px; height: 32px; border-radius: 50%; background: var(--bg-panel); display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0; border: 1px solid var(--border); }
.msg-body { flex: 1; min-width: 0; }
.msg-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.msg-name { font-size: 12px; font-weight: 600; }
.msg-time { font-size: 11px; color: var(--text-dim); }
.msg-content { font-size: 13px; line-height: 1.6; color: var(--text); background: var(--bg-panel); padding: 10px 14px; border-radius: 0 var(--radius) var(--radius) var(--radius); border: 1px solid var(--border); white-space: pre-wrap; word-break: break-word; }
.msg-user .msg-content { background: var(--primary); color: #fff; border: none; border-radius: var(--radius) 0 var(--radius) var(--radius); }
.chat-input { display: flex; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--border); }
.chat-input textarea { flex: 1; resize: none; border: 1px solid var(--border); border-radius: var(--radius); padding: 10px; font-size: 13px; font-family: var(--font); }
.chat-input textarea:focus { outline: none; border-color: var(--primary); }
.chat-input button { width: 40px; height: 40px; border-radius: var(--radius); background: var(--primary); color: #fff; border: none; cursor: pointer; font-size: 16px; }
.chat-input button:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
cd frontend && npm test -- ChatPanel.test.js
```

Expected: 4 tests passed

---

### Task 11: InterruptDialog + OutputPanel + DiscussionPanel（TDD）

**Files:**
- Create: `frontend/src/components/InterruptDialog.vue`
- Create: `frontend/src/components/OutputPanel.vue`
- Create: `frontend/src/components/DiscussionPanel.vue`
- Create: `frontend/src/__tests__/components/InterruptDialog.test.js`
- Create: `frontend/src/__tests__/components/OutputPanel.test.js`

- [ ] **Step 1: 写失败的测试（InterruptDialog）**

```javascript
// frontend/src/__tests__/components/InterruptDialog.test.js
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useProjectStore } from '../../stores/project.js'
import InterruptDialog from '../../components/InterruptDialog.vue'

vi.mock('../../composables/useWebSocket.js', () => ({
  useWebSocket: () => ({ send: vi.fn() }),
}))

describe('InterruptDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('无 interrupt 时不显示', () => {
    const wrapper = mount(InterruptDialog)
    expect(wrapper.find('.overlay').exists()).toBe(false)
  })

  it('有 interrupt 时显示对话框', async () => {
    const store = useProjectStore()
    store.interrupt = { type: 'confirm', message: '请确认架构设计' }

    const wrapper = mount(InterruptDialog)
    expect(wrapper.find('.overlay').exists()).toBe(true)
    expect(wrapper.text()).toContain('请确认架构设计')
  })

  it('clarify 类型显示不同标题', async () => {
    const store = useProjectStore()
    store.interrupt = { type: 'clarify', message: '需求不明确', questions: ['目标用户是谁？'] }

    const wrapper = mount(InterruptDialog)
    expect(wrapper.text()).toContain('需要补充信息')
    expect(wrapper.text()).toContain('目标用户是谁？')
  })
})
```

- [ ] **Step 2: 写失败的测试（OutputPanel）**

```javascript
// frontend/src/__tests__/components/OutputPanel.test.js
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useProjectStore } from '../../stores/project.js'
import OutputPanel from '../../components/OutputPanel.vue'

describe('OutputPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('无文件时不显示', () => {
    const wrapper = mount(OutputPanel)
    expect(wrapper.find('.output-panel').exists()).toBe(false)
  })

  it('有文件时显示文件列表', async () => {
    const store = useProjectStore()
    store.files = { 'main.py': 'print("hello")', 'index.html': '<html></html>' }

    const wrapper = mount(OutputPanel)
    expect(wrapper.text()).toContain('main.py')
    expect(wrapper.text()).toContain('index.html')
  })
})
```

- [ ] **Step 3: 运行测试，验证失败**

```bash
cd frontend && npm test -- InterruptDialog.test.js OutputPanel.test.js
```

Expected: FAIL

- [ ] **Step 4: 写最小实现**

```vue
<!-- frontend/src/components/InterruptDialog.vue -->
<template>
  <div v-if="projectStore.interrupt" class="overlay">
    <div class="dialog">
      <h3>{{ projectStore.interrupt.type === 'clarify' ? '需要补充信息' : '需要确认' }}</h3>
      <p>{{ projectStore.interrupt.message }}</p>
      <ul v-if="projectStore.interrupt.questions">
        <li v-for="q in projectStore.interrupt.questions" :key="q">{{ q }}</li>
      </ul>
      <textarea v-model="reply" placeholder="输入你的回复..."></textarea>
      <div class="actions">
        <button class="btn-secondary" @click="handleReject">拒绝</button>
        <button class="btn-primary" @click="handleApprove">确认</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useProjectStore } from '../stores/project.js'
import { useWebSocket } from '../composables/useWebSocket.js'

const projectStore = useProjectStore()
const { send } = useWebSocket()
const reply = ref('')

function handleApprove() {
  send({ type: 'resume', thread_id: projectStore.currentProject?.id, decision: 'approved', clarification: reply.value })
  projectStore.interrupt = null
  reply.value = ''
}
function handleReject() {
  send({ type: 'resume', thread_id: projectStore.currentProject?.id, decision: 'rejected', clarification: reply.value })
  projectStore.interrupt = null
  reply.value = ''
}
</script>

<style scoped>
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.dialog { background: var(--bg); border-radius: 12px; padding: 32px; max-width: 480px; width: 90%; box-shadow: 0 8px 32px rgba(0,0,0,0.15); }
.dialog h3 { margin-bottom: 12px; }
.dialog p { font-size: 14px; color: var(--text-dim); margin-bottom: 16px; }
.dialog ul { margin-bottom: 16px; padding-left: 20px; font-size: 13px; color: var(--text-dim); }
.dialog textarea { width: 100%; border: 1px solid var(--border); border-radius: var(--radius); padding: 10px; font-size: 13px; margin-bottom: 16px; resize: vertical; min-height: 60px; }
.actions { display: flex; gap: 8px; justify-content: flex-end; }
.btn-primary { background: var(--primary); color: #fff; border: none; padding: 8px 20px; border-radius: var(--radius); cursor: pointer; }
.btn-secondary { background: transparent; border: 1px solid var(--border); padding: 8px 20px; border-radius: var(--radius); cursor: pointer; }
</style>
```

```vue
<!-- frontend/src/components/OutputPanel.vue -->
<template>
  <div v-if="Object.keys(projectStore.files).length > 0" class="output-panel">
    <div class="output-title">生成文件</div>
    <div v-for="(content, path) in projectStore.files" :key="path" class="file-item">
      <span class="file-icon">📄</span>
      <span class="file-name">{{ path }}</span>
      <button class="btn-sm" @click="preview(path, content)">预览</button>
    </div>
    <div v-if="previewContent" class="preview-box">
      <div class="preview-header">
        <span>{{ previewPath }}</span>
        <button @click="previewContent = null">✕</button>
      </div>
      <pre>{{ previewContent }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useProjectStore } from '../stores/project.js'

const projectStore = useProjectStore()
const previewPath = ref(null)
const previewContent = ref(null)

function preview(path, content) {
  previewPath.value = path
  previewContent.value = content
}
</script>

<style scoped>
.output-panel { margin-top: 20px; padding: 16px; background: var(--bg); border-radius: var(--radius); border: 1px solid var(--border); }
.output-title { font-size: 12px; font-weight: 600; color: var(--text-dim); margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px; }
.file-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 13px; }
.file-icon { font-size: 14px; }
.file-name { flex: 1; font-family: monospace; }
.btn-sm { font-size: 11px; padding: 2px 8px; border: 1px solid var(--border); border-radius: 4px; background: transparent; cursor: pointer; }
.preview-box { margin-top: 12px; border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.preview-header { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: var(--bg-panel); font-size: 12px; }
.preview-header button { background: none; border: none; cursor: pointer; font-size: 14px; }
.preview-box pre { padding: 12px; font-size: 12px; overflow: auto; max-height: 200px; background: var(--bg); margin: 0; }
</style>
```

```vue
<!-- frontend/src/components/DiscussionPanel.vue -->
<template>
  <div v-if="discussionMessages.length > 0" class="discussion-panel">
    <div class="discussion-title" @click="expanded = !expanded">
      💬 Proposer-Critic 讨论 ({{ discussionMessages.length }} 条)
      <span>{{ expanded ? '收起' : '展开' }}</span>
    </div>
    <div v-if="expanded" class="discussion-body">
      <div v-for="(msg, i) in discussionMessages" :key="i" :class="['disc-item', msg.name?.includes('critic') ? 'critic' : 'proposer']">
        <div class="disc-label">{{ msg.name?.includes('critic') ? '审查' : '方案' }}</div>
        <div class="disc-content">{{ msg.content }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useProjectStore } from '../stores/project.js'

const projectStore = useProjectStore()
const expanded = ref(false)

const discussionMessages = computed(() =>
  projectStore.messages.filter(m => m.name && (m.name.includes('proposer') || m.name.includes('critic')))
)
</script>

<style scoped>
.discussion-panel { margin-top: 20px; background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius); }
.discussion-title { padding: 12px 16px; font-size: 13px; font-weight: 600; cursor: pointer; display: flex; justify-content: space-between; }
.discussion-title span { font-size: 12px; color: var(--primary); font-weight: 400; }
.discussion-body { padding: 0 16px 16px; }
.disc-item { padding: 8px 12px; margin-bottom: 8px; border-radius: 6px; font-size: 12px; line-height: 1.5; }
.disc-item.proposer { background: #EFF6FF; border-left: 3px solid var(--primary); }
.disc-item.critic { background: #FFF1F2; border-left: 3px solid var(--error); }
.disc-label { font-size: 11px; font-weight: 600; margin-bottom: 4px; color: var(--text-dim); }
</style>
```

- [ ] **Step 5: 运行测试，验证通过**

```bash
cd frontend && npm test -- InterruptDialog.test.js OutputPanel.test.js
```

Expected: 5 tests passed

---

### Task 12: LoadingBar + AgentStatusBar + App.vue（TDD）

**Files:**
- Create: `frontend/src/components/LoadingBar.vue`
- Create: `frontend/src/components/AgentStatusBar.vue`
- Modify: `frontend/src/App.vue`
- Create: `frontend/src/__tests__/components/LoadingBar.test.js`

- [ ] **Step 1: 写失败的测试**

```javascript
// frontend/src/__tests__/components/LoadingBar.test.js
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useWsStore } from '../../stores/websocket.js'
import LoadingBar from '../../components/LoadingBar.vue'

describe('LoadingBar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('未重连时不显示', () => {
    const wrapper = mount(LoadingBar)
    expect(wrapper.find('.reconnect-bar').exists()).toBe(false)
  })

  it('重连中时显示提示', async () => {
    const store = useWsStore()
    store.reconnecting = true

    const wrapper = mount(LoadingBar)
    expect(wrapper.text()).toContain('正在重连')
  })
})
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd frontend && npm test -- LoadingBar.test.js
```

Expected: FAIL

- [ ] **Step 3: 写最小实现**

```vue
<!-- frontend/src/components/LoadingBar.vue -->
<template>
  <div v-if="wsStore.reconnecting" class="reconnect-bar">
    连接断开，正在重连...
  </div>
</template>

<script setup>
import { useWsStore } from '../stores/websocket.js'
const wsStore = useWsStore()
</script>

<style scoped>
.reconnect-bar { position: fixed; top: 0; left: 0; right: 0; z-index: 9999; background: var(--warning); color: #fff; text-align: center; padding: 6px; font-size: 13px; }
</style>
```

```vue
<!-- frontend/src/components/AgentStatusBar.vue -->
<template>
  <div v-if="hasActiveProject" class="status-bar">
    <div v-for="agent in projectStore.agentList" :key="agent.name" :class="['status-dot', agent.status]" :title="`${agent.name}: ${agent.status}`"></div>
    <span class="status-text">{{ statusText }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useProjectStore } from '../stores/project.js'

const projectStore = useProjectStore()
const hasActiveProject = computed(() => Object.keys(projectStore.agentStatus).length > 0)
const statusText = computed(() => {
  const running = projectStore.agentList.find(a => a.status === 'running')
  return running ? `${running.name} 执行中...` : projectStore.agentList.every(a => a.status === 'done') ? '已完成' : '就绪'
})
</script>

<style scoped>
.status-bar { display: flex; align-items: center; gap: 6px; padding: 0 16px; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--border); }
.status-dot.running { background: var(--primary); animation: pulse 1.5s infinite; }
.status-dot.done { background: var(--success); }
.status-dot.error { background: var(--error); }
.status-text { font-size: 12px; color: var(--text-dim); }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
</style>
```

```vue
<!-- frontend/src/App.vue -->
<template>
  <LoadingBar />
  <div class="app-layout">
    <nav v-if="authStore.isLoggedIn" class="navbar">
      <div class="nav-brand">Blueprint</div>
      <div class="nav-links">
        <router-link to="/">工作台</router-link>
        <router-link to="/projects">项目</router-link>
        <router-link to="/settings">设置</router-link>
      </div>
      <AgentStatusBar />
      <div class="nav-user">
        <span>{{ authStore.username }}</span>
        <button @click="logout">退出</button>
      </div>
    </nav>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth.js'
import { useWebSocket } from './composables/useWebSocket.js'
import LoadingBar from './components/LoadingBar.vue'
import AgentStatusBar from './components/AgentStatusBar.vue'

const authStore = useAuthStore()
const router = useRouter()
const { connect, disconnect } = useWebSocket()

onMounted(() => { if (authStore.isLoggedIn) connect() })
onUnmounted(() => { disconnect() })

function logout() {
  disconnect()
  authStore.clearAuth()
  router.push('/login')
}
</script>

<style scoped>
.app-layout { min-height: 100vh; display: flex; flex-direction: column; }
.navbar { display: flex; align-items: center; justify-content: space-between; padding: 12px 24px; background: var(--bg); border-bottom: 1px solid var(--border); }
.nav-brand { font-weight: 700; font-size: 18px; color: var(--primary); }
.nav-links { display: flex; gap: 16px; }
.nav-links a { color: var(--text-dim); text-decoration: none; font-size: 14px; }
.nav-links a.router-link-active { color: var(--primary); }
.nav-user { display: flex; align-items: center; gap: 12px; font-size: 13px; color: var(--text-dim); }
.nav-user button { background: none; border: 1px solid var(--border); border-radius: var(--radius); padding: 4px 12px; cursor: pointer; font-size: 12px; }
.main-content { flex: 1; }
</style>
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
cd frontend && npm test -- LoadingBar.test.js
```

Expected: 2 tests passed

---

### Task 13: LoginPage（TDD）

**Files:**
- Modify: `frontend/src/pages/LoginPage.vue`
- Create: `frontend/src/__tests__/pages/LoginPage.test.js`

- [ ] **Step 1: 写失败的测试**

```javascript
// frontend/src/__tests__/pages/LoginPage.test.js
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import LoginPage from '../../pages/LoginPage.vue'

vi.mock('../../composables/useWebSocket.js', () => ({
  useWebSocket: () => ({ send: vi.fn(), connect: vi.fn(), disconnect: vi.fn() }),
}))

vi.mock('../../api/index.js', () => ({
  api: {
    login: vi.fn().mockResolvedValue({ token: 'abc', username: 'user' }),
    register: vi.fn().mockResolvedValue({ token: 'abc', username: 'user' }),
  },
}))

describe('LoginPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('显示登录表单', () => {
    const wrapper = mount(LoginPage)
    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
    expect(wrapper.find('button[type="submit"]').exists()).toBe(true)
  })

  it('默认显示登录模式', () => {
    const wrapper = mount(LoginPage)
    expect(wrapper.find('button[type="submit"]').text()).toBe('登录')
    expect(wrapper.text()).toContain('没有账号？去注册')
  })

  it('点击切换到注册模式', async () => {
    const wrapper = mount(LoginPage)
    await wrapper.find('.toggle').trigger('click')
    expect(wrapper.find('button[type="submit"]').text()).toBe('注册')
  })
})
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd frontend && npm test -- LoginPage.test.js
```

Expected: FAIL

- [ ] **Step 3: 写最小实现**

```vue
<!-- frontend/src/pages/LoginPage.vue -->
<template>
  <div class="login-container">
    <div class="login-card">
      <h1>Blueprint</h1>
      <p class="subtitle">AI 开发团队</p>
      <form @submit.prevent="handleSubmit">
        <div class="form-group">
          <label>用户名</label>
          <input v-model="username" type="text" placeholder="输入用户名" required />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="输入密码" required />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" :disabled="loading">{{ isRegister ? '注册' : '登录' }}</button>
        <p class="toggle" @click="isRegister = !isRegister">
          {{ isRegister ? '已有账号？去登录' : '没有账号？去注册' }}
        </p>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { useWebSocket } from '../composables/useWebSocket.js'
import { api } from '../api/index.js'

const router = useRouter()
const authStore = useAuthStore()
const { connect } = useWebSocket()

const username = ref('')
const password = ref('')
const isRegister = ref(false)
const loading = ref(false)
const error = ref('')

async function handleSubmit() {
  loading.value = true
  error.value = ''
  try {
    const fn = isRegister.value ? api.register : api.login
    const data = await fn(username.value, password.value)
    authStore.setAuth(data.token, data.username || username.value)
    connect()
    router.push('/')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--bg-panel); }
.login-card { background: var(--bg); padding: 40px; border-radius: 12px; box-shadow: var(--shadow); width: 360px; }
.login-card h1 { color: var(--primary); margin-bottom: 4px; }
.subtitle { color: var(--text-dim); margin-bottom: 24px; font-size: 14px; }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; font-size: 13px; color: var(--text-dim); margin-bottom: 6px; }
.form-group input { width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius); font-size: 14px; }
.form-group input:focus { outline: none; border-color: var(--primary); }
.error { color: var(--error); font-size: 13px; margin-bottom: 12px; }
button[type="submit"] { width: 100%; padding: 10px; background: var(--primary); color: #fff; border: none; border-radius: var(--radius); font-size: 14px; cursor: pointer; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.toggle { text-align: center; margin-top: 12px; font-size: 13px; color: var(--primary); cursor: pointer; }
</style>
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
cd frontend && npm test -- LoginPage.test.js
```

Expected: 3 tests passed

---

### Task 14: WorkbenchPage + 其他页面（TDD）

**Files:**
- Modify: `frontend/src/pages/WorkbenchPage.vue`
- Modify: `frontend/src/pages/SettingsPage.vue`
- Modify: `frontend/src/pages/ProjectsPage.vue`
- Modify: `frontend/src/pages/ProjectDetailPage.vue`
- Create: `frontend/src/__tests__/pages/WorkbenchPage.test.js`

- [ ] **Step 1: 写失败的测试**

```javascript
// frontend/src/__tests__/pages/WorkbenchPage.test.js
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import WorkbenchPage from '../../pages/WorkbenchPage.vue'

vi.mock('../../composables/useWebSocket.js', () => ({
  useWebSocket: () => ({ send: vi.fn(), connect: vi.fn(), disconnect: vi.fn() }),
}))

describe('WorkbenchPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染流程面板和聊天面板', () => {
    const wrapper = mount(WorkbenchPage)
    expect(wrapper.find('.flow-panel').exists()).toBe(true)
    expect(wrapper.find('.chat-panel').exists()).toBe(true)
  })

  it('包含 5 个 Agent 卡片', () => {
    const wrapper = mount(WorkbenchPage)
    expect(wrapper.findAll('.agent-card')).toHaveLength(5)
  })
})
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd frontend && npm test -- WorkbenchPage.test.js
```

Expected: FAIL

- [ ] **Step 3: 写最小实现（WorkbenchPage）**

```vue
<!-- frontend/src/pages/WorkbenchPage.vue -->
<template>
  <div class="workbench">
    <FlowPanel />
    <ChatPanel />
  </div>
</template>

<script setup>
import FlowPanel from '../components/FlowPanel.vue'
import ChatPanel from '../components/ChatPanel.vue'
</script>

<style scoped>
.workbench { display: flex; height: calc(100vh - 49px); }
</style>
```

- [ ] **Step 4: 实现其他页面（SettingsPage, ProjectsPage, ProjectDetailPage）**

参考 Task 12 的实现代码（同之前的计划，此处不重复）。

- [ ] **Step 5: 运行测试，验证通过**

```bash
cd frontend && npm test
```

Expected: ALL tests passed

---

### Task 15: WebSocket Composable（TDD）

**Files:**
- Create: `frontend/src/composables/useWebSocket.js`
- Create: `frontend/src/__tests__/composables/useWebSocket.test.js`

- [ ] **Step 1: 写失败的测试**

```javascript
// frontend/src/__tests__/composables/useWebSocket.test.js
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWsStore } from '../../stores/websocket.js'
import { useAuthStore } from '../../stores/auth.js'

// Mock WebSocket
class MockWebSocket {
  constructor(url) { this.url = url; this.readyState = 1; this.onopen = null; this.onmessage = null; this.onclose = null; this.onerror = null; }
  send(data) { this.sent = data; }
  close() { this.closed = true; }
}

describe('useWebSocket', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('connect 设置 isConnected', async () => {
    global.WebSocket = MockWebSocket
    const authStore = useAuthStore()
    authStore.setAuth('test-token', 'user')

    const { useWebSocket } = await import('../../composables/useWebSocket.js')
    const { connect } = useWebSocket()
    connect()

    const wsStore = useWsStore()
    // 模拟 onopen
    expect(wsStore.isConnected).toBe(false) // 还没触发 onopen
  })

  it('无 token 时不连接', async () => {
    const { useWebSocket } = await import('../../composables/useWebSocket.js')
    const { connect } = useWebSocket()
    connect()

    const wsStore = useWsStore()
    expect(wsStore.isConnected).toBe(false)
  })
})
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
cd frontend && npm test -- useWebSocket.test.js
```

Expected: FAIL

- [ ] **Step 3: 写最小实现**

参考之前计划的 useWebSocket.js 完整代码。

- [ ] **Step 4: 运行测试，验证通过**

```bash
cd frontend && npm test -- useWebSocket.test.js
```

Expected: 2 tests passed

---

### Task 16: 构建 + 部署到 FastAPI

**Files:**
- Modify: `frontend/vite.config.js`（已配置）

- [ ] **Step 1: 运行所有测试**

```bash
cd frontend && npm test
```

Expected: ALL tests passed

- [ ] **Step 2: 构建**

```bash
cd frontend && npm run build
```

Expected: 构建产物输出到 `Blueprint/static/`

- [ ] **Step 3: 验证生产模式**

```bash
cd "c:/Users/lahm/Desktop/Many AgentS"
python -m Blueprint.start
```

访问 `http://localhost:8080`，应看到新的 Vue 3 前端。

- [ ] **Step 4: 删除旧 HTML 文件**

确认新前端工作正常后，删除 `Blueprint/static/` 下的旧 HTML 文件。

---

## 依赖关系

```
Task 1 (项目初始化+测试框架)
    ↓
Task 2 (authStore) → Task 3 (projectStore) → Task 4 (wsStore)
    ↓
Task 5 (main.js) → Task 6 (Router) → Task 7 (API)
    ↓
Task 8 (AgentCard) → Task 9 (FlowPanel) → Task 10 (ChatPanel)
    ↓
Task 11 (Dialogs) → Task 12 (LoadingBar+StatusBar+App.vue)
    ↓
Task 13 (LoginPage) → Task 14 (WorkbenchPage+其他页面)
    ↓
Task 15 (WebSocket composable) → Task 16 (构建部署)
```

## 预计工时

| Task | 内容 | 工时 |
|------|------|------|
| 1 | 项目初始化+测试框架 | 10 分钟 |
| 2-4 | Stores（TDD） | 30 分钟 |
| 5-7 | main.js + Router + API（TDD） | 30 分钟 |
| 8-10 | 组件（TDD） | 40 分钟 |
| 11-12 | Dialogs + App.vue（TDD） | 30 分钟 |
| 13-14 | 页面（TDD） | 40 分钟 |
| 15 | WebSocket composable（TDD） | 20 分钟 |
| 16 | 构建部署 | 10 分钟 |

**总计：约 3.5 小时**
