import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ProjectFilesPanel from '../../components/project/ProjectFilesPanel.vue'

describe('ProjectFilesPanel', () => {
  it('renders file list', () => {
    const wrapper = mount(ProjectFilesPanel, {
      props: {
        projectId: 'test-123',
        projectData: { files: { 'main.py': 'print("hello")', 'style.css': 'body{}' } }
      }
    })
    expect(wrapper.text()).toContain('main.py')
    expect(wrapper.text()).toContain('style.css')
  })

  it('shows empty state when no files', () => {
    const wrapper = mount(ProjectFilesPanel, {
      props: { projectId: 'test-123', projectData: { files: {} } }
    })
    expect(wrapper.text()).toContain('暂无文件')
  })
})
