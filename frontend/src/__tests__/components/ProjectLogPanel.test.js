import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ProjectLogPanel from '../../components/project/ProjectLogPanel.vue'

describe('ProjectLogPanel', () => {
  it('renders with empty state', () => {
    const wrapper = mount(ProjectLogPanel, {
      props: { projectId: 'test-123' }
    })
    expect(wrapper.text()).toContain('开发日志')
  })
})
