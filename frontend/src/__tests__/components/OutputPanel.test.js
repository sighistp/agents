import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useProjectStore } from '../../stores/project.js'
import OutputPanel from '../../components/OutputPanel.vue'

describe('OutputPanel', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('无文件时不显示', () => {
    const wrapper = mount(OutputPanel)
    expect(wrapper.find('.output-panel').exists()).toBe(false)
  })

  it('有文件时显示文件列表', async () => {
    const store = useProjectStore()
    store.files = { 'main.py': 'print("hello")', 'index.html': '<html></html>' }
    const wrapper = mount(OutputPanel)
    expect(wrapper.text()).toContain('main.py')
    expect(wrapper.text()).toContain('index.html')
  })
})
