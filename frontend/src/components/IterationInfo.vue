<template>
  <div v-if="projectStore.maxIterations > 0" class="iteration-info">
    <div class="iteration-label">迭代进度</div>
    <div class="iteration-bar">
      <div class="iteration-fill" :style="fillStyle"></div>
    </div>
    <div class="iteration-count">{{ projectStore.iteration }} / {{ projectStore.maxIterations }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useProjectStore } from '../stores/project.js'
const projectStore = useProjectStore()

const fillStyle = computed(() => {
  const percent = projectStore.maxIterations > 0
    ? (projectStore.iteration / projectStore.maxIterations) * 100
    : 0
  let color = '#4caf50' // green < 50%
  if (percent > 80) color = '#f44336' // red > 80%
  else if (percent >= 50) color = '#ff9800' // yellow 50-80%
  return { width: `${percent}%`, background: color }
})
</script>

<style scoped>
.iteration-info { margin-top: 20px; padding: 16px; background: var(--bg); border-radius: var(--radius); border: 1px solid var(--border); }
.iteration-label { font-size: 12px; color: var(--text-dim); margin-bottom: 8px; }
.iteration-bar { height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; }
.iteration-fill { height: 100%; border-radius: 4px; transition: width 0.3s; }
.iteration-count { font-size: 12px; color: var(--text-dim); margin-top: 6px; text-align: right; }
</style>
