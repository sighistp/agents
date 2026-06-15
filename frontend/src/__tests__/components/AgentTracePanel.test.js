import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import AgentTracePanel from '../../components/AgentTracePanel.vue'
import { api } from '../../api/index.js'

vi.mock('../../api/index.js', () => ({
  api: { getTraces: vi.fn() }
}))

describe('AgentTracePanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('shows loading state initially', () => {
    api.getTraces.mockReturnValue(new Promise(() => {}))
    const wrapper = mount(AgentTracePanel, { props: { projectId: 'p1' } })
    expect(wrapper.text()).toContain('加载中')
  })

  it('renders trace items after load', async () => {
    api.getTraces.mockResolvedValue({
      traces: [
        {
          id: 1,
          agent: 'developer',
          iteration: 1,
          prompt: '请实现用户登录功能',
          response: '已实现登录页面',
          tools: ['write_file', 'run_command']
        },
        {
          id: 2,
          agent: 'tester',
          iteration: 1,
          prompt: '测试登录功能',
          response: '测试通过',
          tools: ['run_test']
        }
      ]
    })
    const wrapper = mount(AgentTracePanel, { props: { projectId: 'p1' } })
    await flushPromises()
    expect(wrapper.text()).toContain('developer')
    expect(wrapper.text()).toContain('write_file')
    await wrapper.find('.trace-header').trigger('click')
    expect(wrapper.text()).toContain('请实现用户登录功能')
  })

  it('shows error state on API failure', async () => {
    api.getTraces.mockRejectedValue(new Error('Traces unavailable'))
    const wrapper = mount(AgentTracePanel, { props: { projectId: 'p1' } })
    await flushPromises()
    expect(wrapper.text()).toContain('Traces unavailable')
  })

  it('expands/collapses trace items on click', async () => {
    api.getTraces.mockResolvedValue({
      traces: [
        {
          id: 1,
          agent: 'developer',
          iteration: 1,
          prompt: '请实现功能',
          response: '已实现',
          tools: ['write_file']
        }
      ]
    })
    const wrapper = mount(AgentTracePanel, { props: { projectId: 'p1' } })
    await flushPromises()

    const header = wrapper.find('.trace-header')
    expect(header.exists()).toBe(true)

    const body = wrapper.find('.trace-body')
    expect(body.exists()).toBe(false)

    await header.trigger('click')
    expect(wrapper.find('.trace-body').exists()).toBe(true)

    await header.trigger('click')
    expect(wrapper.find('.trace-body').exists()).toBe(false)
  })

  it('passes agent and iteration params to API', async () => {
    api.getTraces.mockResolvedValue({ traces: [] })
    mount(AgentTracePanel, { props: { projectId: 'p1', agent: 'tester', iteration: 2 } })
    await flushPromises()
    expect(api.getTraces).toHaveBeenCalledWith('p1', 'tester', 2)
  })
})
