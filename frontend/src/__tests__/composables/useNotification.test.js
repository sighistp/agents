import { describe, it, expect, vi } from 'vitest'
import { useNotification, _notifications } from '../../composables/useNotification.js'

describe('useNotification', () => {
  beforeEach(() => {
    _notifications.value = []
  })

  it('adds success notification', () => {
    const { success } = useNotification()
    success('测试消息')
    expect(_notifications.value.length).toBe(1)
    expect(_notifications.value[0].message).toBe('测试消息')
    expect(_notifications.value[0].type).toBe('success')
  })

  it('adds error notification', () => {
    const { error } = useNotification()
    error('出错了')
    expect(_notifications.value.length).toBe(1)
    expect(_notifications.value[0].type).toBe('error')
  })

  it('adds warning notification', () => {
    const { warning } = useNotification()
    warning('注意')
    expect(_notifications.value.length).toBe(1)
    expect(_notifications.value[0].type).toBe('warning')
  })

  it('adds info notification', () => {
    const { info } = useNotification()
    info('提示')
    expect(_notifications.value.length).toBe(1)
    expect(_notifications.value[0].type).toBe('info')
  })

  it('removes notification', () => {
    const { success, remove } = useNotification()
    success('test')
    const id = _notifications.value[0].id
    remove(id)
    expect(_notifications.value.length).toBe(0)
  })
})
