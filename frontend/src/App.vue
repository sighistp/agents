<template>
  <LoadingBar />
  <InterruptDialog />
  <div class="app-layout">
    <nav v-if="authStore.isLoggedIn" class="navbar">
      <div class="nav-brand">DevTeam</div>
      <div class="nav-links">
        <router-link to="/">工作台</router-link>
        <router-link to="/projects">项目</router-link>
        <router-link to="/settings">设置</router-link>
      </div>
      <AgentStatusBar />
      <div class="nav-user">
        <span>{{ authStore.username }}</span>
        <button @click="logout">退出</button>
      </div>
    </nav>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth.js'
import { useWebSocket } from './composables/useWebSocket.js'
import LoadingBar from './components/LoadingBar.vue'
import AgentStatusBar from './components/AgentStatusBar.vue'
import InterruptDialog from './components/InterruptDialog.vue'

const authStore = useAuthStore()
const router = useRouter()
const { connect, disconnect } = useWebSocket()

onMounted(() => { if (authStore.isLoggedIn) connect() })
onUnmounted(() => { disconnect() })

function logout() {
  disconnect()
  authStore.clearAuth()
  router.push('/login')
}
</script>

<style scoped>
.app-layout { min-height: 100vh; display: flex; flex-direction: column; }
.navbar { display: flex; align-items: center; justify-content: space-between; padding: 12px 24px; background: var(--bg); border-bottom: 1px solid var(--border); }
.nav-brand { font-weight: 700; font-size: 18px; color: var(--primary); }
.nav-links { display: flex; gap: 16px; }
.nav-links a { color: var(--text-dim); text-decoration: none; font-size: 14px; }
.nav-links a.router-link-active { color: var(--primary); }
.nav-user { display: flex; align-items: center; gap: 12px; font-size: 13px; color: var(--text-dim); }
.nav-user button { background: none; border: 1px solid var(--border); border-radius: var(--radius); padding: 4px 12px; cursor: pointer; font-size: 12px; }
.main-content { flex: 1; }
</style>
