<template>
  <div v-if="discussionMessages.length > 0" class="discussion-panel">
    <div class="discussion-title" @click="expanded = !expanded">
      💬 Proposer-Critic 讨论 ({{ discussionMessages.length }} 条)
      <span>{{ expanded ? '收起' : '展开' }}</span>
    </div>
    <div v-if="expanded" class="discussion-body">
      <div v-for="(msg, i) in discussionMessages" :key="i" :class="['disc-item', msg.name?.includes('critic') ? 'critic' : 'proposer']">
        <div class="disc-label">{{ msg.name?.includes('critic') ? '审查' : '方案' }}</div>
        <div class="disc-content">{{ msg.content }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useProjectStore } from '../stores/project.js'

const projectStore = useProjectStore()
const expanded = ref(false)

const discussionMessages = computed(() =>
  projectStore.messages.filter(m => m.name && (m.name.includes('proposer') || m.name.includes('critic')))
)
</script>

<style scoped>
.discussion-panel { margin-top: 20px; background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius); }
.discussion-title { padding: 12px 16px; font-size: 13px; font-weight: 600; cursor: pointer; display: flex; justify-content: space-between; }
.discussion-title span { font-size: 12px; color: var(--primary); font-weight: 400; }
.discussion-body { padding: 0 16px 16px; }
.disc-item { padding: 8px 12px; margin-bottom: 8px; border-radius: 6px; font-size: 12px; line-height: 1.5; }
.disc-item.proposer { background: rgba(59,130,246,0.1); border-left: 3px solid var(--primary); }
.disc-item.critic { background: rgba(239,68,68,0.1); border-left: 3px solid var(--error); }
.disc-label { font-size: 11px; font-weight: 600; margin-bottom: 4px; color: var(--text-dim); }
</style>
