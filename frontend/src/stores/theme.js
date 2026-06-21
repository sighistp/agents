import { defineStore } from 'pinia'

export const useThemeStore = defineStore('theme', {
  state: () => ({
    mode: localStorage.getItem('theme') || 'system', // 'system' | 'light' | 'dark'
  }),
  getters: {
    isDark: (state) => {
      if (state.mode === 'dark') return true
      if (state.mode === 'light') return false
      return window.matchMedia('(prefers-color-scheme: dark)').matches
    },
  },
  actions: {
    setMode(mode) {
      this.mode = mode
      localStorage.setItem('theme', mode)
      this._apply()
    },
    toggle() {
      const next = this.isDark ? 'light' : 'dark'
      this.setMode(next)
    },
    _apply() {
      document.documentElement.classList.toggle('dark', this.isDark)
    },
    init() {
      this._apply()
      // Listen for system theme changes
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        if (this.mode === 'system') this._apply()
      })
    },
  },
})
