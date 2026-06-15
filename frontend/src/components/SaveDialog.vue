<!-- frontend/src/components/SaveDialog.vue -->
<template>
  <div v-if="visible" class="save-overlay" @click.self="cancel">
    <div class="save-dialog">
      <div class="dialog-title">💾 保存项目</div>
      <div class="dialog-label">项目名称</div>
      <input
        v-model="name"
        class="dialog-input"
        maxlength="50"
        placeholder="输入项目名称..."
        @keydown.enter="confirm"
      />
      <div class="dialog-hint">自动生成，可修改</div>
      <div v-if="localError || error" class="dialog-error">{{ localError || error }}</div>
      <div class="dialog-actions">
        <button class="btn-cancel" @click="cancel">取消</button>
        <button class="btn-confirm" @click="confirm">保存</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  visible: Boolean,
  defaultName: String,
  error: { type: String, default: '' }
})
const emit = defineEmits(['update:visible', 'save'])

const name = ref('')
const localError = ref('')

watch(() => props.visible, (v) => {
  if (v) { name.value = props.defaultName || ''; localError.value = '' }
}, { immediate: true })

function confirm() {
  const finalName = (name.value || props.defaultName || '未命名项目').slice(0, 50)
  if (!finalName.trim()) { localError.value = '名称不能为空'; return }
  localError.value = ''
  emit('save', finalName)
}

function cancel() { emit('update:visible', false) }
</script>

<style scoped>
.save-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.save-dialog { background: var(--bg); border-radius: 12px; padding: 24px; width: 360px; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.dialog-title { font-weight: 600; font-size: 16px; margin-bottom: 16px; }
.dialog-label { font-size: 13px; color: var(--text-dim); margin-bottom: 6px; }
.dialog-input { width: 100%; border: 2px solid var(--primary); border-radius: 8px; padding: 10px 14px; font-size: 14px; box-sizing: border-box; outline: none; }
.dialog-hint { font-size: 11px; color: var(--text-dim); margin-top: 4px; }
.dialog-error { font-size: 12px; color: #EF4444; margin-top: 8px; }
.dialog-actions { display: flex; gap: 8px; margin-top: 20px; justify-content: flex-end; }
.btn-cancel { background: var(--bg-panel); border: 1px solid var(--border); border-radius: 8px; padding: 8px 20px; cursor: pointer; font-size: 13px; }
.btn-confirm { background: var(--primary); color: #fff; border: none; border-radius: 8px; padding: 8px 20px; cursor: pointer; font-size: 13px; }
</style>
