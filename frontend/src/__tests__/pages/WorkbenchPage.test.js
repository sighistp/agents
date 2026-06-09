import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import WorkbenchPage from '../../pages/WorkbenchPage.vue'

vi.mock('../../composables/useWebSocket.js', () => ({
  useWebSocket: () => ({ send: vi.fn(), connect: vi.fn(), disconnect: vi.fn() }),
}))

describe('WorkbenchPage', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('渲染流程面板和聊天面板', () => {
    const wrapper = mount(WorkbenchPage)
    expect(wrapper.find('.flow-panel').exists()).toBe(true)
    expect(wrapper.find('.chat-panel').exists()).toBe(true)
  })

  it('包含 5 个 Agent 卡片', () => {
    const wrapper = mount(WorkbenchPage)
    expect(wrapper.findAll('.agent-card')).toHaveLength(5)
  })
})
