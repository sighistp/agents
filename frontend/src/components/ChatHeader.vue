<!-- frontend/src/components/ChatHeader.vue -->
<template>
  <div class="chat-header">
    <span class="chat-title">通讯频道</span>
    <div class="chat-actions">
      <span v-if="!isConnected" class="disconnect-hint">⚠ 连接断开</span>
      <!-- 运行中：暂停 + 保存 -->
      <template v-if="isRunning && !isPaused">
        <button class="btn-icon btn-pause" @click="$emit('pause')" title="暂停" :disabled="!isConnected">⏸</button>
      </template>
      <!-- 已暂停：继续 + 停止 -->
      <template v-else-if="isRunning && isPaused">
        <button class="btn-icon btn-resume" @click="$emit('resume')" title="继续" :disabled="!isConnected">▶</button>
        <button class="btn-icon btn-stop" @click="$emit('stop')" title="停止" :disabled="!isConnected">⏹</button>
      </template>
      <!-- 通用按钮 -->
      <button class="btn-icon" @click="$emit('save')" title="保存项目">💾</button>
      <button class="btn-icon" @click="$emit('clear')" title="清空聊天">🗑️</button>
      <button class="btn-icon" @click="$emit('new')" title="新建对话">✚</button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useProjectStore } from '../stores/project.js'
import { useWsStore } from '../stores/websocket.js'

const projectStore = useProjectStore()
const wsStore = useWsStore()
const isRunning = computed(() => projectStore.isRunning)
const isPaused = computed(() => projectStore.isPaused)
const isConnected = computed(() => wsStore.isConnected)

defineEmits(['pause', 'resume', 'stop', 'save', 'clear', 'new'])
</script>

<style scoped>
.chat-header { padding: 12px 16px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
.chat-title { font-size: 14px; font-weight: 600; color: var(--text-dim); }
.chat-actions { display: flex; gap: 6px; }
.btn-icon { width: 28px; height: 28px; border-radius: 6px; background: transparent; border: 1px solid var(--border); color: var(--text-dim); cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 13px; transition: all 0.15s; }
.btn-icon:hover { background: var(--bg-panel); border-color: var(--primary); color: var(--primary); }
.btn-pause { color: var(--warning); border-color: rgba(245,158,11,0.3); }
.btn-pause:hover { background: rgba(245,158,11,0.1); border-color: var(--warning); }

.btn-resume { color: var(--success); border-color: rgba(34,197,94,0.3); }
.btn-resume:hover { background: rgba(34,197,94,0.1); border-color: var(--success); }

.btn-stop { color: var(--error); border-color: rgba(239,68,68,0.3); }
.btn-stop:hover { background: rgba(239,68,68,0.1); border-color: var(--error); }
.disconnect-hint { font-size: 12px; color: var(--error); font-weight: 500; margin-right: 4px; }
.btn-icon:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-icon:disabled:hover { background: transparent; border-color: var(--border); color: var(--text-dim); }
</style>
