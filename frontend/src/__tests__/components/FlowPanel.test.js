import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useProjectStore } from '../../stores/project.js'
import FlowPanel from '../../components/FlowPanel.vue'

describe('FlowPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('显示 5 个 Agent 卡片', () => {
    const wrapper = mount(FlowPanel)
    const cards = wrapper.findAll('.agent-card')
    expect(cards).toHaveLength(5)
  })

  it('Agent 状态变化时卡片自动更新', async () => {
    const store = useProjectStore()
    const wrapper = mount(FlowPanel)
    store.setAgentStatus('pm', 'running')
    await wrapper.vm.$nextTick()
    const pmCard = wrapper.find('.agent-pm')
    expect(pmCard.classes()).toContain('running')
  })

  it('iteration > 0 时显示迭代信息', async () => {
    const store = useProjectStore()
    store.iteration = 2
    store.maxIterations = 3
    const wrapper = mount(FlowPanel)
    expect(wrapper.text()).toContain('迭代进度')
    expect(wrapper.text()).toContain('2 / 3')
  })
})
