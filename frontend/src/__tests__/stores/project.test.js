import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useProjectStore } from '../../stores/project.js'

describe('projectStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认状态正确', () => {
    const store = useProjectStore()
    expect(store.messages).toEqual([])
    expect(store.agentStatus).toEqual({})
    expect(store.iteration).toBe(0)
    expect(store.maxIterations).toBe(3)
    expect(store.files).toEqual({})
    expect(store.interrupt).toBeNull()
  })

  it('addMessage 添加消息并附加 timestamp', () => {
    const store = useProjectStore()
    store.addMessage({ role: 'user', name: 'user', content: 'hello' })
    expect(store.messages).toHaveLength(1)
    expect(store.messages[0].content).toBe('hello')
    expect(store.messages[0].timestamp).toBeDefined()
  })

  it('setAgentStatus 更新指定 Agent 状态', () => {
    const store = useProjectStore()
    store.setAgentStatus('pm', 'running')
    expect(store.agentStatus.pm).toBe('running')
    store.setAgentStatus('pm', 'done')
    expect(store.agentStatus.pm).toBe('done')
  })

  it('agentList 按固定顺序返回 Agent 列表', () => {
    const store = useProjectStore()
    store.setAgentStatus('pm', 'done')
    store.setAgentStatus('developer', 'running')
    const list = store.agentList
    expect(list).toHaveLength(5)
    expect(list[0]).toEqual({ name: 'pm', status: 'done' })
    expect(list[1]).toEqual({ name: 'architect', status: 'waiting' })
    expect(list[2]).toEqual({ name: 'developer', status: 'running' })
    expect(list[3]).toEqual({ name: 'tester', status: 'waiting' })
    expect(list[4]).toEqual({ name: 'reviewer', status: 'waiting' })
  })

  it('reset 清空所有状态', () => {
    const store = useProjectStore()
    store.addMessage({ role: 'user', name: 'user', content: 'test' })
    store.setAgentStatus('pm', 'done')
    store.iteration = 3
    store.reset()
    expect(store.messages).toEqual([])
    expect(store.agentStatus).toEqual({})
    expect(store.iteration).toBe(0)
    expect(store.files).toEqual({})
    expect(store.interrupt).toBeNull()
  })
})
