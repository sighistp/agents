<template>
  <div :class="['agent-card', `agent-${name}`, status]">
    <div class="agent-bar"></div>
    <div class="agent-body">
      <div class="agent-icon">{{ icon }}</div>
      <div class="agent-info">
        <div class="agent-name">{{ label }}</div>
        <div class="agent-status-text">{{ statusText }}</div>
      </div>
      <div class="agent-dot" :class="status"></div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ name: String, status: { type: String, default: 'waiting' } })

const labels = { pm: 'PM', architect: '架构师', developer: '开发者', tester: '测试员', reviewer: '审查员' }
const icons = { pm: '👤', architect: '🏗️', developer: '💻', tester: '🧪', reviewer: '🔍' }
const statusTexts = { waiting: '等待中', running: '执行中', done: '已完成', error: '错误', paused: '暂停' }

const label = computed(() => labels[props.name] || props.name)
const icon = computed(() => icons[props.name] || '🤖')
const statusText = computed(() => statusTexts[props.status] || props.status)
</script>

<style scoped>
.agent-card { background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; transition: all 0.2s; }
.agent-card.running { border-color: var(--agent-color); box-shadow: 0 0 12px rgba(59,130,246,0.15); }
.agent-bar { height: 3px; background: var(--agent-color); opacity: 0.4; }
.agent-card.running .agent-bar { opacity: 1; }
.agent-body { display: flex; align-items: center; gap: 12px; padding: 14px 16px; }
.agent-icon { font-size: 24px; }
.agent-info { flex: 1; }
.agent-name { font-size: 13px; font-weight: 600; color: var(--text); }
.agent-status-text { font-size: 12px; color: var(--text-dim); margin-top: 2px; }
.agent-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--border); }
.agent-dot.running { background: var(--primary); animation: pulse 1.5s infinite; }
.agent-dot.done { background: var(--success); }
.agent-dot.error { background: var(--error); }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
</style>
