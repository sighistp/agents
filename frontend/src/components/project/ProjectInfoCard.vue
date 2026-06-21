<template>
  <div class="card">
    <div class="card-title">📋 项目信息</div>
    <div v-if="loading" class="skeleton-inner">
      <div class="skeleton-bar skeleton-title"></div>
      <div class="skeleton-bar" v-for="n in 3" :key="n"></div>
    </div>
    <div v-else-if="error" class="error-inner">
      <div class="error-text">{{ error }}</div>
      <button class="btn-retry" @click="load">重试</button>
    </div>
    <template v-else-if="state">
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
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../../api/index.js'

const props = defineProps({ projectId: { type: String, required: true } })

const loading = ref(true)
const error = ref(null)
const state = ref(null)

const statusClass = computed(() => {
  const s = state.value?.status
  if (!s) return ''
  if (['delivered', 'completed', 'saved'].includes(s)) return 'status-good'
  if (['failed', 'error', 'cancelled'].includes(s)) return 'status-bad'
  if (s === 'running') return 'status-running'
  return ''
})

async function load() {
  loading.value = true
  error.value = null
  try {
    state.value = await api.getProjectState(props.projectId)
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

defineExpose({ load, state })

onMounted(load)
</script>

<style scoped>
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
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}
.info-item { display: flex; flex-direction: column; gap: 2px; }
.info-label { font-size: 11px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.5px; }
.info-value { font-size: 14px; font-weight: 500; }
.status-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; width: fit-content; }
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
.error-inner { display: flex; align-items: center; gap: 12px; padding: 8px 0; }
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
</style>
