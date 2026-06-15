<template>
  <div class="login-container">
    <div class="login-card">
      <h1>Blueprint</h1>
      <p class="subtitle">AI 开发团队</p>
      <form @submit.prevent="handleSubmit">
        <div class="form-group">
          <label>用户名</label>
          <input v-model="username" type="text" placeholder="输入用户名" required />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="输入密码" required />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" :disabled="loading">{{ isRegister ? '注册' : '登录' }}</button>
        <p class="toggle" @click="isRegister = !isRegister">
          {{ isRegister ? '已有账号？去登录' : '没有账号？去注册' }}
        </p>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { useWebSocket } from '../composables/useWebSocket.js'
import { api } from '../api/index.js'

const router = useRouter()
const authStore = useAuthStore()
const { connect } = useWebSocket()

const username = ref('')
const password = ref('')
const isRegister = ref(false)
const loading = ref(false)
const error = ref('')

async function handleSubmit() {
  loading.value = true
  error.value = ''
  try {
    const fn = isRegister.value ? api.register : api.login
    const data = await fn(username.value, password.value)
    authStore.setAuth(data.token, data.username || username.value)
    connect()
    router.push('/')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--bg-panel); }
.login-card { background: var(--bg); padding: 40px; border-radius: 12px; box-shadow: var(--shadow); width: 360px; }
.login-card h1 { color: var(--primary); margin-bottom: 4px; }
.subtitle { color: var(--text-dim); margin-bottom: 24px; font-size: 14px; }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; font-size: 13px; color: var(--text-dim); margin-bottom: 6px; }
.form-group input { width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius); font-size: 14px; }
.form-group input:focus { outline: none; border-color: var(--primary); }
.error { color: var(--error); font-size: 13px; margin-bottom: 12px; }
button[type="submit"] { width: 100%; padding: 10px; background: var(--primary); color: #fff; border: none; border-radius: var(--radius); font-size: 14px; cursor: pointer; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.toggle { text-align: center; margin-top: 12px; font-size: 13px; color: var(--primary); cursor: pointer; }
</style>
