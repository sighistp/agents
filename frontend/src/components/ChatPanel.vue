<template>
  <div class="chat-panel">
    <ChatHeader
      @pause="send({ type: 'pause' })"
      @resume="send({ type: 'resume_execution' })"
      @stop="send({ type: 'stop' })"
      @save="showSaveDialog"
      @clear="clearChat"
      @new="newChat"
    />
    <SaveDialog
      v-model:visible="projectStore.saveDialogVisible"
      :default-name="projectStore.autoSaveName"
      :error="saveError"
      @save="handleSave"
    />
    <div class="messages" ref="messagesRef">
      <!-- 精简/全量切换 -->
      <div v-if="projectStore.currentProject?.id" class="view-toggle">
        <button :class="{ active: viewMode === 'brief' }" @click="switchView('brief')">精简</button>
        <button :class="{ active: viewMode === 'full' }" @click="switchView('full')">全量</button>
      </div>
      <div v-for="(msg, i) in displayMessages" :key="i" :class="['message', `msg-${msg.name || msg.role}`]">
        <!-- Agent 结构化输出卡片 -->
        <AgentOutputCard
          v-if="isAgentMessage(msg)"
          :msg="{ ...msg, data: { data: projectStore.agentOutputs[msg.name] } }"
        />
        <!-- 普通消息（用户/系统/tool） -->
        <template v-else>
          <div class="msg-avatar">{{ avatar(msg.name || msg.role) }}</div>
          <div class="msg-body">
            <div class="msg-header">
              <span class="msg-name" :class="colorClass(msg.name)">{{ label(msg.name) }}</span>
              <span class="msg-time">{{ time(msg.timestamp) }}</span>
              <button v-if="msg.name === 'user'" class="btn-retry" @click="retryMessage(msg.content)" title="重试">↻</button>
            </div>
            <div class="msg-content">{{ formatMessageContent(msg) }}</div>
          </div>
        </template>
      </div>
    </div>
    <div class="chat-input">
      <textarea v-model="inputText" @keydown.enter.exact.prevent="sendMessage" placeholder="描述你的需求..." rows="1"></textarea>
      <button @click="sendMessage" :disabled="!inputText.trim()">▶</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useProjectStore } from '../stores/project.js'
import { useWebSocket, setActiveProject } from '../composables/useWebSocket.js'
import { api } from '../api/index.js'
import ChatHeader from './ChatHeader.vue'
import SaveDialog from './SaveDialog.vue'
import AgentOutputCard from './AgentOutputCard.vue'

const AGENT_NAMES = ['pm', 'architect', 'developer', 'tester', 'reviewer']
function isAgentMessage(msg) {
  return AGENT_NAMES.includes(msg.name) && projectStore.agentOutputs[msg.name]
}

const projectStore = useProjectStore()
const { send } = useWebSocket()
const inputText = ref('')
const messagesRef = ref(null)
const saveError = ref('')

// 精简/全量切换
const viewMode = ref('brief')  // 'brief' | 'full'
const fullMessages = ref([])

const displayMessages = computed(() => {
  if (viewMode.value === 'full') return fullMessages.value
  return projectStore.messages
})

async function switchView(mode) {
  viewMode.value = mode
  if (mode === 'full') {
    const projectId = projectStore.currentProject?.id
    if (projectId) {
      try {
        const data = await api.getProjectConversations(projectId)
        // Flatten conversations into message list
        const msgs = []
        if (data?.conversations) {
          for (const conv of data.conversations) {
            msgs.push({ role: 'system', name: conv.agent_name, content: `--- ${conv.agent_name} (迭代 ${conv.iteration}) ---`, timestamp: conv.created_at })
            for (const m of (conv.messages || [])) {
              msgs.push({ role: m.role, name: m.name || conv.agent_name, content: m.content || '', timestamp: conv.created_at })
            }
          }
        }
        fullMessages.value = msgs
      } catch (e) {
        console.error('Failed to load conversations:', e)
        fullMessages.value = [{ role: 'system', name: 'system', content: '加载全量对话失败' }]
      }
    }
  }
}

const avatarMap = { pm: '👤', architect: '🏗️', developer: '💻', tester: '🧪', reviewer: '🔍', system: '🤖', user: '👤', pm_proposer: '👤', pm_critic: '🔍', arch_proposer: '🏗️', arch_critic: '🔍', developer_critic: '🔍' }
const colorClassMap = { pm: 'color-pm', architect: 'color-architect', developer: 'color-developer', tester: 'color-tester', reviewer: 'color-reviewer', system: 'color-system', user: 'color-user', pm_proposer: 'color-pm', pm_critic: 'color-reviewer', arch_proposer: 'color-architect', arch_critic: 'color-reviewer', developer_critic: 'color-reviewer' }
const labelMap = { pm: 'PM', architect: '架构师', developer: '开发者', tester: '测试员', reviewer: '审查员', system: '系统', user: '用户', pm_proposer: 'PM·方案', pm_critic: 'PM·审查', arch_proposer: '架构师·方案', arch_critic: '架构师·审查', developer_critic: '开发·审查' }

function avatar(name) { return avatarMap[name] || '🤖' }
function colorClass(name) { return colorClassMap[name] || 'color-system' }
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

function autoGenerateName(requirement) {
  if (!requirement) return '未命名项目'
  const isChinese = /[一-鿿]/.test(requirement)
  const maxLen = isChinese ? 15 : 30
  if (requirement.length <= maxLen) return requirement
  return requirement.slice(0, maxLen) + '...'
}

function sendMessage() {
  const text = inputText.value.trim()
  if (!text) return
  const projectId = 'proj-' + Date.now()
  setActiveProject(projectId)
  projectStore.currentProject = { id: projectId, requirement: text }
  projectStore.autoSaveName = autoGenerateName(text)
  projectStore.addMessage({ role: 'user', name: 'user', content: text })
  send({ type: 'start_project', requirement: text, project_id: projectId })
  inputText.value = ''
}

function showSaveDialog() {
  projectStore.saveDialogVisible = true
}

async function handleSave(name) {
  saveError.value = ''
  const ok = await projectStore.saveProject(name)
  if (ok) {
    projectStore.saveDialogVisible = false
    projectStore.addMessage({ role: 'system', name: 'system', content: `💾 项目已保存: ${name}` })
  } else {
    saveError.value = '保存失败，请重试'
    projectStore.addMessage({ role: 'system', name: 'system', content: '❌ 保存失败' })
  }
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
  projectStore.currentProject = { id: projectId, requirement: content }
  projectStore.addMessage({ role: 'user', name: 'user', content })
  send({ type: 'start_project', requirement: content, project_id: projectId })
}

onMounted(() => {
  // Check store first, then sessionStorage as fallback
  const req = projectStore.pendingRequirement || sessionStorage.getItem('pendingRequirement')
  if (req) {
    projectStore.pendingRequirement = null
    sessionStorage.removeItem('pendingRequirement')
    inputText.value = req
    nextTick(() => sendMessage())
  }
})

watch(() => projectStore.messages.length, () => {
  nextTick(() => { if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight })
})
</script>

<style scoped>
.chat-panel { display: flex; flex-direction: column; height: 100%; }
.btn-retry { background: none; border: none; cursor: pointer; font-size: 12px; opacity: 0; transition: opacity 0.15s; padding: 0 4px; }
.message:hover .btn-retry { opacity: 0.6; }
.btn-retry:hover { opacity: 1; }
.view-toggle { display: flex; gap: 4px; padding: 0 16px 8px; border-bottom: 1px solid var(--border); margin-bottom: 8px; }
.view-toggle button { padding: 4px 12px; font-size: 12px; border: 1px solid var(--border); border-radius: 4px; background: var(--bg-panel); color: var(--text-secondary); cursor: pointer; transition: all 0.15s; }
.view-toggle button.active { background: var(--primary); color: #fff; border-color: var(--primary); }
.view-toggle button:hover:not(.active) { background: var(--bg-hover, rgba(128,128,128,0.1)); }
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
.color-pm { color: var(--primary); }
.color-architect { color: #8B5CF6; }
.color-developer { color: var(--success); }
.color-tester { color: var(--warning); }
.color-reviewer { color: #EC4899; }
.color-system { color: var(--text-dim); }
.color-user { color: var(--primary); }
</style>
