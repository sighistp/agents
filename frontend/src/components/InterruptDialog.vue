<template>
  <div v-if="projectStore.interrupt" class="overlay">
    <div class="dialog">
      <h3>{{ projectStore.interrupt.type === 'clarify' ? '需要补充信息' : '需要确认' }}</h3>
      <p>{{ projectStore.interrupt.message }}</p>
      <ul v-if="projectStore.interrupt.questions">
        <li v-for="q in projectStore.interrupt.questions" :key="q">{{ q }}</li>
      </ul>
      <textarea v-model="reply" placeholder="输入你的回复..."></textarea>
      <div class="actions">
        <button class="btn-secondary" @click="handleReject">拒绝</button>
        <button class="btn-primary" @click="handleApprove">确认</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useProjectStore } from '../stores/project.js'
import { useWebSocket } from '../composables/useWebSocket.js'

const projectStore = useProjectStore()
const { send } = useWebSocket()
const reply = ref('')

function handleApprove() {
  send({ type: 'resume', thread_id: projectStore.currentProject?.id, decision: 'approved', clarification: reply.value })
  projectStore.interrupt = null
  reply.value = ''
}
function handleReject() {
  send({ type: 'resume', thread_id: projectStore.currentProject?.id, decision: 'rejected', clarification: reply.value })
  projectStore.interrupt = null
  reply.value = ''
}
</script>

<style scoped>
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.dialog { background: var(--bg); border-radius: 12px; padding: 32px; max-width: 480px; width: 90%; box-shadow: 0 8px 32px rgba(0,0,0,0.15); }
.dialog h3 { margin-bottom: 12px; }
.dialog p { font-size: 14px; color: var(--text-dim); margin-bottom: 16px; }
.dialog ul { margin-bottom: 16px; padding-left: 20px; font-size: 13px; color: var(--text-dim); }
.dialog textarea { width: 100%; border: 1px solid var(--border); border-radius: var(--radius); padding: 10px; font-size: 13px; margin-bottom: 16px; resize: vertical; min-height: 60px; }
.actions { display: flex; gap: 8px; justify-content: flex-end; }
.btn-primary { background: var(--primary); color: #fff; border: none; padding: 8px 20px; border-radius: var(--radius); cursor: pointer; }
.btn-secondary { background: transparent; border: 1px solid var(--border); padding: 8px 20px; border-radius: var(--radius); cursor: pointer; }
</style>
