# Workbench UX 改进实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将通讯页面从纯文本聊天升级为结构化 Agent 输出 + 暂停/继续 + 保存命名 + 代码预览

**Architecture:** 组件拆分策略 — ChatPanel 拆为 ChatHeader/MessageList/ChatInput，新增 AgentOutputCard/SaveDialog 组件，提取 useFilePreview composable。后端新增 pause/stop/resume WebSocket 消息处理。

**Tech Stack:** Vue 3 + Pinia + highlight.js + FastAPI + WebSocket

---

## 文件结构

### 新增文件

| 文件 | 职责 |
|------|------|
| `frontend/src/composables/useFilePreview.js` | 文件预览逻辑 + 语法高亮 |
| `frontend/src/components/AgentOutputCard.vue` | Agent 输出结构化卡片 |
| `frontend/src/components/SaveDialog.vue` | 保存命名弹窗 |
| `frontend/src/components/ChatHeader.vue` | 操作栏（暂停/继续/保存/清空/新建） |
| `frontend/src/__tests__/composables/useFilePreview.test.js` | useFilePreview 测试 |
| `frontend/src/__tests__/components/AgentOutputCard.test.js` | AgentOutputCard 测试 |
| `frontend/src/__tests__/components/SaveDialog.test.js` | SaveDialog 测试 |
| `frontend/src/__tests__/components/ChatHeader.test.js` | ChatHeader 测试 |
| `devteam/tests/test_websocket_pause.py` | pause/stop/resume 后端测试 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `frontend/src/stores/project.js` | 新增 isPaused/isRunning/saveDialogVisible/autoSaveName/agentStartTime |
| `frontend/src/composables/useWebSocket.js` | 新增 paused/resumed/stopped/heartbeat 消息处理 |
| `frontend/src/components/ChatPanel.vue` | 拆分，引用 ChatHeader/SaveDialog/AgentOutputCard |
| `frontend/src/components/AgentCard.vue` | 可交互（点击展开/折叠 + 耗时） |
| `frontend/src/components/IterationInfo.vue` | 进度条加粗 + 变色 |
| `frontend/src/components/OutputPanel.vue` | 文件预览（useFilePreview） |
| `devteam/api/websocket.py` | pause/stop/resume 消息处理 + 心跳 + 节点边界检查 |
| `devteam/api/projects.py` | POST 新增 name 字段 + GET 返回 name |
| `frontend/package.json` | 新增 highlight.js 依赖 |

---

### Task 1: useFilePreview composable

**Files:**
- Create: `frontend/src/composables/useFilePreview.js`
- Create: `frontend/src/__tests__/composables/useFilePreview.test.js`

- [ ] **Step 1: 安装 highlight.js**

```bash
cd frontend && npm install highlight.js
```

- [ ] **Step 2: 写失败测试**

```js
// frontend/src/__tests__/composables/useFilePreview.test.js
import { describe, it, expect } from 'vitest'
import { useFilePreview } from '../../composables/useFilePreview.js'

describe('useFilePreview', () => {
  it('openPreview 设置文件名和内容', () => {
    const { previewFile, previewContent, openPreview } = useFilePreview()
    openPreview('main.py', 'print("hello")')
    expect(previewFile.value).toBe('main.py')
    expect(previewContent.value).toBe('print("hello")')
  })

  it('openPreview 生成语法高亮内容', () => {
    const { highlightedContent, openPreview } = useFilePreview()
    openPreview('main.py', 'print("hello")')
    expect(highlightedContent.value).toContain('hljs')
  })

  it('closePreview 清空所有状态', () => {
    const { previewFile, previewContent, highlightedContent, openPreview, closePreview } = useFilePreview()
    openPreview('main.py', 'print("hello")')
    closePreview()
    expect(previewFile.value).toBeNull()
    expect(previewContent.value).toBe('')
    expect(highlightedContent.value).toBe('')
  })

  it('copyContent 复制原始内容到剪贴板', async () => {
    const { openPreview, copyContent, previewContent } = useFilePreview()
    openPreview('main.py', 'print("hello")')
    // mock clipboard
    let copied = ''
    Object.assign(navigator, { clipboard: { writeText: async (t) => { copied = t } } })
    await copyContent()
    expect(copied).toBe('print("hello")')
  })

  it('未知扩展名用 highlightAuto', () => {
    const { highlightedContent, openPreview } = useFilePreview()
    openPreview('file.xyz', 'some content')
    expect(highlightedContent.value).toBeTruthy()
  })
})
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd frontend && npx vitest run src/__tests__/composables/useFilePreview.test.js
```

- [ ] **Step 4: 实现 useFilePreview**

```js
// frontend/src/composables/useFilePreview.js
import { ref } from 'vue'
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

- [ ] **Step 5: 运行测试确认通过**

```bash
cd frontend && npx vitest run src/__tests__/composables/useFilePreview.test.js
```

- [ ] **Step 6: 提交**

```bash
git add frontend/src/composables/useFilePreview.js frontend/src/__tests__/composables/useFilePreview.test.js frontend/package.json frontend/package-lock.json
git commit -m "feat: add useFilePreview composable with highlight.js syntax highlighting"
```

---

### Task 2: AgentOutputCard 组件

**Files:**
- Create: `frontend/src/components/AgentOutputCard.vue`
- Create: `frontend/src/__tests__/components/AgentOutputCard.test.js`

- [ ] **Step 1: 写失败测试**

```js
// frontend/src/__tests__/components/AgentOutputCard.test.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AgentOutputCard from '../../components/AgentOutputCard.vue'

describe('AgentOutputCard', () => {
  it('PM 消息显示用户故事数', () => {
    const wrapper = mount(AgentOutputCard, {
      props: { msg: { name: 'pm', content: '已拆分 3 个用户故事', data: { data: { user_stories: [{}, {}, {}], features: [{}, {}] } } } }
    })
    expect(wrapper.text()).toContain('3 个用户故事')
    expect(wrapper.text()).toContain('2 个功能特性')
  })

  it('Developer 消息显示文件列表', () => {
    const wrapper = mount(AgentOutputCard, {
      props: { msg: { name: 'developer', content: '完成', data: { data: { files: { 'main.py': 'x=1', 'index.html': '<html>' } } } } }
    })
    expect(wrapper.text()).toContain('main.py')
    expect(wrapper.text()).toContain('index.html')
  })

  it('Tester 消息显示测试结果', () => {
    const wrapper = mount(AgentOutputCard, {
      props: { msg: { name: 'tester', content: '测试完成', data: { data: { test_passed: false, test_results: [{ summary: '2 passed, 1 failed' }] } } } }
    })
    expect(wrapper.text()).toContain('2 passed, 1 failed')
  })

  it('Reviewer 消息显示审查结论', () => {
    const wrapper = mount(AgentOutputCard, {
      props: { msg: { name: 'reviewer', content: '审查不通过', data: { data: { review_approved: false, review_comments: [{ severity: 'important', description: '问题' }] } } } }
    })
    expect(wrapper.text()).toContain('问题')
  })

  it('未知 agent 退化为纯文本', () => {
    const wrapper = mount(AgentOutputCard, {
      props: { msg: { name: 'unknown', content: '纯文本消息', data: {} } }
    })
    expect(wrapper.text()).toContain('纯文本消息')
  })

  it('data 缺失时不崩溃', () => {
    const wrapper = mount(AgentOutputCard, {
      props: { msg: { name: 'developer', content: '内容' } }
    })
    expect(wrapper.text()).toContain('内容')
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 AgentOutputCard**

```vue
<!-- frontend/src/components/AgentOutputCard.vue -->
<template>
  <div class="agent-output-card" :style="{ borderLeftColor: color }">
    <div class="card-header">
      <span class="card-agent" :style="{ color }">{{ icon }} {{ label }}</span>
      <span class="card-time" v-if="duration">{{ duration }}</span>
    </div>
    <div class="card-body">
      <!-- PM -->
      <template v-if="msg.name === 'pm'">
        <div>{{ userStories.length }} 个用户故事 · {{ features.length }} 个功能特性</div>
      </template>
      <!-- Architect -->
      <template v-else-if="msg.name === 'architect'">
        <div>{{ apiDefinitions.length }} 个 API · {{ dataModels.length }} 个数据模型</div>
      </template>
      <!-- Developer -->
      <template v-else-if="msg.name === 'developer'">
        <div v-if="fileList.length">{{ fileList.length }} 个文件</div>
        <div class="file-list">
          <span v-for="f in fileList" :key="f" class="file-tag">📝 {{ f }}</span>
        </div>
        <div v-if="keyDecisions.length" class="decisions">
          <span v-for="d in keyDecisions" :key="d" class="decision-tag">💡 {{ d }}</span>
        </div>
      </template>
      <!-- Tester -->
      <template v-else-if="msg.name === 'tester'">
        <div :class="testPassed ? 'test-pass' : 'test-fail'">
          {{ testPassed ? '✅ 测试通过' : '❌ 测试未通过' }}
        </div>
        <div v-for="(r, i) in testResults" :key="i" class="test-summary">{{ r.summary }}</div>
      </template>
      <!-- Reviewer -->
      <template v-else-if="msg.name === 'reviewer'">
        <div :class="reviewApproved ? 'review-pass' : 'review-fail'">
          {{ reviewApproved ? '✅ 审查通过' : '❌ 审查不通过' }}
        </div>
        <div v-for="(c, i) in reviewComments" :key="i" class="review-comment">
          <span class="severity" :class="c.severity">{{ c.severity }}</span>
          {{ c.description }}
        </div>
      </template>
      <!-- 兜底 -->
      <template v-else>
        <div>{{ msg.content }}</div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ msg: Object })

const data = computed(() => props.msg.data?.data ?? {})
const userStories = computed(() => data.value.user_stories ?? [])
const features = computed(() => data.value.features ?? [])
const apiDefinitions = computed(() => data.value.api_definitions ?? [])
const dataModels = computed(() => data.value.data_models ?? [])
const fileList = computed(() => Object.keys(data.value.files ?? {}))
const keyDecisions = computed(() => data.value.key_decisions ?? [])
const testPassed = computed(() => data.value.test_passed ?? false)
const testResults = computed(() => data.value.test_results ?? [])
const reviewApproved = computed(() => data.value.review_approved ?? false)
const reviewComments = computed(() => data.value.review_comments ?? [])

const colorMap = { pm: '#3B82F6', architect: '#8B5CF6', developer: '#10B981', tester: '#F59E0B', reviewer: '#EC4899' }
const iconMap = { pm: '👤', architect: '🏗️', developer: '💻', tester: '🧪', reviewer: '🔍' }
const labelMap = { pm: 'PM', architect: '架构师', developer: '开发者', tester: '测试员', reviewer: '审查员' }

const color = computed(() => colorMap[props.msg.name] || '#6B7280')
const icon = computed(() => iconMap[props.msg.name] || '🤖')
const label = computed(() => labelMap[props.msg.name] || props.msg.name)
const duration = computed(() => null) // 后续从 agentStartTime 计算
</script>

<style scoped>
.agent-output-card { border-left: 3px solid; border-radius: 8px; padding: 10px 14px; background: var(--bg-panel); border: 1px solid var(--border); margin: 4px 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.card-agent { font-weight: 600; font-size: 12px; }
.card-time { font-size: 11px; color: var(--text-dim); }
.card-body { font-size: 12px; color: var(--text); line-height: 1.6; }
.file-list { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.file-tag { background: var(--bg); padding: 2px 8px; border-radius: 4px; font-size: 11px; }
.decisions { margin-top: 4px; }
.decision-tag { display: inline-block; margin-right: 8px; font-size: 11px; }
.test-pass { color: #10B981; } .test-fail { color: #EF4444; }
.review-pass { color: #10B981; } .review-fail { color: #EF4444; }
.review-comment { font-size: 11px; margin-top: 2px; }
.severity { font-weight: 600; margin-right: 4px; }
.severity.critical { color: #EF4444; } .severity.important { color: #F59E0B; } .severity.minor { color: #6B7280; }
.test-summary { font-size: 11px; margin-top: 2px; }
</style>
```

- [ ] **Step 4: 运行测试确认通过**

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/AgentOutputCard.vue frontend/src/__tests__/components/AgentOutputCard.test.js
git commit -m "feat: add AgentOutputCard component for structured agent output display"
```

---

### Task 3: SaveDialog 组件

**Files:**
- Create: `frontend/src/components/SaveDialog.vue`
- Create: `frontend/src/__tests__/components/SaveDialog.test.js`

- [ ] **Step 1: 写失败测试**

```js
// frontend/src/__tests__/components/SaveDialog.test.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SaveDialog from '../../components/SaveDialog.vue'

describe('SaveDialog', () => {
  it('显示默认名称', () => {
    const wrapper = mount(SaveDialog, { props: { visible: true, defaultName: '紫色计算器' } })
    expect(wrapper.find('input').element.value).toBe('紫色计算器')
  })

  it('确认时 emit save 事件', async () => {
    const wrapper = mount(SaveDialog, { props: { visible: true, defaultName: '测试项目' } })
    await wrapper.find('input').setValue('我的项目')
    await wrapper.find('.btn-confirm').trigger('click')
    expect(wrapper.emitted('save')[0]).toEqual(['我的项目'])
  })

  it('取消时 emit update:visible', async () => {
    const wrapper = mount(SaveDialog, { props: { visible: true, defaultName: '测试' } })
    await wrapper.find('.btn-cancel').trigger('click')
    expect(wrapper.emitted('update:visible')[0]).toEqual([false])
  })

  it('空名称时用默认名称', async () => {
    const wrapper = mount(SaveDialog, { props: { visible: true, defaultName: '默认名称' } })
    await wrapper.find('input').setValue('')
    await wrapper.find('.btn-confirm').trigger('click')
    expect(wrapper.emitted('save')[0]).toEqual(['默认名称'])
  })

  it('名称超过 50 字截断', async () => {
    const wrapper = mount(SaveDialog, { props: { visible: true, defaultName: '测试' } })
    const longName = 'a'.repeat(60)
    await wrapper.find('input').setValue(longName)
    await wrapper.find('.btn-confirm').trigger('click')
    expect(wrapper.emitted('save')[0][0].length).toBeLessThanOrEqual(50)
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

- [ ] **Step 3: 实现 SaveDialog**

```vue
<!-- frontend/src/components/SaveDialog.vue -->
<template>
  <div v-if="visible" class="save-overlay" @click.self="cancel">
    <div class="save-dialog">
      <div class="dialog-title">💾 保存项目</div>
      <div class="dialog-label">项目名称</div>
      <input
        v-model="name"
        class="dialog-input"
        maxlength="50"
        placeholder="输入项目名称..."
        @keydown.enter="confirm"
      />
      <div class="dialog-hint">自动生成，可修改</div>
      <div v-if="error" class="dialog-error">{{ error }}</div>
      <div class="dialog-actions">
        <button class="btn-cancel" @click="cancel">取消</button>
        <button class="btn-confirm" @click="confirm">保存</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({ visible: Boolean, defaultName: String })
const emit = defineEmits(['update:visible', 'save'])

const name = ref('')
const error = ref('')

watch(() => props.visible, (v) => {
  if (v) { name.value = props.defaultName || ''; error.value = '' }
})

function confirm() {
  const finalName = (name.value || props.defaultName || '未命名项目').slice(0, 50)
  if (!finalName.trim()) { error.value = '名称不能为空'; return }
  emit('save', finalName)
}

function cancel() { emit('update:visible', false) }
</script>

<style scoped>
.save-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.save-dialog { background: var(--bg); border-radius: 12px; padding: 24px; width: 360px; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.dialog-title { font-weight: 600; font-size: 16px; margin-bottom: 16px; }
.dialog-label { font-size: 13px; color: var(--text-dim); margin-bottom: 6px; }
.dialog-input { width: 100%; border: 2px solid var(--primary); border-radius: 8px; padding: 10px 14px; font-size: 14px; box-sizing: border-box; outline: none; }
.dialog-hint { font-size: 11px; color: var(--text-dim); margin-top: 4px; }
.dialog-error { font-size: 12px; color: #EF4444; margin-top: 8px; }
.dialog-actions { display: flex; gap: 8px; margin-top: 20px; justify-content: flex-end; }
.btn-cancel { background: var(--bg-panel); border: 1px solid var(--border); border-radius: 8px; padding: 8px 20px; cursor: pointer; font-size: 13px; }
.btn-confirm { background: var(--primary); color: #fff; border: none; border-radius: 8px; padding: 8px 20px; cursor: pointer; font-size: 13px; }
</style>
```

- [ ] **Step 4: 运行测试确认通过**

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/SaveDialog.vue frontend/src/__tests__/components/SaveDialog.test.js
git commit -m "feat: add SaveDialog component for project naming"
```

---

### Task 4: AgentCard 可交互

**Files:**
- Modify: `frontend/src/components/AgentCard.vue`
- Modify: `frontend/src/stores/project.js` (agentStartTime)

**现有 AgentCard 结构：**
- template：`.agent-card` > `.agent-bar` + `.agent-body`（icon + info + dot）
- script：props `name`/`status`，computed `label`/`icon`/`statusText`
- style：27 行 CSS，含 running/done/error 状态

- [ ] **Step 1: project store 新增 agentStartTime**

```js
// frontend/src/stores/project.js — state 新增
agentStartTime: {},
```

- [ ] **Step 2: 改造 AgentCard template**

在 `.agent-body` 下方新增可折叠详情区：

```vue
<template>
  <div :class="['agent-card', `agent-${name}`, status]" @click="toggleExpand">
    <div class="agent-bar"></div>
    <div class="agent-body">
      <div class="agent-icon">{{ icon }}</div>
      <div class="agent-info">
        <div class="agent-name">{{ label }}</div>
        <div class="agent-status-text">{{ statusText }}<span v-if="elapsed"> · {{ elapsed }}</span></div>
      </div>
      <div class="agent-dot" :class="status"></div>
    </div>
    <div v-if="expanded" class="agent-detail">
      <slot name="detail">
        <div class="detail-summary">{{ summary || '暂无详情' }}</div>
      </slot>
    </div>
  </div>
</template>
```

- [ ] **Step 3: 改造 AgentCard script**

```vue
<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { useProjectStore } from '../stores/project.js'

const props = defineProps({
  name: String,
  status: { type: String, default: 'waiting' },
  summary: { type: String, default: '' }
})

const projectStore = useProjectStore()
const expanded = ref(false)
const now = ref(Date.now())
let timer = null

function toggleExpand() { expanded.value = !expanded.value }

// 执行中每秒更新计时
const elapsed = computed(() => {
  if (props.status !== 'running') return ''
  const start = projectStore.agentStartTime[props.name]
  if (!start) return ''
  const secs = Math.floor((now.value - start) / 1000)
  return secs < 60 ? `${secs}s` : `${Math.floor(secs / 60)}m${secs % 60}s`
})

// 启动/停止计时器
import { watch } from 'vue'
watch(() => props.status, (s) => {
  if (s === 'running') {
    projectStore.agentStartTime[props.name] = Date.now()
    timer = setInterval(() => { now.value = Date.now() }, 1000)
  } else {
    if (timer) { clearInterval(timer); timer = null }
  }
}, { immediate: true })

onUnmounted(() => { if (timer) clearInterval(timer) })

// ... 现有 labels/icons/statusTexts 不变 ...
</script>
```

- [ ] **Step 4: 新增 CSS**

```css
.agent-detail { padding: 0 16px 14px; border-top: 1px solid var(--border); }
.detail-summary { font-size: 11px; color: var(--text-dim); line-height: 1.5; padding-top: 8px; }
.agent-card { cursor: pointer; }
.agent-card:hover { border-color: var(--primary); }
```

- [ ] **Step 5: 运行现有测试确认不破坏**

```bash
cd frontend && npx vitest run
```

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/AgentCard.vue frontend/src/stores/project.js
git commit -m "feat: make AgentCard interactive with expand/collapse and duration"
```

---

### Task 5: IterationInfo 进度可视化

**Files:**
- Modify: `frontend/src/components/IterationInfo.vue`

- [ ] **Step 1: 改造进度条样式**

读取 `frontend/src/components/IterationInfo.vue`，改造：
- 进度条加粗 4px → 8px
- 动态颜色：<50% 绿 #4caf50，50-80% 黄 #ff9800，>80% 红 #f44336
- 始终显示（移除 `v-if="iteration > 0"`，改为 0 时也显示）

- [ ] **Step 2: 运行现有测试确认不破坏**

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/IterationInfo.vue
git commit -m "feat: enhance IterationInfo with color-coded progress bar"
```

---

### Task 6: 后端 WebSocket pause/stop/resume

**Files:**
- Modify: `devteam/api/websocket.py`
- Create: `devteam/tests/test_websocket_pause.py`

- [ ] **Step 1: 写失败测试**

```python
# devteam/tests/test_websocket_pause.py
import pytest
import asyncio
import threading
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

def test_pause_handler_exists():
    """pause 消息处理逻辑应存在"""
    import devteam.api.websocket as ws_mod
    source = inspect.getsource(ws_mod.ws_project)
    assert 'msg_type == "pause"' in source
    assert 'stop_event.set()' in source

def test_resume_handler_exists():
    """resume_execution 消息处理逻辑应存在"""
    import devteam.api.websocket as ws_mod
    source = inspect.getsource(ws_mod.ws_project)
    assert 'msg_type == "resume_execution"' in source
    assert 'stop_event.clear()' in source

def test_stop_handler_exists():
    """stop 消息处理逻辑应存在"""
    import devteam.api.websocket as ws_mod
    source = inspect.getsource(ws_mod.ws_project)
    assert 'msg_type == "stop"' in source

def test_heartbeat_function_exists():
    """_send_heartbeat 函数应存在且为 async"""
    from devteam.api.websocket import _send_heartbeat
    assert callable(_send_heartbeat)
    assert inspect.iscoroutinefunction(_send_heartbeat)

@pytest.mark.asyncio
async def test_heartbeat_sends_messages():
    """_send_heartbeat 应在暂停期间发送心跳"""
    from devteam.api.websocket import _send_heartbeat

    ws = AsyncMock()
    paused = [True]

    async def is_paused():
        return paused[0]

    # 启动心跳，2 次后取消
    async def run_heartbeat():
        await _send_heartbeat(ws, "test-proj", is_paused)

    task = asyncio.create_task(run_heartbeat())
    await asyncio.sleep(0.3)  # 等待至少一次心跳
    paused[0] = False  # 取消暂停
    await asyncio.sleep(0.2)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # 应该发送了至少一次心跳
    assert ws.send_json.call_count >= 1
    call_args = ws.send_json.call_args[0][0]
    assert call_args["type"] == "heartbeat"

def test_node_boundary_check_in_graph():
    """_run_async 中应在节点边界检查 stop_event"""
    import devteam.api.websocket as ws_mod
    source = inspect.getsource(ws_mod._run_graph_sync)
    assert 'stop_event.is_set()' in source

def test_pause_state_variable_exists():
    """ws_project 中应有 paused 状态变量"""
    import devteam.api.websocket as ws_mod
    source = inspect.getsource(ws_mod.ws_project)
    assert 'paused' in source
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "c:\Users\lahm\Desktop\Many AgentS" && python -m pytest devteam/tests/test_websocket_pause.py -v
```

- [ ] **Step 3: 实现 pause/stop/resume**

在 `devteam/api/websocket.py` 的 `ws_project` 函数中：

1. 新增 `paused = False` 和 `heartbeat_task = None` 变量
2. 新增 `_send_heartbeat` 异步函数
3. 在消息循环中新增 pause/resume_execution/stop 处理
4. 在 `_run_async` 的 `async for event` 循环中添加 stop_event 检查

- [ ] **Step 4: 运行测试确认通过**

```bash
cd "c:\Users\lahm\Desktop\Many AgentS" && python -m pytest devteam/tests/test_websocket_pause.py -v
```

- [ ] **Step 5: 运行全量测试**

```bash
cd "c:\Users\lahm\Desktop\Many AgentS" && python -m pytest devteam/tests/ -q
```

- [ ] **Step 6: 提交**

```bash
git add devteam/api/websocket.py devteam/tests/test_websocket_pause.py
git commit -m "feat: add pause/stop/resume WebSocket handling with heartbeat"
```

---

### Task 7a: ChatHeader 组件（独立）

**Files:**
- Create: `frontend/src/components/ChatHeader.vue`
- Create: `frontend/src/__tests__/components/ChatHeader.test.js`

- [ ] **Step 1: 写 ChatHeader 测试**

```js
// frontend/src/__tests__/components/ChatHeader.test.js
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '../../stores/project.js'
import ChatHeader from '../../components/ChatHeader.vue'

describe('ChatHeader', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('空闲状态显示保存/清空/新建，无暂停', () => {
    const wrapper = mount(ChatHeader)
    expect(wrapper.find('[title="保存项目"]').exists()).toBe(true)
    expect(wrapper.find('[title="清空聊天"]').exists()).toBe(true)
    expect(wrapper.find('[title="新建对话"]').exists()).toBe(true)
    expect(wrapper.find('[title="暂停"]').exists()).toBe(false)
    expect(wrapper.find('[title="继续"]').exists()).toBe(false)
  })

  it('运行中显示暂停按钮', () => {
    const store = useProjectStore()
    store.isRunning = true
    store.isPaused = false
    const wrapper = mount(ChatHeader)
    expect(wrapper.find('[title="暂停"]').exists()).toBe(true)
    expect(wrapper.find('[title="继续"]').exists()).toBe(false)
  })

  it('已暂停显示继续和停止按钮', () => {
    const store = useProjectStore()
    store.isRunning = true
    store.isPaused = true
    const wrapper = mount(ChatHeader)
    expect(wrapper.find('[title="继续"]').exists()).toBe(true)
    expect(wrapper.find('[title="停止"]').exists()).toBe(true)
    expect(wrapper.find('[title="暂停"]').exists()).toBe(false)
  })

  it('点击暂停 emit pause 事件', async () => {
    const store = useProjectStore()
    store.isRunning = true
    const wrapper = mount(ChatHeader)
    await wrapper.find('[title="暂停"]').trigger('click')
    expect(wrapper.emitted('pause')).toBeTruthy()
  })

  it('点击继续 emit resume 事件', async () => {
    const store = useProjectStore()
    store.isRunning = true
    store.isPaused = true
    const wrapper = mount(ChatHeader)
    await wrapper.find('[title="继续"]').trigger('click')
    expect(wrapper.emitted('resume')).toBeTruthy()
  })

  it('点击停止 emit stop 事件', async () => {
    const store = useProjectStore()
    store.isRunning = true
    store.isPaused = true
    const wrapper = mount(ChatHeader)
    await wrapper.find('[title="停止"]').trigger('click')
    expect(wrapper.emitted('stop')).toBeTruthy()
  })
})
```

- [ ] **Step 2: 实现 ChatHeader**

```vue
<!-- frontend/src/components/ChatHeader.vue -->
<template>
  <div class="chat-header">
    <span class="chat-title">通讯频道</span>
    <div class="chat-actions">
      <!-- 运行中：暂停 + 保存 -->
      <template v-if="isRunning && !isPaused">
        <button class="btn-icon btn-pause" @click="$emit('pause')" title="暂停">⏸</button>
      </template>
      <!-- 已暂停：继续 + 停止 -->
      <template v-else-if="isRunning && isPaused">
        <button class="btn-icon btn-resume" @click="$emit('resume')" title="继续">▶</button>
        <button class="btn-icon btn-stop" @click="$emit('stop')" title="停止">⏹</button>
      </template>
      <!-- 通用按钮 -->
      <button class="btn-icon" @click="$emit('save')" title="保存项目">💾</button>
      <button class="btn-icon" @click="$emit('clear')" title="清空聊天">🗑️</button>
      <button class="btn-icon" @click="$emit('new')" title="新建对话">✚</button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useProjectStore } from '../stores/project.js'

const projectStore = useProjectStore()
const isRunning = computed(() => projectStore.isRunning)
const isPaused = computed(() => projectStore.isPaused)

defineEmits(['pause', 'resume', 'stop', 'save', 'clear', 'new'])
</script>

<style scoped>
.chat-header { padding: 12px 16px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
.chat-title { font-size: 14px; font-weight: 600; color: var(--text-dim); }
.chat-actions { display: flex; gap: 6px; }
.btn-icon { width: 28px; height: 28px; border-radius: 6px; background: transparent; border: 1px solid var(--border); color: var(--text-dim); cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 13px; transition: all 0.15s; }
.btn-icon:hover { background: var(--bg-panel); border-color: var(--primary); color: var(--primary); }
.btn-pause { color: #ff9800; border-color: #ff980044; }
.btn-pause:hover { background: #fff8f0; border-color: #ff9800; }
.btn-resume { color: #4caf50; border-color: #4caf5044; }
.btn-resume:hover { background: #f0fff0; border-color: #4caf50; }
.btn-stop { color: #e74c3c; border-color: #e74c3c44; }
.btn-stop:hover { background: #ffeaea; border-color: #e74c3c; }
</style>
```

- [ ] **Step 3: 运行测试**

```bash
cd frontend && npx vitest run src/__tests__/components/ChatHeader.test.js
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/ChatHeader.vue frontend/src/__tests__/components/ChatHeader.test.js
git commit -m "feat: add ChatHeader component with pause/stop/resume buttons"
```

### Task 7b: store + WebSocket 消息处理

**Files:**
- Modify: `frontend/src/stores/project.js`
- Modify: `frontend/src/composables/useWebSocket.js`

- [ ] **Step 1: project store 新增字段**

```js
// frontend/src/stores/project.js — state 新增
isPaused: false,
isRunning: false,
saveDialogVisible: false,
autoSaveName: '',
agentStartTime: {},
```

- [ ] **Step 2: useWebSocket 新增消息处理**

在 `handleMessage` 的 switch 中新增：

```js
case 'paused':
  projectStore.isPaused = true
  break
case 'resumed':
  projectStore.isPaused = false
  break
case 'stopped':
  projectStore.isRunning = false
  projectStore.isPaused = false
  projectStore.addMessage({ role: 'system', name: 'system', content: '⏹ 任务已停止' })
  break
case 'heartbeat':
  break
```

修改 `agent_start`：`projectStore.isRunning = true`
修改 `project_done` 和 `error`：`projectStore.isRunning = false`

- [ ] **Step 3: 运行前端测试**

```bash
cd frontend && npx vitest run
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/stores/project.js frontend/src/composables/useWebSocket.js
git commit -m "feat: add pause/resume/stop state to project store and WebSocket handler"
```

### Task 7c: ChatPanel 拆分引用 ChatHeader

**Files:**
- Modify: `frontend/src/components/ChatPanel.vue`

- [ ] **Step 1: ChatPanel 引入 ChatHeader**

在 ChatPanel template 中，用 `<ChatHeader />` 替换原有的操作栏 div。监听 ChatHeader 的事件：

```vue
<ChatHeader
  @pause="send({ type: 'pause' })"
  @resume="send({ type: 'resume_execution' })"
  @stop="send({ type: 'stop' })"
  @save="saveProject"
  @clear="clearChat"
  @new="newChat"
/>
```

删除 ChatPanel 中原有的 `.chat-header`、`.chat-actions`、`.btn-icon` 相关 template 和 style。

- [ ] **Step 2: 运行全部前端测试**

```bash
cd frontend && npx vitest run
```

- [ ] **Step 3: 构建**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/ChatPanel.vue
git commit -m "refactor: ChatPanel uses ChatHeader component"
```

---

### Task 8: 保存命名（前端 + 后端）

**Files:**
- Modify: `devteam/api/projects.py`
- Modify: `frontend/src/stores/project.js`
- Modify: `frontend/src/components/ChatPanel.vue`

- [ ] **Step 1: 后端 POST 新增 name 字段**

在 `devteam/api/projects.py` 的 `ProjectCreate` 模型中新增 `name: Optional[str] = None`，在 `create_project` 中存入 meta.json。

- [ ] **Step 2: 后端 GET 返回 name 字段**

在 `list_projects` 返回结果中新增 `name`。

- [ ] **Step 3: 前端 saveProject 传 name**

在 `frontend/src/stores/project.js` 的 `saveProject` 中传入 `name` 字段。

- [ ] **Step 4: ChatPanel 集成 SaveDialog**

点击保存按钮时显示 SaveDialog，确认后调 saveProject(name)。

- [ ] **Step 5: 运行后端测试**

```bash
cd "c:\Users\lahm\Desktop\Many AgentS" && python -m pytest devteam/tests/test_file_api.py -v
```

- [ ] **Step 6: 构建前端**

```bash
cd frontend && npm run build
```

- [ ] **Step 7: 提交**

```bash
git add devteam/api/projects.py frontend/src/stores/project.js frontend/src/components/ChatPanel.vue
git commit -m "feat: add project naming with SaveDialog and backend name field"
```

---

### Task 9: OutputPanel 文件预览

**Files:**
- Modify: `frontend/src/components/OutputPanel.vue`

- [ ] **Step 1: 集成 useFilePreview**

在 OutputPanel 中引入 `useFilePreview`，点击文件名时调用 `openPreview(path, content)`。

- [ ] **Step 2: 添加预览区域**

在文件列表下方显示预览区：语法高亮代码 + 复制按钮。

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
git add frontend/src/components/OutputPanel.vue
git commit -m "feat: add inline file preview with syntax highlighting to OutputPanel"
```

---

### Task 10: 异常状态处理

**Files:**
- Modify: `frontend/src/components/ChatHeader.vue`
- Modify: `frontend/src/components/SaveDialog.vue`
- Modify: `frontend/src/components/OutputPanel.vue`

- [ ] **Step 1: WebSocket 断连提示**

ChatHeader 中引入 wsStore，`wsStore.isConnected` 为 false 时显示"连接断开"文字提示，暂停/继续按钮加 `disabled` 属性。

- [ ] **Step 2: 保存失败提示**

SaveDialog 中 catch 错误时设 `error.value = err.message`，显示红色提示，不关闭弹窗。

- [ ] **Step 3: 文件预览空内容占位符**

OutputPanel 预览区 `previewContent` 为空时显示"文件内容为空"占位符。

- [ ] **Step 4: 运行全部测试 + 构建**

```bash
cd frontend && npx vitest run && npm run build
cd "c:\Users\lahm\Desktop\Many AgentS" && python -m pytest devteam/tests/ -q
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/ChatHeader.vue frontend/src/components/SaveDialog.vue frontend/src/components/OutputPanel.vue
git commit -m "feat: add error state handling for disconnect, save failure, empty preview"
```

---

### 依赖图

```
Task 1 (useFilePreview) ─────────────────────────→ Task 9 (OutputPanel 预览)
Task 2 (AgentOutputCard) ──┐
Task 3 (SaveDialog) ───────┤
                           ├──→ Task 7c (ChatPanel 拆分) ──→ Task 8 (保存命名)
Task 7a (ChatHeader) ──────┤
Task 7b (store+WS) ────────┘
Task 4 (AgentCard 可交互) —— 独立
Task 5 (IterationInfo) —— 独立
Task 6 (后端 WS) —— 独立
Task 10 (异常兜底) —— 依赖 Task 1-9
Task 11 (集成测试) —— 依赖 Task 1-10
```

**可并行：** Task 1, 2, 3, 4, 5, 6, 7a, 7b 可同时开工。

### Task 11: 集成测试

- [ ] **Step 1: 启动服务器手动测试**

```bash
cd "c:\Users\lahm\Desktop\Many AgentS" && python -m devteam.start
```

测试清单：
1. 发送需求 → Agent 输出用卡片显示
2. 点击 Agent 卡片 → 展开详情
3. 迭代进度条变色
4. 生成文件后点击预览 → 语法高亮
5. 点击保存 → 弹窗命名 → 确认 → 跳转项目详情
6. 项目页面显示项目名称
7. 运行中点暂停 → 暂停 → 点继续 → 继续
8. 暂停中点停止 → 停止

- [ ] **Step 2: 运行全量测试**

```bash
cd "c:\Users\lahm\Desktop\Many AgentS" && python -m pytest devteam/tests/ -q
cd frontend && npx vitest run
```

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "feat: Workbench UX improvements - structured output, pause/resume, save naming, file preview"
```
