<template>
  <div class="settings-page">
    <div class="settings-card">
      <h2>系统设置</h2>
      <form @submit.prevent="save">
        <!-- API 预设 -->
        <div class="section-title">API 预设</div>
        <div class="preset-bar">
          <select v-model="selectedPreset" class="preset-select" @change="applyPreset">
            <option value="">选择预设...</option>
            <option v-for="(_, name) in presets" :key="name" :value="name">{{ name }}</option>
          </select>
          <input v-model="newPresetName" type="text" placeholder="预设名称" class="preset-name-input" />
          <button type="button" class="btn-sm" @click="savePreset" :disabled="!newPresetName">保存当前</button>
          <button type="button" class="btn-sm btn-danger" @click="deletePreset" :disabled="!selectedPreset">删除</button>
        </div>

        <!-- LLM 配置 -->
        <div class="section-title">LLM 配置</div>
        <div class="form-group">
          <label>API Key</label>
          <input v-model="form.api_key" type="password" placeholder="留空保持原值" />
        </div>
        <div class="form-group">
          <label>Base URL</label>
          <input v-model="form.base_url" type="text" />
        </div>
        <div class="form-group">
          <label>模型</label>
          <input v-model="form.model" type="text" />
        </div>

        <!-- Agent 配置 -->
        <div class="section-title">Agent 配置</div>
        <div class="form-group">
          <label>最大迭代次数</label>
          <input v-model.number="form.max_iterations" type="number" min="1" max="10" />
        </div>
        <div class="form-group">
          <label>执行模式</label>
          <div class="radio-group">
            <label><input type="radio" v-model="form.agent_mode" value="max" /> max（质量优先，开启讨论）</label>
            <label><input type="radio" v-model="form.agent_mode" value="mini" /> mini（速度优先，跳过讨论）</label>
          </div>
        </div>

        <p v-if="message" :class="['msg', success ? 'success' : 'error']">{{ message }}</p>
        <div class="actions">
          <button type="button" class="btn-secondary" @click="$router.push('/')">返回</button>
          <button type="submit" class="btn-primary" :disabled="saving">保存设置</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/index.js'

const form = ref({ api_key: '', base_url: '', model: '', max_iterations: 3, agent_mode: 'mini' })
const saving = ref(false)
const message = ref('')
const success = ref(false)
const presets = ref({})
const selectedPreset = ref('')
const newPresetName = ref('')

onMounted(async () => {
  try {
    const data = await api.getSettings()
    form.value = { ...form.value, ...data }
  } catch (e) { message.value = '加载设置失败' }
  loadPresets()
})

async function loadPresets() {
  try {
    presets.value = await api.getPresets()
  } catch {}
}

async function save() {
  saving.value = true; message.value = ''
  try {
    const payload = { ...form.value }
    if (!payload.api_key) delete payload.api_key
    await api.updateSettings(payload)
    message.value = '设置已保存'; success.value = true
  } catch (e) { message.value = e.message; success.value = false }
  finally { saving.value = false }
}

async function savePreset() {
  if (!newPresetName.value) return
  try {
    await api.savePreset(newPresetName.value)
    message.value = `预设 "${newPresetName.value}" 已保存`; success.value = true
    newPresetName.value = ''
    loadPresets()
  } catch (e) { message.value = e.message; success.value = false }
}

async function applyPreset() {
  if (!selectedPreset.value) return
  try {
    await api.applyPreset(selectedPreset.value)
    const data = await api.getSettings()
    form.value = { ...form.value, ...data }
    message.value = `已切换到 "${selectedPreset.value}"`; success.value = true
  } catch (e) { message.value = e.message; success.value = false }
}

async function deletePreset() {
  if (!selectedPreset.value) return
  try {
    await api.deletePreset(selectedPreset.value)
    message.value = `预设 "${selectedPreset.value}" 已删除`; success.value = true
    selectedPreset.value = ''
    loadPresets()
  } catch (e) { message.value = e.message; success.value = false }
}
</script>

<style scoped>
.settings-page { display: flex; justify-content: center; padding: 32px; }
.settings-card { background: var(--bg); border: 1px solid var(--border); border-radius: 12px; padding: 32px; width: 100%; max-width: 520px; }
.settings-card h2 { margin-bottom: 24px; }
.section-title { font-size: 12px; font-weight: 600; color: var(--primary); text-transform: uppercase; letter-spacing: 1px; margin: 20px 0 12px; padding-top: 16px; border-top: 1px solid var(--border); }
.section-title:first-of-type { border-top: none; margin-top: 0; padding-top: 0; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 13px; color: var(--text-dim); margin-bottom: 4px; }
.form-group input[type="text"], .form-group input[type="password"], .form-group input[type="number"] { width: 100%; padding: 8px 12px; border: 1px solid var(--border); border-radius: var(--radius); font-size: 13px; }
.form-group input:focus { outline: none; border-color: var(--primary); }
.radio-group { display: flex; flex-direction: column; gap: 8px; }
.radio-group label { font-size: 13px; display: flex; align-items: center; gap: 6px; }
.msg { font-size: 13px; margin: 12px 0; }
.msg.success { color: var(--success); }
.msg.error { color: var(--error); }
.actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 20px; }
.btn-primary { background: var(--primary); color: #fff; border: none; padding: 8px 20px; border-radius: var(--radius); cursor: pointer; }
.btn-primary:disabled { opacity: 0.6; }
.btn-secondary { background: transparent; border: 1px solid var(--border); padding: 8px 20px; border-radius: var(--radius); cursor: pointer; }
.btn-sm { padding: 6px 12px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--bg-panel); cursor: pointer; font-size: 12px; }
.btn-sm:hover { border-color: var(--primary); }
.btn-sm:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-danger { border-color: var(--error); color: var(--error); }
.btn-danger:hover { background: rgba(239,68,68,0.1); }
.preset-bar { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.preset-select { flex: 1; padding: 8px 12px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--bg-input); color: var(--text); font-size: 13px; }
.preset-name-input { width: 120px; padding: 8px 12px; border: 1px solid var(--border); border-radius: var(--radius); font-size: 13px; }
</style>
