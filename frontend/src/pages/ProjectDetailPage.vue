<template>
  <div class="detail-page">
    <!-- Page Header -->
    <div class="page-header">
      <button class="btn-back" @click="$router.push('/projects')">&larr; 返回</button>
      <h2 class="page-title">{{ displayName }}</h2>
      <div class="header-actions">
        <button class="btn-action" @click="handleRerun" :disabled="!state">🔄 重新运行</button>
        <button class="btn-action" @click="showEditDialog" :disabled="!state">✏️ 编辑需求</button>
        <button class="btn-action btn-export" @click="handleExport">📤 导出</button>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="pageLoading" class="skeleton-wrap">
      <div class="skeleton-card" v-for="n in 2" :key="n">
        <div class="skeleton-bar skeleton-title"></div>
        <div class="skeleton-bar" v-for="m in 3" :key="m"></div>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="pageError" class="card error-card">
      <div class="error-text">{{ pageError }}</div>
      <button class="btn-retry" @click="loadState">重试</button>
    </div>

    <!-- Cards -->
    <template v-else-if="state">
      <!-- Card 1: Project Info -->
      <div class="card">
        <div class="card-title">📋 项目信息</div>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">名称</span>
            <span class="info-value">{{ state.name || state.requirement || state.project_id }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">状态</span>
            <span class="info-value status-badge" :class="statusClass">{{ state.status }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">迭代</span>
            <span class="info-value">{{ state.iteration }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">心跳</span>
            <span class="info-value">{{ state.last_heartbeat || '-' }}</span>
          </div>
        </div>
        <div class="info-requirement" v-if="state.requirement">
          <span class="info-label">需求</span>
          <div class="requirement-text">{{ state.requirement }}</div>
        </div>
      </div>

      <!-- Card 2: Files -->
      <div class="card">
        <div class="card-title">📁 生成文件</div>
        <template v-if="fileList.length > 0">
          <div class="files-list">
            <div v-for="f in fileList" :key="f.path" class="file-item">
              <span class="file-icon">{{ getFileIcon(f.path) }}</span>
              <span class="file-name clickable" @click="toggleFilePreview(f.path, f.content)">{{ f.path }}</span>
              <button class="btn-sm" @click="downloadSingle(f.path, f.content)">下载</button>
            </div>
          </div>
          <!-- Preview -->
          <div v-if="previewFile" class="preview-box">
            <div class="preview-header">
              <span class="preview-filename">{{ previewFile }}</span>
              <div class="preview-actions">
                <button class="btn-icon" @click="copyContent" title="复制">📋</button>
                <button class="btn-icon" @click="closePreview" title="关闭">&times;</button>
              </div>
            </div>
            <div v-if="previewContent" class="preview-code">
              <pre><code v-html="highlightedContent"></code></pre>
            </div>
            <div v-else class="preview-empty">文件内容为空</div>
          </div>
        </template>
        <div v-else class="empty-text">暂无文件</div>
      </div>

      <!-- Card 3: Dev Log (lazy load) -->
      <div class="card">
        <div class="card-title clickable" @click="toggleConversations">
          💬 开发日志
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
                  <span class="conv-role">{{ msg.role === 'assistant' ? '🤖' : '🔧' }}</span>
                  <div class="conv-content">{{ truncate(msg.content, 500) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Card 4: Execution Summary (lazy load) -->
      <div class="card">
        <div class="card-title clickable" @click="toggleExecutions">
          📊 执行摘要
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
    </template>

    <!-- New Analysis Tabs -->
    <template v-if="state">
      <div class="tab-bar">
        <button class="tab-btn" :class="{ active: activeTab === 'quality' }" @click="activeTab = activeTab === 'quality' ? '' : 'quality'">质量评分</button>
        <button class="tab-btn" :class="{ active: activeTab === 'security' }" @click="activeTab = activeTab === 'security' ? '' : 'security'">安全扫描</button>
        <button class="tab-btn" :class="{ active: activeTab === 'diff' }" @click="activeTab = activeTab === 'diff' ? '' : 'diff'">变更对比</button>
        <button class="tab-btn" :class="{ active: activeTab === 'traces' }" @click="activeTab = activeTab === 'traces' ? '' : 'traces'">Agent追踪</button>
      </div>
      <div class="tab-panel" v-if="activeTab">
        <QualityScore v-if="activeTab === 'quality'" :projectId="projectId" />
        <SecurityReport v-if="activeTab === 'security'" :projectId="projectId" />
        <DiffViewer v-if="activeTab === 'diff'" :projectId="projectId" />
        <AgentTracePanel v-if="activeTab === 'traces'" :projectId="projectId" />
      </div>
    </template>

    <!-- Edit Dialog -->
    <div v-if="editDialogVisible" class="dialog-overlay" @click.self="editDialogVisible = false">
      <div class="dialog">
        <div class="dialog-title">编辑需求</div>
        <textarea v-model="editText" rows="6" class="dialog-textarea"></textarea>
        <div class="dialog-actions">
          <button class="btn-cancel" @click="editDialogVisible = false">取消</button>
          <button class="btn-confirm" @click="handleEditConfirm">确认并运行</button>
        </div>
      </div>
    </div>

    <!-- Rerun Confirm Dialog -->
    <div v-if="rerunDialogVisible" class="dialog-overlay" @click.self="rerunDialogVisible = false">
      <div class="dialog">
        <div class="dialog-title">重新运行</div>
        <p class="dialog-text">将用相同需求创建新项目，是否继续？</p>
        <div class="dialog-actions">
          <button class="btn-cancel" @click="rerunDialogVisible = false">取消</button>
          <button class="btn-confirm" @click="handleRerunConfirm">确认</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { saveAs } from 'file-saver'
import { api } from '../api/index.js'
import { useProjectStore } from '../stores/project.js'
import { useFilePreview } from '../composables/useFilePreview.js'
import QualityScore from '../components/QualityScore.vue'
import SecurityReport from '../components/SecurityReport.vue'
import DiffViewer from '../components/DiffViewer.vue'
import AgentTracePanel from '../components/AgentTracePanel.vue'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const projectId = route.params.id

const { previewFile, previewContent, highlightedContent, openPreview, closePreview, copyContent } = useFilePreview()

// Page-level state
const pageLoading = ref(true)
const pageError = ref(null)
const state = ref(null)

// Card 3: Conversations
const conversationsExpanded = ref(false)
const conversationsLoading = ref(false)
const conversationsError = ref(null)
const conversationsLoaded = ref(false)
const conversations = ref([])

// Card 4: Executions
const executionsExpanded = ref(false)
const executionsLoading = ref(false)
const executionsError = ref(null)
const executionsLoaded = ref(false)
const executions = ref([])

// Dialogs
const editDialogVisible = ref(false)
const editText = ref('')
const rerunDialogVisible = ref(false)

// Tabs for new panels
const activeTab = ref('')

// Computed
const displayName = computed(() => {
  if (!state.value) return projectId
  return state.value.name || state.value.requirement || projectId
})

const fileList = computed(() => {
  if (!state.value?.files) return []
  return Object.entries(state.value.files).map(([path, content]) => ({ path, content }))
})

const statusClass = computed(() => {
  const s = state.value?.status
  if (!s) return ''
  if (['delivered', 'completed', 'saved'].includes(s)) return 'status-good'
  if (['failed', 'error', 'cancelled'].includes(s)) return 'status-bad'
  if (s === 'running') return 'status-running'
  return ''
})

// File icon logic (reuse from OutputPanel)
function getFileIcon(path) {
  if (path.endsWith('.py')) return '🐍'
  if (path.endsWith('.html')) return '🌐'
  if (path.endsWith('.css')) return '🎨'
  if (path.endsWith('.js') || path.endsWith('.ts')) return '⚡'
  if (path.endsWith('.json')) return '📋'
  if (path.endsWith('.sh') || path.endsWith('.bat')) return '⚙️'
  return '📄'
}

// Agent label
function label(name) {
  const labels = { pm: 'PM', architect: 'Architect', developer: 'Developer', tester: 'Tester', reviewer: 'Reviewer' }
  return labels[name] || name
}

// Truncate helper
function truncate(text, max) {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '...' : text
}

// Format time
function formatTime(ts) {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleString('zh-CN')
  } catch {
    return ts
  }
}

// File preview toggle
function toggleFilePreview(path, content) {
  if (previewFile.value === path) {
    closePreview()
  } else {
    openPreview(path, content)
  }
}

// Download single file
function downloadSingle(path, content) {
  const blob = new Blob([content], { type: 'text/plain' })
  saveAs(blob, path.split('/').pop())
}

// Load state (Card 1 + Card 2)
async function loadState() {
  pageLoading.value = true
  pageError.value = null
  try {
    state.value = await api.getProjectState(projectId)
  } catch (e) {
    pageError.value = e.message || '加载失败'
  } finally {
    pageLoading.value = false
  }
}

// Load conversations (Card 3)
async function loadConversations() {
  conversationsLoading.value = true
  conversationsError.value = null
  try {
    const data = await api.getProjectConversations(projectId)
    conversations.value = data.conversations || []
    conversationsLoaded.value = true
  } catch (e) {
    conversationsError.value = e.message || '加载对话历史失败'
  } finally {
    conversationsLoading.value = false
  }
}

// Load executions (Card 4)
async function loadExecutions() {
  executionsLoading.value = true
  executionsError.value = null
  try {
    const data = await api.getProjectExecutions(projectId)
    executions.value = data.executions || []
    executionsLoaded.value = true
  } catch (e) {
    executionsError.value = e.message || '加载执行摘要失败'
  } finally {
    executionsLoading.value = false
  }
}

// Toggle conversations card
function toggleConversations() {
  conversationsExpanded.value = !conversationsExpanded.value
  if (conversationsExpanded.value && !conversationsLoaded.value) {
    loadConversations()
  }
}

// Toggle executions card
function toggleExecutions() {
  executionsExpanded.value = !executionsExpanded.value
  if (executionsExpanded.value && !executionsLoaded.value) {
    loadExecutions()
  }
}

// Action: Rerun
function handleRerun() {
  rerunDialogVisible.value = true
}

function handleRerunConfirm() {
  rerunDialogVisible.value = false
  const req = state.value?.requirement || ''
  projectStore.pendingRequirement = req
  sessionStorage.setItem('pendingRequirement', req)
  router.push('/')
}

// Action: Edit
function showEditDialog() {
  editText.value = state.value?.requirement || ''
  editDialogVisible.value = true
}

function handleEditConfirm() {
  editDialogVisible.value = false
  const req = editText.value.trim()
  if (!req) return
  projectStore.pendingRequirement = req
  sessionStorage.setItem('pendingRequirement', req)
  router.push('/')
}

// Action: Export
function handleExport() {
  window.open(api.exportProject(projectId))
}

// Init
onMounted(() => {
  loadState()
})
</script>

<style scoped>
.detail-page {
  padding: 24px 32px;
  max-width: 960px;
  margin: 0 auto;
}

/* Page Header */
.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.btn-back {
  background: none;
  border: none;
  color: var(--primary);
  cursor: pointer;
  font-size: 13px;
  padding: 4px 8px;
}
.btn-back:hover { text-decoration: underline; }
.page-title {
  font-size: 18px;
  font-weight: 600;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.btn-action {
  font-size: 12px;
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: transparent;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-action:hover:not(:disabled) {
  border-color: var(--primary);
  color: var(--primary);
}
.btn-action:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-export {
  border-color: var(--primary);
  color: var(--primary);
}
.btn-export:hover:not(:disabled) {
  background: var(--primary);
  color: #fff;
}

/* Card */
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
.card-title.clickable {
  cursor: pointer;
  user-select: none;
}
.card-title.clickable:hover { color: var(--primary); }
.toggle-icon { font-size: 12px; color: var(--text-dim); }

/* Info Card */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}
.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.info-label {
  font-size: 11px;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.info-value {
  font-size: 14px;
  font-weight: 500;
}
.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  width: fit-content;
}
.status-good { background: rgba(34, 197, 94, 0.15); color: #22c55e; }
.status-bad { background: rgba(239, 68, 68, 0.15); color: #ef4444; }
.status-running { background: rgba(59, 130, 246, 0.15); color: #3b82f6; }
.info-requirement { margin-top: 8px; }
.requirement-text {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: var(--text);
  background: var(--bg);
  padding: 12px;
  border-radius: var(--radius);
  max-height: 200px;
  overflow-y: auto;
}

/* Files Card */
.files-list { display: flex; flex-direction: column; gap: 4px; }
.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
}
.file-icon { font-size: 14px; }
.file-name { flex: 1; font-family: monospace; }
.file-name.clickable { cursor: pointer; color: var(--primary); }
.file-name.clickable:hover { text-decoration: underline; }
.btn-sm {
  font-size: 11px;
  padding: 2px 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
}
.btn-sm:hover { border-color: var(--primary); color: var(--primary); }

/* Preview */
.preview-box {
  margin-top: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: var(--bg-panel);
  font-size: 13px;
  font-weight: 500;
}
.preview-filename { font-family: monospace; }
.preview-actions { display: flex; gap: 4px; }
.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  color: var(--text-dim);
  padding: 2px 4px;
  border-radius: 4px;
}
.btn-icon:hover { color: var(--primary); background: var(--bg); }
.preview-code {
  max-height: 400px;
  overflow: auto;
  background: var(--bg);
}
.preview-code pre { padding: 16px; margin: 0; font-size: 13px; line-height: 1.6; }
.preview-code code { font-family: monospace; }
.preview-empty { padding: 24px; text-align: center; color: var(--text-dim); font-size: 13px; }

/* Conversations */
.conversations-list { display: flex; flex-direction: column; gap: 16px; }
.conv-group {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
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
.conv-messages {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}
.conv-msg {
  display: flex;
  gap: 8px;
  font-size: 13px;
  line-height: 1.5;
}
.conv-role { flex-shrink: 0; }
.conv-content {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: monospace;
  font-size: 12px;
}
.conv-msg-tool .conv-content {
  color: var(--text-dim);
}

/* Executions Timeline */
.exec-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
  position: relative;
}
.exec-item {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  position: relative;
}
.exec-item:not(:last-child) {
  border-bottom: 1px solid var(--border);
}
.exec-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-top: 4px;
  flex-shrink: 0;
}
.dot-success { background: #22c55e; }
.dot-other { background: #ef4444; }
.exec-body { flex: 1; min-width: 0; }
.exec-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.exec-agent { font-size: 13px; font-weight: 600; color: var(--primary); }
.exec-iter { font-size: 11px; color: var(--text-dim); }
.exec-status {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
}
.status-success { background: rgba(34, 197, 94, 0.15); color: #22c55e; }
.status-other { background: rgba(239, 68, 68, 0.15); color: #ef4444; }
.exec-time { font-size: 11px; color: var(--text-dim); margin-left: auto; }
.exec-summary { font-size: 13px; line-height: 1.5; }

/* Skeleton */
.skeleton-wrap { display: flex; flex-direction: column; gap: 16px; }
.skeleton-card {
  background: var(--bg-panel, var(--bg));
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.skeleton-inner { display: flex; flex-direction: column; gap: 12px; padding: 8px 0; }
.skeleton-bar {
  height: 14px;
  background: linear-gradient(90deg, var(--border) 25%, transparent 50%, var(--border) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
}
.skeleton-title { width: 40%; height: 18px; }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

/* Error / Empty */
.error-card {
  display: flex;
  align-items: center;
  gap: 12px;
}
.error-inner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}
.error-text { color: #ef4444; font-size: 13px; }
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
.empty-text {
  font-size: 13px;
  color: var(--text-dim);
  padding: 16px 0;
  text-align: center;
}

/* Tabs */
.tab-bar { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.tab-btn { font-size: 13px; padding: 8px 16px; border: 1px solid var(--border); border-radius: var(--radius); background: transparent; cursor: pointer; transition: all 0.15s; }
.tab-btn:hover { border-color: var(--primary); color: var(--primary); }
.tab-btn.active { background: var(--primary); color: #fff; border-color: var(--primary); }
.tab-panel { background: var(--bg-panel, var(--bg)); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; margin-bottom: 16px; }

/* Dialog */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.dialog {
  background: var(--bg-panel, #1a1a2e);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  width: 480px;
  max-width: 90vw;
}
.dialog-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
}
.dialog-text {
  font-size: 14px;
  color: var(--text);
  margin-bottom: 16px;
  line-height: 1.5;
}
.dialog-textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
  resize: vertical;
  font-family: inherit;
  margin-bottom: 16px;
}
.dialog-textarea:focus { outline: none; border-color: var(--primary); }
.dialog-actions { display: flex; justify-content: flex-end; gap: 8px; }
.btn-cancel {
  padding: 8px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: transparent;
  cursor: pointer;
  font-size: 13px;
}
.btn-confirm {
  padding: 8px 16px;
  border: 1px solid var(--primary);
  border-radius: var(--radius);
  background: var(--primary);
  color: #fff;
  cursor: pointer;
  font-size: 13px;
}
.btn-confirm:hover { opacity: 0.9; }
</style>
