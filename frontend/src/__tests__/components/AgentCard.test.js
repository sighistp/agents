import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AgentCard from '../../components/AgentCard.vue'

describe('AgentCard', () => {
  it('显示 Agent 名称和状态', () => {
    const wrapper = mount(AgentCard, { props: { name: 'pm', status: 'waiting' } })
    expect(wrapper.text()).toContain('PM')
    expect(wrapper.text()).toContain('等待中')
  })

  it('执行中状态显示正确文字', () => {
    const wrapper = mount(AgentCard, { props: { name: 'developer', status: 'running' } })
    expect(wrapper.text()).toContain('开发者')
    expect(wrapper.text()).toContain('执行中')
    expect(wrapper.classes()).toContain('running')
  })

  it('完成状态显示绿色', () => {
    const wrapper = mount(AgentCard, { props: { name: 'tester', status: 'done' } })
    expect(wrapper.text()).toContain('已完成')
    expect(wrapper.classes()).toContain('done')
  })

  it('默认状态为 waiting', () => {
    const wrapper = mount(AgentCard, { props: { name: 'pm' } })
    expect(wrapper.text()).toContain('等待中')
  })
})
