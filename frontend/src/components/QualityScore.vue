<template>
  <div class="quality-score">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <template v-else-if="data">
      <div class="score-header">
        <div class="total-score" :class="scoreColor">
          <span class="score-num">{{ data.total_score }}</span>
          <span class="score-label">总分</span>
        </div>
        <div class="grade-badge" :class="scoreColor">{{ data.grade }}</div>
      </div>

      <div class="dimensions">
        <div v-for="dim in data.dimensions" :key="dim.name" class="dim-row">
          <span class="dim-name">{{ dim.name }}</span>
          <div class="dim-bar-wrap">
            <div class="dim-bar" :class="dimColor(dim.score)" :style="{ width: dim.score + '%' }"></div>
          </div>
          <span class="dim-score">{{ dim.score }}</span>
        </div>
      </div>

      <div v-if="data.suggestions && data.suggestions.length" class="suggestions">
        <div class="section-title">改进建议</div>
        <ul>
          <li v-for="(s, i) in data.suggestions" :key="i">{{ s }}</li>
        </ul>
      </div>
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

const scoreColor = computed(() => {
  if (!data.value) return ''
  const s = data.value.total_score
  if (s > 80) return 'score-green'
  if (s >= 50) return 'score-yellow'
  return 'score-red'
})

function dimColor(score) {
  if (score > 80) return 'dim-green'
  if (score >= 50) return 'dim-yellow'
  return 'dim-red'
}

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await api.getQualityScore(props.projectId)
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.quality-score { padding: 4px 0; }
.loading, .error { font-size: 13px; color: var(--text-dim); padding: 16px 0; text-align: center; }
.error { color: #ef4444; }
.score-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.total-score { display: flex; flex-direction: column; align-items: center; }
.score-num { font-size: 40px; font-weight: 700; line-height: 1; }
.score-label { font-size: 11px; color: var(--text-dim); margin-top: 4px; }
.score-green .score-num { color: #22c55e; }
.score-yellow .score-num { color: #eab308; }
.score-red .score-num { color: #ef4444; }
.grade-badge { font-size: 24px; font-weight: 700; padding: 8px 16px; border-radius: 8px; }
.score-green .grade-badge { background: rgba(34,197,94,0.15); color: #22c55e; }
.score-yellow .grade-badge { background: rgba(234,179,8,0.15); color: #eab308; }
.score-red .grade-badge { background: rgba(239,68,68,0.15); color: #ef4444; }
.dimensions { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
.dim-row { display: flex; align-items: center; gap: 12px; }
.dim-name { width: 80px; font-size: 12px; color: var(--text-dim); flex-shrink: 0; }
.dim-bar-wrap { flex: 1; height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; }
.dim-bar { height: 100%; border-radius: 4px; transition: width 0.3s; }
.dim-green { background: #22c55e; }
.dim-yellow { background: #eab308; }
.dim-red { background: #ef4444; }
.dim-score { width: 30px; font-size: 12px; font-weight: 600; text-align: right; }
.section-title { font-size: 12px; font-weight: 600; color: var(--text-dim); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
.suggestions ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }
.suggestions li { font-size: 13px; color: var(--text); padding: 8px 12px; background: var(--bg); border-radius: var(--radius); border: 1px solid var(--border); }
</style>
