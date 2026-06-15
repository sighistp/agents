<template>
  <div class="diff-viewer">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <template v-else>
      <div class="diff-controls">
        <select v-model="snapA" class="diff-select">
          <option value="" disabled>选择版本 A</option>
          <option v-for="s in snapshots" :key="s.id" :value="s.id">迭代 {{ s.iteration }}{{ s.label ? ' - ' + s.label : '' }}</option>
        </select>
        <span class="diff-arrow">→</span>
        <select v-model="snapB" class="diff-select">
          <option value="" disabled>选择版本 B</option>
          <option v-for="s in snapshots" :key="s.id" :value="s.id">迭代 {{ s.iteration }}{{ s.label ? ' - ' + s.label : '' }}</option>
        </select>
      </div>

      <div v-if="diffData" class="diff-files">
        <div v-if="diffData.files.length === 0" class="empty">无变更</div>
        <div v-for="f in diffData.files" :key="f.path" class="diff-file">
          <div class="file-header">
            <span class="file-path">{{ f.path }}</span>
            <span class="file-type" :class="'type-' + f.type">{{ f.type }}</span>
          </div>
          <div class="diff-lines">
            <template v-for="(hunk, hi) in f.hunks" :key="hi">
              <div v-for="(line, li) in hunk.lines" :key="li" class="diff-line" :class="lineClass(line)">
                <span class="line-text">{{ line }}</span>
              </div>
            </template>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { api } from '../api/index.js'

const props = defineProps({ projectId: { type: String, required: true } })

const loading = ref(true)
const error = ref(null)
const snapshots = ref([])
const snapA = ref('')
const snapB = ref('')
const diffData = ref(null)

function lineClass(line) {
  if (line.startsWith('+')) return 'diff-add'
  if (line.startsWith('-')) return 'diff-del'
  return ''
}

async function loadSnapshots() {
  loading.value = true
  error.value = null
  try {
    const data = await api.getSnapshots(props.projectId)
    snapshots.value = data.snapshots || []
  } catch (e) {
    error.value = e.message || '加载快照失败'
  } finally {
    loading.value = false
  }
}

async function loadDiff() {
  if (!snapA.value || !snapB.value) return
  try {
    diffData.value = await api.getDiff(props.projectId, snapA.value, snapB.value)
  } catch (e) {
    error.value = e.message || '加载差异失败'
  }
}

watch([snapA, snapB], loadDiff)

onMounted(loadSnapshots)
</script>

<style scoped>
.diff-viewer { padding: 4px 0; }
.loading, .error, .empty { font-size: 13px; color: var(--text-dim); padding: 16px 0; text-align: center; }
.error { color: #ef4444; }
.diff-controls { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.diff-select { flex: 1; padding: 8px 12px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--bg); color: var(--text); font-size: 13px; }
.diff-select:focus { outline: none; border-color: var(--primary); }
.diff-arrow { color: var(--text-dim); font-size: 16px; }
.diff-files { display: flex; flex-direction: column; gap: 16px; }
.diff-file { border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.file-header { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; background: var(--bg); border-bottom: 1px solid var(--border); font-size: 13px; }
.file-path { font-family: monospace; font-weight: 500; }
.file-type { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 600; text-transform: uppercase; }
.type-added { background: rgba(34,197,94,0.15); color: #22c55e; }
.type-modified { background: rgba(59,130,246,0.15); color: #3b82f6; }
.type-deleted { background: rgba(239,68,68,0.15); color: #ef4444; }
.diff-lines { font-family: monospace; font-size: 12px; }
.diff-line { padding: 2px 16px; white-space: pre; line-height: 1.6; }
.diff-add { background: rgba(34,197,94,0.1); color: #22c55e; }
.diff-del { background: rgba(239,68,68,0.1); color: #ef4444; }
</style>
