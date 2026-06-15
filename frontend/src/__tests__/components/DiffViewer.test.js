import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DiffViewer from '../../components/DiffViewer.vue'
import { api } from '../../api/index.js'

vi.mock('../../api/index.js', () => ({
  api: {
    getSnapshots: vi.fn(),
    getDiff: vi.fn()
  }
}))

describe('DiffViewer', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads snapshots for dropdowns', async () => {
    api.getSnapshots.mockResolvedValue({
      snapshots: [
        { id: 'snap1', iteration: 1, label: '迭代1' },
        { id: 'snap2', iteration: 2, label: '迭代2' },
      ]
    })
    api.getDiff.mockResolvedValue({ files: [] })
    const wrapper = mount(DiffViewer, { props: { projectId: 'p1' } })
    await flushPromises()
    expect(api.getSnapshots).toHaveBeenCalledWith('p1')
    expect(wrapper.findAll('select').length).toBe(2)
  })

  it('fetches diff when both snapshots selected', async () => {
    api.getSnapshots.mockResolvedValue({
      snapshots: [
        { id: 'snap1', iteration: 1, label: '迭代1' },
        { id: 'snap2', iteration: 2, label: '迭代2' },
      ]
    })
    api.getDiff.mockResolvedValue({
      files: [
        { path: 'main.py', type: 'modified', hunks: [{ oldStart: 1, newStart: 1, lines: ['-old', '+new'] }] }
      ]
    })
    const wrapper = mount(DiffViewer, { props: { projectId: 'p1' } })
    await flushPromises()

    const selects = wrapper.findAll('select')
    await selects[0].setValue('snap1')
    await selects[1].setValue('snap2')
    await flushPromises()

    expect(api.getDiff).toHaveBeenCalledWith('p1', 'snap1', 'snap2')
  })

  it('shows error state on API failure', async () => {
    api.getSnapshots.mockRejectedValue(new Error('Snapshots unavailable'))
    const wrapper = mount(DiffViewer, { props: { projectId: 'p1' } })
    await flushPromises()
    expect(wrapper.text()).toContain('Snapshots unavailable')
  })

  it('renders diff lines with +/- styling', async () => {
    api.getSnapshots.mockResolvedValue({ snapshots: [{ id: 's1', iteration: 1 }, { id: 's2', iteration: 2 }] })
    api.getDiff.mockResolvedValue({
      files: [
        { path: 'app.py', type: 'modified', hunks: [{ oldStart: 1, newStart: 1, lines: ['-old line', '+new line'] }] }
      ]
    })
    const wrapper = mount(DiffViewer, { props: { projectId: 'p1' } })
    await flushPromises()
    const selects = wrapper.findAll('select')
    await selects[0].setValue('s1')
    await selects[1].setValue('s2')
    await flushPromises()

    expect(wrapper.text()).toContain('app.py')
    expect(wrapper.text()).toContain('modified')
    expect(wrapper.find('.diff-del').exists()).toBe(true)
    expect(wrapper.find('.diff-add').exists()).toBe(true)
  })
})
