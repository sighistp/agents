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
.toast-success { background: #dcfce7; color: #166534; border-left: 3px solid #16a34a; }
.toast-error { background: #fee2e2; color: #991b1b; border-left: 3px solid #dc2626; }
.toast-warning { background: #fef3c7; color: #92400e; border-left: 3px solid #d97706; }
.toast-info { background: #dbeafe; color: #1e40af; border-left: 3px solid #3b82f6; }
.toast-enter-active { animation: slideIn 0.3s; }
.toast-leave-active { animation: slideOut 0.3s; }
@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
@keyframes slideOut { from { transform: translateX(0); opacity: 1; } to { transform: translateX(100%); opacity: 0; } }
</style>
