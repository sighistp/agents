import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../../stores/auth.js'

describe('authStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('默认未登录', () => {
    const store = useAuthStore()
    expect(store.isLoggedIn).toBe(false)
    expect(store.token).toBeNull()
    expect(store.username).toBeNull()
  })

  it('setAuth 保存 token 和 username 到 state 和 localStorage', () => {
    const store = useAuthStore()
    store.setAuth('test-token', 'testuser')
    expect(store.token).toBe('test-token')
    expect(store.username).toBe('testuser')
    expect(store.isLoggedIn).toBe(true)
    expect(localStorage.getItem('token')).toBe('test-token')
    expect(localStorage.getItem('username')).toBe('testuser')
  })

  it('clearAuth 清除 state 和 localStorage', () => {
    const store = useAuthStore()
    store.setAuth('test-token', 'testuser')
    store.clearAuth()
    expect(store.token).toBeNull()
    expect(store.username).toBeNull()
    expect(store.isLoggedIn).toBe(false)
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('从 localStorage 恢复 token', () => {
    localStorage.setItem('token', 'saved-token')
    localStorage.setItem('username', 'saved-user')
    const store = useAuthStore()
    expect(store.token).toBe('saved-token')
    expect(store.username).toBe('saved-user')
    expect(store.isLoggedIn).toBe(true)
  })
})
