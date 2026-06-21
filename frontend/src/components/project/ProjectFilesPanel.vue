<template>
  <div class="card">
    <div class="card-title">📁 生成文件</div>
    <template>
      <template v-if="fileList.length > 0">
        <div class="files-list">
          <div v-for="f in fileList" :key="f.path" class="file-item">
            <span class="file-icon">{{ getFileIcon(f.path) }}</span>
            <span class="file-name clickable" @click="toggleFilePreview(f.path, f.content)">{{ f.path }}</span>
            <button class="btn-sm" @click="downloadSingle(f.path, f.content)">下载</button>
          </div>
        </div>
        <div v-if="previewFile" class="preview-box">
          <div class="preview-header">
            <span class="preview-filename">{{ previewFile }}</span>
            <div class="preview-actions">
              <button class="btn-icon" @click="copyContent" title="复制">📋</button>
              <button class="btn-icon" @click="closePreview" title="关闭">&times;</button>
            </div>
          </div>
          <div v-if="previewContent" class="preview-code">
            <pre><code v-html="highlightedContent"></code></pre>
          </div>
          <div v-else class="preview-empty">文件内容为空</div>
        </div>
      </template>
      <div v-else class="empty-text">暂无文件</div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { saveAs } from 'file-saver'
import { useFilePreview } from '../../composables/useFilePreview.js'

const props = defineProps({
  projectId: { type: String, required: true },
  projectData: { type: Object, default: null }
})

const files = computed(() => props.projectData?.files || {})

const { previewFile, previewContent, highlightedContent, openPreview, closePreview, copyContent } = useFilePreview()

const fileList = computed(() => {
  if (!files.value) return []
  return Object.entries(files.value).map(([path, content]) => ({ path, content }))
})

function getFileIcon(path) {
  if (path.endsWith('.py')) return '🐍'
  if (path.endsWith('.html')) return '🌐'
  if (path.endsWith('.css')) return '🎨'
  if (path.endsWith('.js') || path.endsWith('.ts')) return '⚡'
  if (path.endsWith('.json')) return '📋'
  if (path.endsWith('.sh') || path.endsWith('.bat')) return '⚙️'
  return '📄'
}

function toggleFilePreview(path, content) {
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
</script>

<style scoped>
.card {
  background: var(--bg-panel, var(--bg));
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 16px;
}
.card-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.files-list { display: flex; flex-direction: column; gap: 4px; }
.file-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 13px; }
.file-icon { font-size: 14px; }
.file-name { flex: 1; font-family: monospace; }
.file-name.clickable { cursor: pointer; color: var(--primary); }
.file-name.clickable:hover { text-decoration: underline; }
.btn-sm {
  font-size: 11px;
  padding: 2px 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
}
.btn-sm:hover { border-color: var(--primary); color: var(--primary); }
.preview-box { margin-top: 16px; border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: var(--bg-panel);
  font-size: 13px;
  font-weight: 500;
}
.preview-filename { font-family: monospace; }
.preview-actions { display: flex; gap: 4px; }
.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  color: var(--text-dim);
  padding: 2px 4px;
  border-radius: 4px;
}
.btn-icon:hover { color: var(--primary); background: var(--bg); }
.preview-code { max-height: 400px; overflow: auto; background: var(--bg); }
.preview-code pre { padding: 16px; margin: 0; font-size: 13px; line-height: 1.6; }
.preview-code code { font-family: monospace; }
.preview-empty { padding: 24px; text-align: center; color: var(--text-dim); font-size: 13px; }
.skeleton-inner { display: flex; flex-direction: column; gap: 12px; padding: 8px 0; }
.skeleton-bar {
  height: 14px;
  background: linear-gradient(90deg, var(--border) 25%, transparent 50%, var(--border) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
}
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
.error-inner { display: flex; align-items: center; gap: 12px; padding: 8px 0; }
.error-text { color: #ef4444; font-size: 13px; }
.btn-retry {
  font-size: 12px;
  padding: 4px 12px;
  border: 1px solid var(--primary);
  border-radius: 4px;
  background: transparent;
  color: var(--primary);
  cursor: pointer;
}
.btn-retry:hover { background: var(--primary); color: #fff; }
.empty-text { font-size: 13px; color: var(--text-dim); padding: 16px 0; text-align: center; }
</style>
