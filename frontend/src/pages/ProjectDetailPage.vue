<template>
  <div class="detail-page">
    <button class="btn-back" @click="$router.push('/projects')">← 返回</button>
    <h2>项目详情</h2>
    <div v-if="loading">加载中...</div>
    <div v-else-if="project">
      <div class="meta">状态: {{ project.status }} · 迭代: {{ project.iteration }}</div>

      <!-- 消息记录 -->
      <div class="section-title">Agent 对话</div>
      <div class="messages">
        <div v-for="(msg, i) in project.messages || []" :key="i" class="msg">
          <strong>{{ msg.name || msg.role }}:</strong> {{ msg.content }}
        </div>
      </div>

      <!-- 生成文件 -->
      <div v-if="files && Object.keys(files).length > 0">
        <div class="section-title">生成文件</div>
        <div class="files-list">
          <div v-for="(content, path) in files" :key="path" class="file-item">
            <span class="file-icon">📄</span>
            <span class="file-name">{{ path }}</span>
            <button class="btn-sm" @click="preview(path, content)">预览</button>
            <button class="btn-sm" @click="download(path, content)">下载</button>
          </div>
        </div>
        <div class="download-options">
          <button class="btn-download" @click="downloadSource">📦 下载源码</button>
          <button class="btn-download" @click="downloadApp">🚀 下载应用</button>
          <button class="btn-download btn-download-primary" @click="downloadAll">📁 全部打包下载</button>
        </div>

        <!-- 预览窗口 -->
        <div v-if="previewContent" class="preview-box">
          <div class="preview-header">
            <span>{{ previewPath }}</span>
            <button @click="previewContent = null">✕</button>
          </div>
          <pre>{{ previewContent }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import JSZip from 'jszip'
import { saveAs } from 'file-saver'
import { api } from '../api/index.js'

const route = useRoute()
const project = ref(null)
const files = ref({})
const loading = ref(true)
const previewPath = ref(null)
const previewContent = ref(null)
const downloading = ref(false)

const SOURCE_EXTS = ['.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.vue', '.json', '.yaml', '.yml', '.toml']
const APP_FILES = ['start.sh', 'start.bat', 'requirements.txt', 'package.json', 'Dockerfile']

function isSourceFile(path) { return SOURCE_EXTS.some(ext => path.endsWith(ext)) }
function isAppFile(path) { return APP_FILES.some(name => path.endsWith(name)) || isSourceFile(path) }

onMounted(async () => {
  try {
    project.value = await api.getProject(route.params.id)
    const filesResponse = await api.getProjectFiles(route.params.id)
    files.value = filesResponse.files || filesResponse || {}
  } catch (e) { console.error(e) }
  finally { loading.value = false }
})

function preview(path, content) {
  previewPath.value = path
  previewContent.value = content
}

function downloadSingle(path, content) {
  saveAs(new Blob([content], { type: 'text/plain' }), path.split('/').pop())
}

async function createZip(filterFn, zipName) {
  downloading.value = true
  try {
    const zip = new JSZip()
    let count = 0
    for (const [path, content] of Object.entries(files.value)) {
      if (filterFn(path)) { zip.file(path, content); count++ }
    }
    if (count === 0) { alert('没有匹配的文件'); return }
    const blob = await zip.generateAsync({ type: 'blob' })
    saveAs(blob, `${zipName}.zip`)
  } finally { downloading.value = false }
}

function downloadSource() { createZip(isSourceFile, 'source-code') }
function downloadApp() { createZip(isAppFile, 'application') }
function downloadAll() { createZip(() => true, 'project') }
</script>

<style scoped>
.detail-page { padding: 32px; max-width: 900px; margin: 0 auto; }
.btn-back { background: none; border: none; color: var(--primary); cursor: pointer; font-size: 13px; margin-bottom: 16px; }
.meta { font-size: 13px; color: var(--text-dim); margin-bottom: 16px; }
.section-title { font-size: 12px; font-weight: 600; color: var(--primary); text-transform: uppercase; letter-spacing: 1px; margin: 20px 0 12px; }
.messages { background: var(--bg-panel); border-radius: var(--radius); padding: 16px; margin-bottom: 24px; max-height: 300px; overflow-y: auto; }
.msg { font-size: 13px; margin-bottom: 8px; line-height: 1.5; }
.files-list { display: flex; flex-direction: column; gap: 4px; }
.file-item { display: flex; align-items: center; gap: 8px; padding: 8px; font-size: 13px; font-family: monospace; background: var(--bg-panel); border-radius: var(--radius); }
.file-icon { font-size: 14px; }
.file-name { flex: 1; }
.btn-sm { font-size: 11px; padding: 3px 10px; border: 1px solid var(--border); border-radius: 4px; background: transparent; cursor: pointer; }
.btn-sm:hover { border-color: var(--primary); color: var(--primary); }
.download-options { display: flex; gap: 8px; margin-top: 16px; }
.btn-download { flex: 1; padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius); background: transparent; cursor: pointer; font-size: 12px; font-weight: 500; text-align: center; transition: all 0.15s; }
.btn-download:hover { border-color: var(--primary); color: var(--primary); }
.btn-download-primary { border-color: var(--primary); color: var(--primary); }
.btn-download-primary:hover { background: var(--primary); color: #fff; }
.preview-box { margin-top: 16px; border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.preview-header { display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; background: var(--bg-panel); font-size: 13px; font-weight: 500; }
.preview-header button { background: none; border: none; cursor: pointer; font-size: 16px; color: var(--text-dim); }
.preview-box pre { padding: 16px; font-size: 13px; line-height: 1.6; overflow: auto; max-height: 500px; background: var(--bg); margin: 0; }
</style>
