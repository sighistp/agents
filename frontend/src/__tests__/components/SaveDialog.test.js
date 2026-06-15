// frontend/src/__tests__/components/SaveDialog.test.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SaveDialog from '../../components/SaveDialog.vue'

describe('SaveDialog', () => {
  it('显示默认名称', () => {
    const wrapper = mount(SaveDialog, { props: { visible: true, defaultName: '紫色计算器' } })
    expect(wrapper.find('input').element.value).toBe('紫色计算器')
  })

  it('确认时 emit save 事件', async () => {
    const wrapper = mount(SaveDialog, { props: { visible: true, defaultName: '测试项目' } })
    await wrapper.find('input').setValue('我的项目')
    await wrapper.find('.btn-confirm').trigger('click')
    expect(wrapper.emitted('save')[0]).toEqual(['我的项目'])
  })

  it('取消时 emit update:visible', async () => {
    const wrapper = mount(SaveDialog, { props: { visible: true, defaultName: '测试' } })
    await wrapper.find('.btn-cancel').trigger('click')
    expect(wrapper.emitted('update:visible')[0]).toEqual([false])
  })

  it('空名称时用默认名称', async () => {
    const wrapper = mount(SaveDialog, { props: { visible: true, defaultName: '默认名称' } })
    await wrapper.find('input').setValue('')
    await wrapper.find('.btn-confirm').trigger('click')
    expect(wrapper.emitted('save')[0]).toEqual(['默认名称'])
  })

  it('名称超过 50 字截断', async () => {
    const wrapper = mount(SaveDialog, { props: { visible: true, defaultName: '测试' } })
    const longName = 'a'.repeat(60)
    await wrapper.find('input').setValue(longName)
    await wrapper.find('.btn-confirm').trigger('click')
    expect(wrapper.emitted('save')[0][0].length).toBeLessThanOrEqual(50)
  })
})
