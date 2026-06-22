import { defineStore } from 'pinia'

export const useWsStore = defineStore('ws', {
  state: () => ({
    isConnected: false,
    reconnecting: false,
    lastError: null,
  }),
  actions: {
    setConnected(val) { this.isConnected = val },
    setReconnecting(val) { this.reconnecting = val },
    setError(val) { this.lastError = val },
  },
})
