<template>
  <div class="security-report">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <template v-else-if="data">
      <div class="score-row">
        <span class="score-label">安全评分</span>
        <span class="score-val" :class="scoreClass">{{ data.score }}</span>
      </div>

      <div v-if="data.issues && data.issues.length" class="issues">
        <div v-for="(issue, i) in data.issues" :key="i" class="issue-item">
          <span class="severity-badge" :class="'severity-' + issue.severity">{{ issue.severity }}</span>
          <span class="issue-loc">{{ issue.file }}:{{ issue.line }}</span>
          <span class="issue-desc">{{ issue.description }}</span>
        </div>
      </div>
      <div v-else class="empty">无安全问题</div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api/index.js'

const props = defineProps({ projectId: { type: String, required: true } })

const loading = ref(true)
const error = ref(null)
const data = ref(null)

const scoreClass = computed(() => {
  if (!data.value) return ''
  const s = data.value.score
  if (s > 80) return 'score-green'
  if (s >= 50) return 'score-yellow'
  return 'score-red'
})

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await api.getSecurityReport(props.projectId)
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.security-report { padding: 4px 0; }
.loading, .error { font-size: 13px; color: var(--text-dim); padding: 16px 0; text-align: center; }
.error { color: #ef4444; }
.score-row { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.score-label { font-size: 13px; color: var(--text-dim); }
.score-val { font-size: 28px; font-weight: 700; }
.score-green { color: #22c55e; }
.score-yellow { color: #eab308; }
.score-red { color: #ef4444; }
.issues { display: flex; flex-direction: column; gap: 8px; }
.issue-item { display: flex; align-items: center; gap: 10px; padding: 10px 12px; background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius); font-size: 13px; }
.severity-badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; flex-shrink: 0; }
.severity-critical { background: rgba(239,68,68,0.15); color: #ef4444; }
.severity-high { background: rgba(249,115,22,0.15); color: #f97316; }
.severity-medium { background: rgba(234,179,8,0.15); color: #eab308; }
.severity-low { background: rgba(34,197,94,0.15); color: #22c55e; }
.issue-loc { font-family: monospace; color: var(--text-dim); flex-shrink: 0; }
.issue-desc { flex: 1; min-width: 0; }
.empty { font-size: 13px; color: var(--text-dim); padding: 16px 0; text-align: center; }
</style>
