<template>
  <div class="agent-trace-panel">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <template v-else-if="traces.length">
      <div v-for="trace in traces" :key="trace.id" class="trace-item">
        <div class="trace-header" @click="toggle(trace.id)">
          <span class="trace-toggle">{{ expanded[trace.id] ? '▾' : '▸' }}</span>
          <span class="trace-agent">{{ trace.agent }}</span>
          <span class="trace-iter">迭代 {{ trace.iteration }}</span>
          <span class="trace-tools" v-if="trace.tools && trace.tools.length">
            {{ trace.tools.join(', ') }}
          </span>
        </div>
        <div v-if="expanded[trace.id]" class="trace-body">
          <div class="trace-section">
            <div class="section-label">Prompt</div>
            <div class="section-content">{{ trace.prompt }}</div>
          </div>
          <div class="trace-section">
            <div class="section-label">Response</div>
            <div class="section-content">{{ trace.response }}</div>
          </div>
          <div v-if="trace.tools && trace.tools.length" class="trace-section">
            <div class="section-label">Tools Used</div>
            <div class="section-content tools-list">
              <span v-for="(t, i) in trace.tools" :key="i" class="tool-tag">{{ t }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
    <div v-else class="empty">暂无追踪数据</div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { api } from '../api/index.js'

const props = defineProps({
  projectId: { type: String, required: true },
  agent: { type: String, default: '' },
  iteration: { type: Number, default: null }
})

const loading = ref(true)
const error = ref(null)
const traces = ref([])
const expanded = reactive({})

function toggle(id) {
  expanded[id] = !expanded[id]
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const data = await api.getTraces(props.projectId, props.agent, props.iteration)
    traces.value = data.traces || []
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.agent-trace-panel { padding: 4px 0; }
.loading, .error, .empty { font-size: 13px; color: var(--text-dim); padding: 16px 0; text-align: center; }
.error { color: var(--error); }
.trace-item { border: 1px solid var(--border); border-radius: var(--radius); margin-bottom: 8px; overflow: hidden; }
.trace-header { display: flex; align-items: center; gap: 10px; padding: 12px 16px; cursor: pointer; user-select: none; background: var(--bg); }
.trace-header:hover { background: var(--bg-panel); }
.trace-toggle { color: var(--text-dim); font-size: 12px; }
.trace-agent { font-weight: 600; font-size: 13px; color: var(--primary); }
.trace-iter { font-size: 11px; color: var(--text-dim); }
.trace-tools { font-size: 11px; color: var(--text-dim); margin-left: auto; font-family: monospace; }
.trace-body { border-top: 1px solid var(--border); padding: 12px 16px; display: flex; flex-direction: column; gap: 12px; }
.trace-section { }
.section-label { font-size: 11px; font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
.section-content { font-size: 13px; white-space: pre-wrap; word-break: break-word; line-height: 1.6; padding: 8px 12px; background: var(--bg); border-radius: var(--radius); border: 1px solid var(--border); }
.tools-list { display: flex; flex-wrap: wrap; gap: 6px; }
.tool-tag { font-size: 11px; padding: 2px 8px; background: rgba(59,130,246,0.15); color: var(--primary); border-radius: 4px; font-family: monospace; }
</style>
