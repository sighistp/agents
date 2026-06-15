<template>
  <div v-if="Object.keys(projectStore.files).length > 0" class="output-panel">
    <div class="output-title">生成文件</div>
    <div v-for="(content, path) in projectStore.files" :key="path" class="file-item">
      <span class="file-icon">{{ getFileIcon(path) }}</span>
      <span class="file-name clickable" @click="togglePreview(path, content)">{{ path }}</span>
      <button class="btn-sm" @click="downloadSingle(path, content)">下载</button>
    </div>

    <!-- 下载选项 -->
    <div class="download-options">
      <button class="btn-download" @click="downloadSource" :disabled="downloading">
        📦 下载源码
      </button>
      <button class="btn-download" @click="downloadApp" :disabled="downloading">
        🚀 下载应用
      </button>
      <button class="btn-download btn-download-primary" @click="downloadAll" :disabled="downloading">
        📁 全部打包下载
      </button>
    </div>

    <!-- 预览窗口 -->
    <div v-if="previewFile" class="preview-box">
      <div class="preview-header">
        <span class="preview-filename">{{ previewFile }}</span>
        <div class="preview-actions">
          <button class="btn-icon" @click="copyContent" title="复制">📋</button>
          <button class="btn-icon" @click="closePreview" title="关闭">✕</button>
        </div>
      </div>
      <div v-if="previewContent" class="preview-code">
        <pre><code v-html="highlightedContent"></code></pre>
      </div>
      <div v-else class="preview-empty">文件内容为空</div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import JSZip from 'jszip'
import { saveAs } from 'file-saver'
import { useProjectStore } from '../stores/project.js'
import { useFilePreview } from '../composables/useFilePreview.js'

const projectStore = useProjectStore()
const downloading = ref(false)

const { previewFile, previewContent, highlightedContent, openPreview, closePreview, copyContent } = useFilePreview()

// 源码文件扩展名
const SOURCE_EXTS = ['.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.vue', '.json', '.yaml', '.yml', '.toml']
// 启动脚本
const APP_FILES = ['start.sh', 'start.bat', 'requirements.txt', 'package.json', 'Dockerfile', 'docker-compose.yml']

function getFileIcon(path) {
  if (path.endsWith('.py')) return '🐍'
  if (path.endsWith('.html')) return '🌐'
  if (path.endsWith('.css')) return '🎨'
  if (path.endsWith('.js') || path.endsWith('.ts')) return '⚡'
  if (path.endsWith('.json')) return '📋'
  if (path.endsWith('.sh') || path.endsWith('.bat')) return '⚙️'
  return '📄'
}

function isSourceFile(path) {
  return SOURCE_EXTS.some(ext => path.endsWith(ext))
}

function isAppFile(path) {
  return APP_FILES.some(name => path.endsWith(name)) || isSourceFile(path)
}

function togglePreview(path, content) {
  if (previewFile.value === path) {
    closePreview()
  } else {
    openPreview(path, content)
  }
}

function downloadSingle(path, content) {
  const blob = new Blob([content], { type: 'text/plain' })
  saveAs(blob, path.split('/').pop())
}

async function createZip(files, zipName) {
  downloading.value = true
  try {
    const zip = new JSZip()
    for (const [path, content] of Object.entries(files)) {
      zip.file(path, content)
    }
    const blob = await zip.generateAsync({ type: 'blob' })
    saveAs(blob, `${zipName}.zip`)
  } finally {
    downloading.value = false
  }
}

function downloadSource() {
  const sourceFiles = {}
  for (const [path, content] of Object.entries(projectStore.files)) {
    if (isSourceFile(path)) sourceFiles[path] = content
  }
  if (Object.keys(sourceFiles).length === 0) {
    alert('没有源码文件')
    return
  }
  createZip(sourceFiles, 'source-code')
}

function downloadApp() {
  const appFiles = {}
  for (const [path, content] of Object.entries(projectStore.files)) {
    if (isAppFile(path)) appFiles[path] = content
  }
  if (Object.keys(appFiles).length === 0) {
    alert('没有可运行的应用文件')
    return
  }
  createZip(appFiles, 'application')
}

function downloadAll() {
  createZip(projectStore.files, 'project')
}
</script>

<style scoped>
.output-panel { margin-top: 20px; padding: 16px; background: var(--bg); border-radius: var(--radius); border: 1px solid var(--border); }
.output-title { font-size: 12px; font-weight: 600; color: var(--text-dim); margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px; }
.file-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 13px; }
.file-icon { font-size: 14px; }
.file-name { flex: 1; font-family: monospace; }
.file-name.clickable { cursor: pointer; color: var(--primary); }
.file-name.clickable:hover { text-decoration: underline; }
.btn-sm { font-size: 11px; padding: 2px 8px; border: 1px solid var(--border); border-radius: 4px; background: transparent; cursor: pointer; }
.btn-sm:hover { border-color: var(--primary); color: var(--primary); }
.download-options { display: flex; gap: 8px; margin-top: 16px; }
.btn-download { flex: 1; padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius); background: transparent; cursor: pointer; font-size: 12px; font-weight: 500; text-align: center; transition: all 0.15s; }
.btn-download:hover { border-color: var(--primary); color: var(--primary); background: var(--accent-glow); }
.btn-download:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-download-primary { border-color: var(--primary); color: var(--primary); }
.btn-download-primary:hover { background: var(--primary); color: #fff; }
.preview-box { margin-top: 16px; border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.preview-header { display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; background: var(--bg-panel); font-size: 13px; font-weight: 500; }
.preview-filename { font-family: monospace; }
.preview-actions { display: flex; gap: 4px; }
.preview-header .btn-icon { background: none; border: none; cursor: pointer; font-size: 14px; color: var(--text-dim); padding: 2px 4px; border-radius: 4px; }
.preview-header .btn-icon:hover { color: var(--primary); background: var(--bg); }
.preview-code { max-height: 400px; overflow: auto; background: var(--bg); }
.preview-code pre { padding: 16px; margin: 0; font-size: 13px; line-height: 1.6; }
.preview-code code { font-family: monospace; }
.preview-empty { padding: 24px; text-align: center; color: var(--text-dim); font-size: 13px; }
</style>
