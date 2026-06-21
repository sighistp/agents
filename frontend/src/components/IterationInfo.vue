<template>
  <div v-if="projectStore.maxIterations > 0" class="iteration-info">
    <div class="iteration-label">迭代进度</div>
    <div class="iteration-bar">
      <div class="iteration-fill" :class="fillClass" :style="{ width: fillWidth }"></div>
    </div>
    <div class="iteration-count">{{ projectStore.iteration }} / {{ projectStore.maxIterations }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useProjectStore } from '../stores/project.js'
const projectStore = useProjectStore()

const fillClass = computed(() => {
  const percent = projectStore.maxIterations > 0
    ? (projectStore.iteration / projectStore.maxIterations) * 100
    : 0
  if (percent > 80) return 'bar-red'
  if (percent >= 50) return 'bar-yellow'
  return 'bar-green'
})

const fillWidth = computed(() => {
  const percent = projectStore.maxIterations > 0
    ? (projectStore.iteration / projectStore.maxIterations) * 100
    : 0
  return `${percent}%`
})
</script>

<style scoped>
.iteration-info { margin-top: 20px; padding: 16px; background: var(--bg); border-radius: var(--radius); border: 1px solid var(--border); }
.iteration-label { font-size: 12px; color: var(--text-dim); margin-bottom: 8px; }
.iteration-bar { height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; }
.iteration-fill { height: 100%; border-radius: 4px; transition: width 0.3s ease-out; }
.bar-green { background: var(--success); }
.bar-yellow { background: var(--warning); }
.bar-red { background: var(--error); }
.iteration-fill { height: 100%; border-radius: 4px; transition: width 0.3s; }
.iteration-count { font-size: 12px; color: var(--text-dim); margin-top: 6px; text-align: right; }
</style>
