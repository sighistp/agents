<template>
  <div v-if="wsStore.reconnecting" class="reconnect-bar">
    连接断开，正在重连...
  </div>
</template>

<script setup>
import { useWsStore } from '../stores/websocket.js'
const wsStore = useWsStore()
</script>

<style scoped>
.reconnect-bar { position: fixed; top: 0; left: 0; right: 0; z-index: 9999; background: var(--warning); color: #fff; text-align: center; padding: 6px; font-size: 13px; }
</style>
