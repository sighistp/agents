<template>
  <div class="flow-panel">
    <div class="flow-title">Agent 协作流程</div>
    <div class="agents-grid">
      <AgentCard v-for="agent in projectStore.agentList" :key="agent.name" :name="agent.name" :status="agent.status" />
    </div>
    <IterationInfo />
    <OutputPanel />
    <DiscussionPanel />
  </div>
</template>

<script setup>
import { useProjectStore } from '../stores/project.js'
import AgentCard from './AgentCard.vue'
import IterationInfo from './IterationInfo.vue'
import OutputPanel from './OutputPanel.vue'
import DiscussionPanel from './DiscussionPanel.vue'

const projectStore = useProjectStore()
</script>

<style scoped>
.flow-panel { padding: 24px; background: var(--bg-panel); border-right: 1px solid var(--border); min-width: 280px; overflow-y: auto; }
.flow-title { font-size: 14px; font-weight: 600; color: var(--text-dim); margin-bottom: 16px; text-transform: uppercase; letter-spacing: 1px; }
.agents-grid { display: flex; flex-direction: column; gap: 10px; }
</style>
