import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useWsStore } from '../../stores/websocket.js'
import LoadingBar from '../../components/LoadingBar.vue'

describe('LoadingBar', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('未重连时不显示', () => {
    const wrapper = mount(LoadingBar)
    expect(wrapper.find('.reconnect-bar').exists()).toBe(false)
  })

  it('重连中时显示提示', async () => {
    const store = useWsStore()
    store.reconnecting = true
    const wrapper = mount(LoadingBar)
    expect(wrapper.text()).toContain('正在重连')
  })
})
