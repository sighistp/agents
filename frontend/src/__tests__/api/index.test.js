import { describe, it, expect, beforeEach, vi } from 'vitest'
import { api } from '../../api/index.js'

describe('api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('login 发送 POST 请求到 /api/auth/login', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ token: 'abc', username: 'user' }),
    })

    const result = await api.login('user', 'pass')

    expect(fetchSpy).toHaveBeenCalledWith('/api/auth/login', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ username: 'user', password: 'pass' }),
    }))
    expect(result.token).toBe('abc')
  })

  it('请求带 Authorization header', async () => {
    localStorage.setItem('token', 'my-token')
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    })

    await api.getSettings()

    expect(fetchSpy).toHaveBeenCalledWith('/api/settings', expect.objectContaining({
      headers: expect.objectContaining({
        'Authorization': 'Bearer my-token',
      }),
    }))
  })

  it('401 响应应清除 token', async () => {
    localStorage.setItem('token', 'expired')
    vi.spyOn(global, 'fetch').mockResolvedValue({
      status: 401,
      ok: false,
      json: () => Promise.resolve({}),
    })

    await expect(api.getSettings()).rejects.toThrow('Unauthorized')
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('非 ok 响应应抛出错误', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: 'Server Error' }),
    })

    await expect(api.getSettings()).rejects.toThrow('Server Error')
  })
})
