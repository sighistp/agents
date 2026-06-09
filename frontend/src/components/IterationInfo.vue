<template>
  <div v-if="projectStore.iteration > 0" class="iteration-info">
    <div class="iteration-label">迭代进度</div>
    <div class="iteration-bar">
      <div class="iteration-fill" :style="{ width: `${(projectStore.iteration / projectStore.maxIterations) * 100}%` }"></div>
    </div>
    <div class="iteration-count">{{ projectStore.iteration }} / {{ projectStore.maxIterations }}</div>
  </div>
</template>

<script setup>
import { useProjectStore } from '../stores/project.js'
const projectStore = useProjectStore()
</script>

<style scoped>
.iteration-info { margin-top: 20px; padding: 16px; background: var(--bg); border-radius: var(--radius); border: 1px solid var(--border); }
.iteration-label { font-size: 12px; color: var(--text-dim); margin-bottom: 8px; }
.iteration-bar { height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; }
.iteration-fill { height: 100%; background: var(--primary); border-radius: 2px; transition: width 0.3s; }
.iteration-count { font-size: 12px; color: var(--text-dim); margin-top: 6px; text-align: right; }
</style>
