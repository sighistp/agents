import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useProjectStore } from '../../stores/project.js'
import InterruptDialog from '../../components/InterruptDialog.vue'

vi.mock('../../composables/useWebSocket.js', () => ({
  useWebSocket: () => ({ send: vi.fn() }),
}))

describe('InterruptDialog', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('无 interrupt 时不显示', () => {
    const wrapper = mount(InterruptDialog)
    expect(wrapper.find('.overlay').exists()).toBe(false)
  })

  it('有 interrupt 时显示对话框', async () => {
    const store = useProjectStore()
    store.interrupt = { type: 'confirm', message: '请确认架构设计' }
    const wrapper = mount(InterruptDialog)
    expect(wrapper.find('.overlay').exists()).toBe(true)
    expect(wrapper.text()).toContain('请确认架构设计')
  })

  it('clarify 类型显示不同标题', async () => {
    const store = useProjectStore()
    store.interrupt = { type: 'clarify', message: '需求不明确', questions: ['目标用户是谁？'] }
    const wrapper = mount(InterruptDialog)
    expect(wrapper.text()).toContain('需要补充信息')
    expect(wrapper.text()).toContain('目标用户是谁？')
  })
})
