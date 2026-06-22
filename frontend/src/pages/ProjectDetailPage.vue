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

    <!-- Tab Content -->
    <template v-else-if="state">
      <div class="tab-bar" role="tablist">
        <button v-for="t in tabs" :key="t.key" class="tab-btn" :class="{ active: activeTab === t.key }" role="tab" :aria-selected="activeTab === t.key" @click="activeTab = activeTab === t.key ? '' : t.key">
          {{ t.icon }} {{ t.label }}
        </button>
      </div>
      <div class="tab-panel" role="tabpanel">
        <ProjectInfoCard v-if="activeTab === 'info'" :projectData="state" />
        <ProjectFilesPanel v-if="activeTab === 'files'" :projectData="state" />
        <ProjectLogPanel v-if="activeTab === 'log'" :projectId="projectId" />
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
import { api } from '../api/index.js'
import { useProjectStore } from '../stores/project.js'
import ProjectInfoCard from '../components/project/ProjectInfoCard.vue'
import ProjectFilesPanel from '../components/project/ProjectFilesPanel.vue'
import ProjectLogPanel from '../components/project/ProjectLogPanel.vue'
import QualityScore from '../components/QualityScore.vue'
import SecurityReport from '../components/SecurityReport.vue'
import DiffViewer from '../components/DiffViewer.vue'
import AgentTracePanel from '../components/AgentTracePanel.vue'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const projectId = route.params.id

const pageLoading = ref(true)
const pageError = ref(null)
const state = ref(null)

const editDialogVisible = ref(false)
const editText = ref('')
const rerunDialogVisible = ref(false)

const activeTab = ref('info')

const tabs = [
  { key: 'info', icon: '📋', label: '项目信息' },
  { key: 'files', icon: '📁', label: '文件' },
  { key: 'log', icon: '💬', label: '日志' },
  { key: 'quality', icon: '⭐', label: '质量评分' },
  { key: 'security', icon: '🔒', label: '安全扫描' },
  { key: 'diff', icon: '📊', label: '变更对比' },
  { key: 'traces', icon: '🔍', label: 'Agent追踪' },
]

const displayName = computed(() => {
  if (!state.value) return projectId
  return state.value.name || state.value.requirement || projectId
})

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

function handleRerun() { rerunDialogVisible.value = true }
function handleRerunConfirm() {
  rerunDialogVisible.value = false
  const req = state.value?.requirement || ''
  projectStore.pendingRequirement = req
  sessionStorage.setItem('pendingRequirement', req)
  router.push('/')
}

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

function handleExport() {
  api.exportProject(projectId)
}

onMounted(loadState)
</script>

<style scoped>
.detail-page { padding: 24px 32px; max-width: 960px; margin: 0 auto; }
.page-header { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
.btn-back { background: none; border: none; color: var(--primary); cursor: pointer; font-size: 13px; padding: 4px 8px; }
.btn-back:hover { text-decoration: underline; }
.page-title { font-size: 18px; font-weight: 600; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.header-actions { display: flex; gap: 8px; }
.btn-action { font-size: 12px; padding: 6px 12px; border: 1px solid var(--border); border-radius: var(--radius); background: transparent; cursor: pointer; transition: all 0.15s; }
.btn-action:hover:not(:disabled) { border-color: var(--primary); color: var(--primary); }
.btn-action:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-export { border-color: var(--primary); color: var(--primary); }
.btn-export:hover:not(:disabled) { background: var(--primary); color: #fff; }
.card { background: var(--bg-panel, var(--bg)); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; margin-bottom: 16px; }
.tab-bar { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.tab-btn { font-size: 13px; padding: 8px 16px; border: 1px solid var(--border); border-radius: var(--radius); background: transparent; cursor: pointer; transition: all 0.15s; }
.tab-btn:hover { border-color: var(--primary); color: var(--primary); }
.tab-btn.active { background: var(--primary); color: #fff; border-color: var(--primary); }
.tab-panel { background: var(--bg-panel, var(--bg)); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; margin-bottom: 16px; }
.skeleton-wrap { display: flex; flex-direction: column; gap: 16px; }
.skeleton-card { background: var(--bg-panel, var(--bg)); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; display: flex; flex-direction: column; gap: 12px; }
.skeleton-bar { height: 14px; background: linear-gradient(90deg, var(--border) 25%, transparent 50%, var(--border) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: 4px; }
.skeleton-title { width: 40%; height: 18px; }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
.error-card { display: flex; align-items: center; gap: 12px; }
.error-text { color: #ef4444; font-size: 13px; }
.btn-retry { font-size: 12px; padding: 4px 12px; border: 1px solid var(--primary); border-radius: 4px; background: transparent; color: var(--primary); cursor: pointer; }
.btn-retry:hover { background: var(--primary); color: #fff; }
.dialog-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.dialog { background: var(--bg-panel, #1a1a2e); border: 1px solid var(--border); border-radius: var(--radius); padding: 24px; width: 480px; max-width: 90vw; }
.dialog-title { font-size: 16px; font-weight: 600; margin-bottom: 16px; }
.dialog-text { font-size: 14px; color: var(--text); margin-bottom: 16px; line-height: 1.5; }
.dialog-textarea { width: 100%; padding: 12px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--bg); color: var(--text); font-size: 14px; resize: vertical; font-family: inherit; margin-bottom: 16px; }
.dialog-textarea:focus { outline: none; border-color: var(--primary); }
.dialog-actions { display: flex; justify-content: flex-end; gap: 8px; }
.btn-cancel { padding: 8px 16px; border: 1px solid var(--border); border-radius: var(--radius); background: transparent; cursor: pointer; font-size: 13px; }
.btn-confirm { padding: 8px 16px; border: 1px solid var(--primary); border-radius: var(--radius); background: var(--primary); color: #fff; cursor: pointer; font-size: 13px; }
.btn-confirm:hover { opacity: 0.9; }
</style>
