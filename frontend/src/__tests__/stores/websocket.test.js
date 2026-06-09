import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWsStore } from '../../stores/websocket.js'

describe('wsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认状态正确', () => {
    const store = useWsStore()
    expect(store.isConnected).toBe(false)
    expect(store.reconnecting).toBe(false)
    expect(store.lastError).toBeNull()
  })

  it('可以更新连接状态', () => {
    const store = useWsStore()
    store.isConnected = true
    store.reconnecting = false
    expect(store.isConnected).toBe(true)
  })
})
