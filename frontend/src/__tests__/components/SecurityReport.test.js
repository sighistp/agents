import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import SecurityReport from '../../components/SecurityReport.vue'
import { api } from '../../api/index.js'

vi.mock('../../api/index.js', () => ({
  api: { getSecurityReport: vi.fn() }
}))

describe('SecurityReport', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('shows loading state initially', () => {
    api.getSecurityReport.mockReturnValue(new Promise(() => {}))
    const wrapper = mount(SecurityReport, { props: { projectId: 'p1' } })
    expect(wrapper.text()).toContain('加载中')
  })

  it('renders score and severity badges', async () => {
    api.getSecurityReport.mockResolvedValue({
      score: 75,
      issues: [
        { severity: 'critical', file: 'auth.py', line: 42, description: 'SQL注入风险' },
        { severity: 'high', file: 'db.py', line: 10, description: '硬编码密码' },
        { severity: 'medium', file: 'api.py', line: 55, description: '缺少CSRF防护' },
        { severity: 'low', file: 'utils.py', line: 3, description: '日志过多' },
      ]
    })
    const wrapper = mount(SecurityReport, { props: { projectId: 'p1' } })
    await flushPromises()
    expect(wrapper.text()).toContain('75')
    expect(wrapper.text()).toContain('SQL注入风险')
    expect(wrapper.text()).toContain('auth.py:42')
    expect(wrapper.find('.severity-critical').exists()).toBe(true)
    expect(wrapper.find('.severity-high').exists()).toBe(true)
  })

  it('shows error state on API failure', async () => {
    api.getSecurityReport.mockRejectedValue(new Error('Scan failed'))
    const wrapper = mount(SecurityReport, { props: { projectId: 'p1' } })
    await flushPromises()
    expect(wrapper.text()).toContain('Scan failed')
  })

  it('shows empty state when no issues', async () => {
    api.getSecurityReport.mockResolvedValue({
      score: 100,
      issues: []
    })
    const wrapper = mount(SecurityReport, { props: { projectId: 'p1' } })
    await flushPromises()
    expect(wrapper.text()).toContain('100')
    expect(wrapper.text()).toContain('无安全问题')
  })
})
