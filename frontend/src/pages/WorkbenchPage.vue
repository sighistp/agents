<template>
  <div class="workbench">
    <FlowPanel />
    <ChatPanel />
  </div>
</template>

<script setup>
import FlowPanel from '../components/FlowPanel.vue'
import ChatPanel from '../components/ChatPanel.vue'
</script>

<style scoped>
.workbench { display: flex; height: calc(100vh - 49px); }
</style>
