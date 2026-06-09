import { defineStore } from 'pinia'

export const useWsStore = defineStore('ws', {
  state: () => ({
    isConnected: false,
    reconnecting: false,
    lastError: null,
  }),
})
