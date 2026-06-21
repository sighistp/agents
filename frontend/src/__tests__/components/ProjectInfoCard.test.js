import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ProjectInfoCard from '../../components/project/ProjectInfoCard.vue'

describe('ProjectInfoCard', () => {
  it('renders project name', () => {
    const wrapper = mount(ProjectInfoCard, {
      props: {
        projectId: 'test-123',
        projectData: { name: '我的项目', status: 'delivered', iteration: 3, requirement: '做个计算器' }
      }
    })
    expect(wrapper.text()).toContain('我的项目')
    expect(wrapper.text()).toContain('delivered')
  })

  it('shows empty state when no data', () => {
    const wrapper = mount(ProjectInfoCard, {
      props: { projectId: 'test-123', projectData: null }
    })
    // Component shows card header but no content when projectData is null
    expect(wrapper.text()).toContain('项目信息')
  })
})
