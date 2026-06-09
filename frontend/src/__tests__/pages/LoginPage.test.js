import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import LoginPage from '../../pages/LoginPage.vue'

vi.mock('../../composables/useWebSocket.js', () => ({
  useWebSocket: () => ({ send: vi.fn(), connect: vi.fn(), disconnect: vi.fn() }),
}))

vi.mock('../../api/index.js', () => ({
  api: {
    login: vi.fn().mockResolvedValue({ token: 'abc', username: 'user' }),
    register: vi.fn().mockResolvedValue({ token: 'abc', username: 'user' }),
  },
}))

describe('LoginPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('显示登录表单', () => {
    const wrapper = mount(LoginPage)
    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
    expect(wrapper.find('button[type="submit"]').exists()).toBe(true)
  })

  it('默认显示登录模式', () => {
    const wrapper = mount(LoginPage)
    expect(wrapper.find('button[type="submit"]').text()).toBe('登录')
    expect(wrapper.text()).toContain('没有账号？去注册')
  })

  it('点击切换到注册模式', async () => {
    const wrapper = mount(LoginPage)
    await wrapper.find('.toggle').trigger('click')
    expect(wrapper.find('button[type="submit"]').text()).toBe('注册')
  })
})
