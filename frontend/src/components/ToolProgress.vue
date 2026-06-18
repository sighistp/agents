<template>
  <div class="tool-progress" v-if="progress">
    <div class="progress-bar">
      <div class="progress-fill" :style="{ width: progressPct + '%' }"></div>
    </div>
    <div class="progress-info">
      <span class="progress-agent">{{ agentLabel }}</span>
      <span class="progress-step">步骤 {{ progress.step }}/{{ progress.max_steps }}</span>
      <span class="progress-tool">{{ progress.args_summary }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  progress: {
    type: Object,
    default: null
  }
})

const progressPct = computed(() => {
  if (!props.progress) return 0
  return Math.round((props.progress.step / props.progress.max_steps) * 100)
})

const agentLabel = computed(() => {
  const labels = {
    developer: '👨‍💻 Developer',
    tester: '🧪 Tester',
    reviewer: '📋 Reviewer',
  }
  return labels[props.progress?.agent] || props.progress?.agent || ''
})
</script>

<style scoped>
.tool-progress {
  padding: 8px 12px;
  background: var(--bg-panel);
  border-radius: 6px;
  margin-bottom: 8px;
  font-size: 12px;
}
.progress-bar {
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 4px;
}
.progress-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 2px;
  transition: width 0.3s;
}
.progress-info {
  display: flex;
  gap: 8px;
  color: var(--text-dim);
}
.progress-agent { font-weight: 600; color: var(--text); }
.progress-tool { color: var(--text-dim); }
</style>
