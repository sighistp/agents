<template>
  <div class="toast-container">
    <TransitionGroup name="toast">
      <div
        v-for="n in notifications"
        :key="n.id"
        class="toast"
        :class="`toast-${n.type}`"
        @click="remove(n.id)"
      >
        <span class="toast-icon">{{ icons[n.type] }}</span>
        <span class="toast-message">{{ n.message }}</span>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { useNotification } from '../composables/useNotification.js'

const { notifications, remove } = useNotification()

const icons = {
  success: '✅',
  error: '❌',
  warning: '⚠️',
  info: 'ℹ️',
}
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}
.toast {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 13px;
  pointer-events: auto;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  max-width: 360px;
  transition: all 0.3s;
}
.toast-success { background: var(--success-bg, rgba(34,197,94,0.15)); color: var(--success); border-left: 3px solid var(--success); }
.toast-error { background: var(--error-bg, rgba(239,68,68,0.15)); color: var(--error); border-left: 3px solid var(--error); }
.toast-warning { background: var(--warning-bg, rgba(245,158,11,0.15)); color: var(--warning); border-left: 3px solid var(--warning); }
.toast-info { background: var(--info-bg, rgba(59,130,246,0.15)); color: var(--primary); border-left: 3px solid var(--primary); }
.toast-enter-active { animation: slideIn 0.3s; }
.toast-leave-active { animation: slideOut 0.3s; }
@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
@keyframes slideOut { from { transform: translateX(0); opacity: 1; } to { transform: translateX(100%); opacity: 0; } }
</style>
