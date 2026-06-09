import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWsStore } from '../../stores/websocket.js'
import { useAuthStore } from '../../stores/auth.js'
import { useProjectStore } from '../../stores/project.js'

// Mock WebSocket
class MockWebSocket {
  constructor(url) {
    this.url = url
    this.readyState = 1
    this.onopen = null
    this.onmessage = null
    this.onclose = null
    this.onerror = null
    MockWebSocket.instance = this
  }
  send(data) { this.sent = data }
  close() { this.closed = true }
  static instance = null
}

describe('useWebSocket', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
    MockWebSocket.instance = null
    global.WebSocket = MockWebSocket
  })

  it('无 token 时不连接', async () => {
    const { useWebSocket } = await import('../../composables/useWebSocket.js')
    const { connect } = useWebSocket()
    connect()
    expect(MockWebSocket.instance).toBeNull()
  })

  it('有 token 时创建 WebSocket 连接', async () => {
    const authStore = useAuthStore()
    authStore.setAuth('test-token', 'user')

    const { useWebSocket } = await import('../../composables/useWebSocket.js')
    const { connect } = useWebSocket()
    connect()

    expect(MockWebSocket.instance).not.toBeNull()
    expect(MockWebSocket.instance.url).toContain('test-token')
  })

  it('收到 agent_start 消息时更新 agentStatus', async () => {
    const authStore = useAuthStore()
    authStore.setAuth('test-token', 'user')
    const projectStore = useProjectStore()

    const { useWebSocket } = await import('../../composables/useWebSocket.js')
    const { connect } = useWebSocket()
    connect()

    // 模拟收到消息
    MockWebSocket.instance.onmessage({
      data: JSON.stringify({ type: 'agent_start', agent: 'pm' })
    })

    expect(projectStore.agentStatus.pm).toBe('running')
  })

  it('收到 agent_done 消息时更新状态为 done', async () => {
    const authStore = useAuthStore()
    authStore.setAuth('test-token', 'user')
    const projectStore = useProjectStore()

    const { useWebSocket } = await import('../../composables/useWebSocket.js')
    const { connect } = useWebSocket()
    connect()

    MockWebSocket.instance.onmessage({
      data: JSON.stringify({ type: 'agent_done', agent: 'pm' })
    })

    expect(projectStore.agentStatus.pm).toBe('done')
  })

  it('收到 interrupt 消息时设置 interrupt', async () => {
    const authStore = useAuthStore()
    authStore.setAuth('test-token', 'user')
    const projectStore = useProjectStore()

    const { useWebSocket } = await import('../../composables/useWebSocket.js')
    const { connect } = useWebSocket()
    connect()

    MockWebSocket.instance.onmessage({
      data: JSON.stringify({ type: 'interrupt', data: { type: 'confirm', message: '请确认' } })
    })

    expect(projectStore.interrupt).not.toBeNull()
    expect(projectStore.interrupt.type).toBe('confirm')
  })

  it('disconnect 关闭连接', async () => {
    const authStore = useAuthStore()
    authStore.setAuth('test-token', 'user')

    const { useWebSocket } = await import('../../composables/useWebSocket.js')
    const { connect, disconnect } = useWebSocket()
    connect()
    disconnect()

    expect(MockWebSocket.instance.closed).toBe(true)
  })
})
