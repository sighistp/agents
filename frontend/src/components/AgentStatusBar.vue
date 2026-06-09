<template>
  <div v-if="hasActiveProject" class="status-bar">
    <div v-for="agent in projectStore.agentList" :key="agent.name" :class="['status-dot', agent.status]" :title="`${agent.name}: ${agent.status}`"></div>
    <span class="status-text">{{ statusText }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useProjectStore } from '../stores/project.js'

const projectStore = useProjectStore()
const hasActiveProject = computed(() => Object.keys(projectStore.agentStatus).length > 0)
const statusText = computed(() => {
  const running = projectStore.agentList.find(a => a.status === 'running')
  return running ? `${running.name} 执行中...` : projectStore.agentList.every(a => a.status === 'done') ? '已完成' : '就绪'
})
</script>

<style scoped>
.status-bar { display: flex; align-items: center; gap: 6px; padding: 0 16px; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--border); }
.status-dot.running { background: var(--primary); animation: pulse 1.5s infinite; }
.status-dot.done { background: var(--success); }
.status-dot.error { background: var(--error); }
.status-text { font-size: 12px; color: var(--text-dim); }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
</style>
