<template>
  <div class="log-panel">
    <!-- Conversations -->
    <div class="card">
      <div class="card-title clickable" @click="toggleConversations">
        ◇ 开发日志
        <span class="toggle-icon">{{ conversationsExpanded ? '▾' : '▸' }}</span>
      </div>
      <div v-if="conversationsExpanded">
        <div v-if="conversationsLoading" class="skeleton-inner">
          <div class="skeleton-bar" v-for="n in 3" :key="n"></div>
        </div>
        <div v-else-if="conversationsError" class="error-inner">
          <div class="error-text">{{ conversationsError }}</div>
          <button class="btn-retry" @click="loadConversations">重试</button>
        </div>
        <div v-else-if="conversations.length === 0" class="empty-text">暂无历史对话数据</div>
        <div v-else class="conversations-list">
          <div v-for="(conv, i) in conversations" :key="i" class="conv-group">
            <div class="conv-header">
              <span class="conv-agent">{{ label(conv.agent_name) }}</span>
              <span class="conv-iteration">迭代 {{ conv.iteration }}</span>
            </div>
            <div class="conv-messages">
              <div v-for="(msg, j) in conv.messages" :key="j" class="conv-msg" :class="`conv-msg-${msg.role}`">
                <span class="conv-role">{{ msg.role === 'assistant' ? '○' : '⚙' }}</span>
                <div class="conv-content">{{ truncate(msg.content, 500) }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Executions -->
    <div class="card">
      <div class="card-title clickable" @click="toggleExecutions">
        ▥ 执行摘要
        <span class="toggle-icon">{{ executionsExpanded ? '▾' : '▸' }}</span>
      </div>
      <div v-if="executionsExpanded">
        <div v-if="executionsLoading" class="skeleton-inner">
          <div class="skeleton-bar" v-for="n in 3" :key="n"></div>
        </div>
        <div v-else-if="executionsError" class="error-inner">
          <div class="error-text">{{ executionsError }}</div>
          <button class="btn-retry" @click="loadExecutions">重试</button>
        </div>
        <div v-else-if="executions.length === 0" class="empty-text">暂无执行记录</div>
        <div v-else class="exec-timeline">
          <div v-for="(exec, i) in executions" :key="i" class="exec-item">
            <div class="exec-dot" :class="exec.status === 'success' ? 'dot-success' : 'dot-other'"></div>
            <div class="exec-body">
              <div class="exec-header">
                <span class="exec-agent">{{ label(exec.agent_name) }}</span>
                <span class="exec-iter">迭代 {{ exec.iteration }}</span>
                <span class="exec-status" :class="exec.status === 'success' ? 'status-success' : 'status-other'">{{ exec.status }}</span>
                <span class="exec-time">{{ formatTime(exec.created_at) }}</span>
              </div>
              <div class="exec-summary">{{ exec.result_summary }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../../api/index.js'

const props = defineProps({ projectId: { type: String, required: true } })

// Conversations
const conversationsExpanded = ref(false)
const conversationsLoading = ref(false)
const conversationsError = ref(null)
const conversationsLoaded = ref(false)
const conversations = ref([])

// Executions
const executionsExpanded = ref(false)
const executionsLoading = ref(false)
const executionsError = ref(null)
const executionsLoaded = ref(false)
const executions = ref([])

function label(name) {
  const labels = { pm: 'PM', architect: 'Architect', developer: 'Developer', tester: 'Tester', reviewer: 'Reviewer' }
  return labels[name] || name
}

function truncate(text, max) {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '...' : text
}

function formatTime(ts) {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleString('zh-CN')
  } catch {
    return ts
  }
}

async function loadConversations() {
  conversationsLoading.value = true
  conversationsError.value = null
  try {
    const data = await api.getProjectConversations(props.projectId)
    conversations.value = data.conversations || []
    conversationsLoaded.value = true
  } catch (e) {
    conversationsError.value = e.message || '加载对话历史失败'
  } finally {
    conversationsLoading.value = false
  }
}

async function loadExecutions() {
  executionsLoading.value = true
  executionsError.value = null
  try {
    const data = await api.getProjectExecutions(props.projectId)
    executions.value = data.executions || []
    executionsLoaded.value = true
  } catch (e) {
    executionsError.value = e.message || '加载执行摘要失败'
  } finally {
    executionsLoading.value = false
  }
}

function toggleConversations() {
  conversationsExpanded.value = !conversationsExpanded.value
  if (conversationsExpanded.value && !conversationsLoaded.value) {
    loadConversations()
  }
}

function toggleExecutions() {
  executionsExpanded.value = !executionsExpanded.value
  if (executionsExpanded.value && !executionsLoaded.value) {
    loadExecutions()
  }
}
</script>

<style scoped>
.log-panel { display: flex; flex-direction: column; }
.card {
  background: var(--bg-panel, var(--bg));
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 16px;
}
.card-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.card-title.clickable { cursor: pointer; user-select: none; }
.card-title.clickable:hover { color: var(--primary); }
.toggle-icon { font-size: 12px; color: var(--text-dim); }
.conversations-list { display: flex; flex-direction: column; gap: 16px; }
.conv-group { border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.conv-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: var(--bg);
  font-size: 13px;
  font-weight: 600;
}
.conv-agent { color: var(--primary); }
.conv-iteration { font-size: 11px; color: var(--text-dim); }
.conv-messages { padding: 12px 16px; display: flex; flex-direction: column; gap: 8px; max-height: 300px; overflow-y: auto; }
.conv-msg { display: flex; gap: 8px; font-size: 13px; line-height: 1.5; }
.conv-role { flex-shrink: 0; }
.conv-content { white-space: pre-wrap; word-break: break-word; font-family: monospace; font-size: 12px; }
.conv-msg-tool .conv-content { color: var(--text-dim); }
.exec-timeline { display: flex; flex-direction: column; gap: 0; position: relative; }
.exec-item { display: flex; gap: 12px; padding: 12px 0; position: relative; }
.exec-item:not(:last-child) { border-bottom: 1px solid var(--border); }
.exec-dot { width: 10px; height: 10px; border-radius: 50%; margin-top: 4px; flex-shrink: 0; }
.dot-success { background: var(--success); }
.dot-other { background: var(--error); }
.exec-body { flex: 1; min-width: 0; }
.exec-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; }
.exec-agent { font-size: 13px; font-weight: 600; color: var(--primary); }
.exec-iter { font-size: 11px; color: var(--text-dim); }
.exec-status { font-size: 11px; padding: 1px 6px; border-radius: 3px; }
.status-success { background: rgba(34, 197, 94, 0.15); color: var(--success); }
.status-other { background: rgba(239, 68, 68, 0.15); color: var(--error); }
.exec-time { font-size: 11px; color: var(--text-dim); margin-left: auto; }
.exec-summary { font-size: 13px; line-height: 1.5; }
.skeleton-inner { display: flex; flex-direction: column; gap: 12px; padding: 8px 0; }
.skeleton-bar {
  height: 14px;
  background: linear-gradient(90deg, var(--border) 25%, transparent 50%, var(--border) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
}
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
.error-inner { display: flex; align-items: center; gap: 12px; padding: 8px 0; }
.error-text { color: var(--error); font-size: 13px; }
.btn-retry {
  font-size: 12px;
  padding: 4px 12px;
  border: 1px solid var(--primary);
  border-radius: 4px;
  background: transparent;
  color: var(--primary);
  cursor: pointer;
}
.btn-retry:hover { background: var(--primary); color: #fff; }
.empty-text { font-size: 13px; color: var(--text-dim); padding: 16px 0; text-align: center; }
</style>
