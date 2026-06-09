import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../stores/auth.js'

describe('router guard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('未登录时访问受保护路由应重定向到 /login', async () => {
    const { default: router } = await import('../router.js')
    const authStore = useAuthStore()
    expect(authStore.isLoggedIn).toBe(false)
    await router.push('/')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('已登录时访问 /login 应重定向到 /', async () => {
    const { default: router } = await import('../router.js')
    const authStore = useAuthStore()
    authStore.setAuth('test-token', 'testuser')
    await router.push('/login')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('已登录时可以访问受保护路由', async () => {
    const { default: router } = await import('../router.js')
    const authStore = useAuthStore()
    authStore.setAuth('test-token', 'testuser')
    await router.push('/projects')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/projects')
  })
})
