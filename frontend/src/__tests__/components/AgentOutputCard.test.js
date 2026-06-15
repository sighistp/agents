// frontend/src/__tests__/components/AgentOutputCard.test.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AgentOutputCard from '../../components/AgentOutputCard.vue'

describe('AgentOutputCard', () => {
  it('PM 消息显示用户故事数', () => {
    const wrapper = mount(AgentOutputCard, {
      props: { msg: { name: 'pm', content: '已拆分 3 个用户故事', data: { data: { user_stories: [{}, {}, {}], features: [{}, {}] } } } }
    })
    expect(wrapper.text()).toContain('3 个用户故事')
    expect(wrapper.text()).toContain('2 个功能特性')
  })

  it('Developer 消息显示文件列表', () => {
    const wrapper = mount(AgentOutputCard, {
      props: { msg: { name: 'developer', content: '完成', data: { data: { files: { 'main.py': 'x=1', 'index.html': '<html>' } } } } }
    })
    expect(wrapper.text()).toContain('main.py')
    expect(wrapper.text()).toContain('index.html')
  })

  it('Tester 消息显示测试结果', () => {
    const wrapper = mount(AgentOutputCard, {
      props: { msg: { name: 'tester', content: '测试完成', data: { data: { test_passed: false, test_results: [{ summary: '2 passed, 1 failed' }] } } } }
    })
    expect(wrapper.text()).toContain('2 passed, 1 failed')
  })

  it('Reviewer 消息显示审查结论', () => {
    const wrapper = mount(AgentOutputCard, {
      props: { msg: { name: 'reviewer', content: '审查不通过', data: { data: { review_approved: false, review_comments: [{ severity: 'important', description: '问题' }] } } } }
    })
    expect(wrapper.text()).toContain('问题')
  })

  it('未知 agent 退化为纯文本', () => {
    const wrapper = mount(AgentOutputCard, {
      props: { msg: { name: 'unknown', content: '纯文本消息', data: {} } }
    })
    expect(wrapper.text()).toContain('纯文本消息')
  })

  it('data 缺失时不崩溃', () => {
    const wrapper = mount(AgentOutputCard, {
      props: { msg: { name: 'developer', content: '内容' } }
    })
    expect(wrapper.text()).toContain('内容')
  })
})
