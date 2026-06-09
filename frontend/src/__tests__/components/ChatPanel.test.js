import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useProjectStore } from '../../stores/project.js'
import ChatPanel from '../../components/ChatPanel.vue'

vi.mock('../../composables/useWebSocket.js', () => ({
  useWebSocket: () => ({ send: vi.fn(), connect: vi.fn(), disconnect: vi.fn() }),
  setActiveProject: vi.fn(),
}))

describe('ChatPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('显示已有消息', () => {
    const store = useProjectStore()
    store.addMessage({ role: 'user', name: 'user', content: '做一个计算器' })
    store.addMessage({ role: 'assistant', name: 'pm', content: '收到需求' })

    const wrapper = mount(ChatPanel)
    expect(wrapper.text()).toContain('做一个计算器')
    expect(wrapper.text()).toContain('收到需求')
  })

  it('输入框回车发送消息', async () => {
    const store = useProjectStore()
    const wrapper = mount(ChatPanel)

    const textarea = wrapper.find('textarea')
    await textarea.setValue('测试需求')
    await textarea.trigger('keydown.enter')

    expect(store.messages.some(m => m.content === '测试需求')).toBe(true)
  })

  it('空消息不发送', async () => {
    const store = useProjectStore()
    const wrapper = mount(ChatPanel)

    const textarea = wrapper.find('textarea')
    await textarea.setValue('   ')
    await textarea.trigger('keydown.enter')

    expect(store.messages).toHaveLength(0)
  })

  it('发送后清空输入框', async () => {
    const store = useProjectStore()
    const wrapper = mount(ChatPanel)

    const textarea = wrapper.find('textarea')
    await textarea.setValue('测试需求')
    await textarea.trigger('keydown.enter')

    expect(textarea.element.value).toBe('')
  })

  it('渲染 tool 消息', () => {
    const store = useProjectStore()
    store.addMessage({ role: 'tool', name: 'tool', content: '{"success": true, "path": "main.py"}' })
    const wrapper = mount(ChatPanel)
    expect(wrapper.text()).toContain('main.py')
  })

  it('渲染带 tool_calls 的 assistant 消息', () => {
    const store = useProjectStore()
    store.addMessage({
      role: 'assistant', name: 'developer',
      content: '',
      tool_calls: [{ function: { name: 'file_write', arguments: '{"path":"main.py"}' } }]
    })
    const wrapper = mount(ChatPanel)
    expect(wrapper.text()).toContain('main.py')
  })
})
