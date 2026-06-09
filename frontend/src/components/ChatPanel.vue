<template>
  <div class="chat-panel">
    <div class="chat-header">
      <span class="chat-title">通讯频道</span>
      <div class="chat-actions">
        <button class="btn-icon" @click="clearChat" title="清空聊天">🗑️</button>
        <button class="btn-icon" @click="newChat" title="新建对话">✚</button>
      </div>
    </div>
    <div class="messages" ref="messagesRef">
      <div v-for="(msg, i) in projectStore.messages" :key="i" :class="['message', `msg-${msg.name || msg.role}`]">
        <div class="msg-avatar">{{ avatar(msg.name || msg.role) }}</div>
        <div class="msg-body">
          <div class="msg-header">
            <span class="msg-name" :style="{ color: color(msg.name) }">{{ label(msg.name) }}</span>
            <span class="msg-time">{{ time(msg.timestamp) }}</span>
            <button v-if="msg.name === 'user'" class="btn-retry" @click="retryMessage(msg.content)" title="重试">🔄</button>
          </div>
          <div class="msg-content">{{ formatMessageContent(msg) }}</div>
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
import { useWebSocket, setActiveProject } from '../composables/useWebSocket.js'

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

function formatMessageContent(msg) {
  // tool 消息：显示执行结果
  if (msg.role === 'tool') {
    try {
      const result = JSON.parse(msg.content)
      if (result.stdout !== undefined) {
        const output = result.stdout.slice(0, 300)
        return `📤 输出：${output}${result.stdout.length > 300 ? '...' : ''}`
      }
      if (result.error) return `❌ ${result.error}`
      if (result.success) return `✅ 已写入 ${result.path}`
      if (result.content) return result.content.slice(0, 300)
      if (result.status === 'completed') return `✅ ${result.summary || '完成'}`
      return msg.content.slice(0, 200)
    } catch {
      return msg.content.slice(0, 200)
    }
  }

  // assistant 消息带 tool_calls：显示操作描述
  if (msg.tool_calls && msg.tool_calls.length > 0) {
    const actions = msg.tool_calls.map(tc => {
      const name = tc.function?.name || tc.name || 'tool'
      try {
        const args = JSON.parse(tc.function?.arguments || '{}')
        if (name === 'file_write') return `📝 写入 ${args.path || '?'}`
        if (name === 'file_read') return `📖 读取 ${args.path || '?'}`
        if (name === 'execute_python') return '▶️ 执行代码'
        if (name === 'done') return '✅ 完成'
        return `🔧 ${name}`
      } catch { return `🔧 ${name}` }
    })
    return actions.join('，')
  }

  return msg.content || ''
}

function sendMessage() {
  const text = inputText.value.trim()
  if (!text) return
  const projectId = 'proj-' + Date.now()
  setActiveProject(projectId)
  projectStore.addMessage({ role: 'user', name: 'user', content: text })
  send({ type: 'start_project', requirement: text, project_id: projectId })
  inputText.value = ''
}

function clearChat() {
  setActiveProject(null)
  projectStore.messages = []
}

function newChat() {
  setActiveProject(null)
  projectStore.reset()
  send({ type: 'cancel' })
}

function retryMessage(content) {
  const projectId = 'proj-' + Date.now()
  setActiveProject(projectId)
  projectStore.reset()
  projectStore.addMessage({ role: 'user', name: 'user', content })
  send({ type: 'start_project', requirement: content, project_id: projectId })
}

watch(() => projectStore.messages.length, () => {
  nextTick(() => { if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight })
})
</script>

<style scoped>
.chat-panel { display: flex; flex-direction: column; height: 100%; }
.chat-header { padding: 12px 16px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
.chat-title { font-size: 14px; font-weight: 600; color: var(--text-dim); }
.chat-actions { display: flex; gap: 6px; }
.btn-icon { width: 28px; height: 28px; border-radius: 6px; background: transparent; border: 1px solid var(--border); color: var(--text-dim); cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 13px; transition: all 0.15s; }
.btn-icon:hover { background: var(--bg-panel); border-color: var(--primary); color: var(--primary); }
.btn-retry { background: none; border: none; cursor: pointer; font-size: 12px; opacity: 0; transition: opacity 0.15s; padding: 0 4px; }
.message:hover .btn-retry { opacity: 0.6; }
.btn-retry:hover { opacity: 1; }
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
