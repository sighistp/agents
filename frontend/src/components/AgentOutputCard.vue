<!-- frontend/src/components/AgentOutputCard.vue -->
<template>
  <div class="agent-output-card" :style="{ borderLeftColor: color }">
    <div class="card-header">
      <span class="card-agent" :style="{ color }">{{ icon }} {{ label }}</span>
      <span class="card-time" v-if="duration">{{ duration }}</span>
    </div>
    <div class="card-body">
      <!-- PM -->
      <template v-if="msg.name === 'pm'">
        <div>{{ userStories.length }} 个用户故事 · {{ features.length }} 个功能特性</div>
      </template>
      <!-- Architect -->
      <template v-else-if="msg.name === 'architect'">
        <div>{{ apiDefinitions.length }} 个 API · {{ dataModels.length }} 个数据模型</div>
      </template>
      <!-- Developer -->
      <template v-else-if="msg.name === 'developer'">
        <template v-if="fileList.length">
          <div>{{ fileList.length }} 个文件</div>
          <div class="file-list">
            <span v-for="f in fileList" :key="f" class="file-tag">📝 {{ f }}</span>
          </div>
        </template>
        <div v-if="keyDecisions.length" class="decisions">
          <span v-for="d in keyDecisions" :key="d" class="decision-tag">💡 {{ d }}</span>
        </div>
        <div v-if="!fileList.length && !keyDecisions.length">{{ msg.content }}</div>
      </template>
      <!-- Tester -->
      <template v-else-if="msg.name === 'tester'">
        <div :class="testPassed ? 'test-pass' : 'test-fail'">
          {{ testPassed ? '✅ 测试通过' : '❌ 测试未通过' }}
        </div>
        <div v-for="(r, i) in testResults" :key="i" class="test-summary">{{ r.summary }}</div>
      </template>
      <!-- Reviewer -->
      <template v-else-if="msg.name === 'reviewer'">
        <div :class="reviewApproved ? 'review-pass' : 'review-fail'">
          {{ reviewApproved ? '✅ 审查通过' : '❌ 审查不通过' }}
        </div>
        <div v-for="(c, i) in reviewComments" :key="i" class="review-comment">
          <span class="severity" :class="c.severity">{{ c.severity }}</span>
          {{ c.description }}
        </div>
      </template>
      <!-- 兜底 -->
      <template v-else>
        <div>{{ msg.content }}</div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ msg: Object })

const data = computed(() => props.msg.data?.data ?? {})
const userStories = computed(() => data.value.user_stories ?? [])
const features = computed(() => data.value.features ?? [])
const apiDefinitions = computed(() => data.value.api_definitions ?? [])
const dataModels = computed(() => data.value.data_models ?? [])
const fileList = computed(() => Object.keys(data.value.files ?? {}))
const keyDecisions = computed(() => data.value.key_decisions ?? [])
const testPassed = computed(() => data.value.test_passed ?? false)
const testResults = computed(() => data.value.test_results ?? [])
const reviewApproved = computed(() => data.value.review_approved ?? false)
const reviewComments = computed(() => data.value.review_comments ?? [])

const colorMap = { pm: '#3B82F6', architect: '#8B5CF6', developer: '#10B981', tester: '#F59E0B', reviewer: '#EC4899' }
const iconMap = { pm: '👤', architect: '🏗️', developer: '💻', tester: '🧪', reviewer: '🔍' }
const labelMap = { pm: 'PM', architect: '架构师', developer: '开发者', tester: '测试员', reviewer: '审查员' }

const color = computed(() => colorMap[props.msg.name] || '#6B7280')
const icon = computed(() => iconMap[props.msg.name] || '🤖')
const label = computed(() => labelMap[props.msg.name] || props.msg.name)
const duration = computed(() => null) // 后续从 agentStartTime 计算
</script>

<style scoped>
.agent-output-card { border-left: 3px solid; border-radius: 8px; padding: 10px 14px; background: var(--bg-panel); border: 1px solid var(--border); margin: 4px 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.card-agent { font-weight: 600; font-size: 12px; }
.card-time { font-size: 11px; color: var(--text-dim); }
.card-body { font-size: 12px; color: var(--text); line-height: 1.6; }
.file-list { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.file-tag { background: var(--bg); padding: 2px 8px; border-radius: 4px; font-size: 11px; }
.decisions { margin-top: 4px; }
.decision-tag { display: inline-block; margin-right: 8px; font-size: 11px; }
.test-pass { color: #10B981; } .test-fail { color: #EF4444; }
.review-pass { color: #10B981; } .review-fail { color: #EF4444; }
.review-comment { font-size: 11px; margin-top: 2px; }
.severity { font-weight: 600; margin-right: 4px; }
.severity.critical { color: #EF4444; } .severity.important { color: #F59E0B; } .severity.minor { color: #6B7280; }
.test-summary { font-size: 11px; margin-top: 2px; }
</style>
