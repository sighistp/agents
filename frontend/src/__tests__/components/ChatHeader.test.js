import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '../../stores/project.js'
import { useWsStore } from '../../stores/websocket.js'
import ChatHeader from '../../components/ChatHeader.vue'

describe('ChatHeader', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('空闲状态显示保存/清空/新建，无暂停', () => {
    const wrapper = mount(ChatHeader)
    expect(wrapper.find('[title="保存项目"]').exists()).toBe(true)
    expect(wrapper.find('[title="清空聊天"]').exists()).toBe(true)
    expect(wrapper.find('[title="新建对话"]').exists()).toBe(true)
    expect(wrapper.find('[title="暂停"]').exists()).toBe(false)
    expect(wrapper.find('[title="继续"]').exists()).toBe(false)
  })

  it('运行中显示暂停按钮', () => {
    const store = useProjectStore()
    store.isRunning = true
    store.isPaused = false
    const wrapper = mount(ChatHeader)
    expect(wrapper.find('[title="暂停"]').exists()).toBe(true)
    expect(wrapper.find('[title="继续"]').exists()).toBe(false)
  })

  it('已暂停显示继续和停止按钮', () => {
    const store = useProjectStore()
    store.isRunning = true
    store.isPaused = true
    const wrapper = mount(ChatHeader)
    expect(wrapper.find('[title="继续"]').exists()).toBe(true)
    expect(wrapper.find('[title="停止"]').exists()).toBe(true)
    expect(wrapper.find('[title="暂停"]').exists()).toBe(false)
  })

  it('点击暂停 emit pause 事件', async () => {
    const store = useProjectStore()
    const wsStore = useWsStore()
    store.isRunning = true
    wsStore.isConnected = true
    const wrapper = mount(ChatHeader)
    await wrapper.find('[title="暂停"]').trigger('click')
    expect(wrapper.emitted('pause')).toBeTruthy()
  })

  it('点击继续 emit resume 事件', async () => {
    const store = useProjectStore()
    const wsStore = useWsStore()
    store.isRunning = true
    store.isPaused = true
    wsStore.isConnected = true
    const wrapper = mount(ChatHeader)
    await wrapper.find('[title="继续"]').trigger('click')
    expect(wrapper.emitted('resume')).toBeTruthy()
  })

  it('点击停止 emit stop 事件', async () => {
    const store = useProjectStore()
    const wsStore = useWsStore()
    store.isRunning = true
    store.isPaused = true
    wsStore.isConnected = true
    const wrapper = mount(ChatHeader)
    await wrapper.find('[title="停止"]').trigger('click')
    expect(wrapper.emitted('stop')).toBeTruthy()
  })
})
