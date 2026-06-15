import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import QualityScore from '../../components/QualityScore.vue'
import { api } from '../../api/index.js'

vi.mock('../../api/index.js', () => ({
  api: { getQualityScore: vi.fn() }
}))

describe('QualityScore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('shows loading state initially', () => {
    api.getQualityScore.mockReturnValue(new Promise(() => {}))
    const wrapper = mount(QualityScore, { props: { projectId: 'p1' } })
    expect(wrapper.text()).toContain('加载中')
  })

  it('renders score and grade after load', async () => {
    api.getQualityScore.mockResolvedValue({
      total_score: 85,
      grade: 'B',
      dimensions: [
        { name: '代码规范', score: 90 },
        { name: '测试覆盖', score: 80 },
        { name: '文档完整', score: 70 },
        { name: '安全性', score: 85 },
        { name: '性能', score: 95 },
      ],
      suggestions: ['增加单元测试', '完善文档']
    })
    const wrapper = mount(QualityScore, { props: { projectId: 'p1' } })
    await flushPromises()
    expect(wrapper.text()).toContain('85')
    expect(wrapper.text()).toContain('B')
    expect(wrapper.text()).toContain('代码规范')
    expect(wrapper.text()).toContain('增加单元测试')
  })

  it('shows error state on API failure', async () => {
    api.getQualityScore.mockRejectedValue(new Error('Network error'))
    const wrapper = mount(QualityScore, { props: { projectId: 'p1' } })
    await flushPromises()
    expect(wrapper.text()).toContain('Network error')
  })

  it('renders green color class for score > 80', async () => {
    api.getQualityScore.mockResolvedValue({
      total_score: 90,
      grade: 'A',
      dimensions: [],
      suggestions: []
    })
    const wrapper = mount(QualityScore, { props: { projectId: 'p1' } })
    await flushPromises()
    expect(wrapper.find('.score-green').exists()).toBe(true)
  })

  it('renders yellow color class for score 50-80', async () => {
    api.getQualityScore.mockResolvedValue({
      total_score: 65,
      grade: 'C',
      dimensions: [],
      suggestions: []
    })
    const wrapper = mount(QualityScore, { props: { projectId: 'p1' } })
    await flushPromises()
    expect(wrapper.find('.score-yellow').exists()).toBe(true)
  })

  it('renders red color class for score < 50', async () => {
    api.getQualityScore.mockResolvedValue({
      total_score: 30,
      grade: 'F',
      dimensions: [],
      suggestions: []
    })
    const wrapper = mount(QualityScore, { props: { projectId: 'p1' } })
    await flushPromises()
    expect(wrapper.find('.score-red').exists()).toBe(true)
  })
})
