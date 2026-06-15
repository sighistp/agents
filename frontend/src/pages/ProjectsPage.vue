<template>
  <div class="projects-page">
    <h2>项目列表</h2>
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="projects.length === 0" class="empty">暂无项目</div>
    <div v-else class="projects-grid">
      <div v-for="p in projects" :key="p.project_id" class="project-card" @click="$router.push(`/projects/${p.project_id}`)">
        <div class="project-name">{{ p.name || p.requirement || p.project_id }}</div>
        <div class="project-meta">{{ p.status || 'unknown' }} · 迭代 {{ p.iteration || 0 }} 次</div>
        <button class="btn-delete" @click.stop="remove(p.project_id)">删除</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/index.js'

const projects = ref([])
const loading = ref(true)

onMounted(async () => {
  try { projects.value = await api.getProjects() } catch (e) { console.error(e) }
  finally { loading.value = false }
})

async function remove(id) {
  if (!confirm('确定删除？')) return
  await api.deleteProject(id)
  projects.value = projects.value.filter(p => p.project_id !== id)
}
</script>

<style scoped>
.projects-page { padding: 32px; max-width: 800px; margin: 0 auto; }
.projects-page h2 { margin-bottom: 24px; }
.loading, .empty { color: var(--text-dim); font-size: 14px; }
.projects-grid { display: flex; flex-direction: column; gap: 12px; }
.project-card { background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; cursor: pointer; position: relative; transition: border-color 0.2s; }
.project-card:hover { border-color: var(--primary); }
.project-name { font-weight: 600; font-size: 14px; }
.project-meta { font-size: 12px; color: var(--text-dim); margin-top: 4px; }
.btn-delete { position: absolute; top: 12px; right: 12px; background: none; border: 1px solid var(--error); color: var(--error); border-radius: 4px; padding: 2px 8px; font-size: 11px; cursor: pointer; opacity: 0; transition: opacity 0.2s; }
.project-card:hover .btn-delete { opacity: 1; }
</style>
