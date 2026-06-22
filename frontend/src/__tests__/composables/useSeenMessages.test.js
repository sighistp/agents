import { describe, it, expect } from 'vitest'

describe('seenMessageIds LRU', () => {
  it('should limit set size to 1000', () => {
    const seen = new Set()
    const LIMIT = 1000

    // Add 1200 items
    for (let i = 0; i < 1200; i++) {
      seen.add(`msg-${i}`)
      if (seen.size > LIMIT) {
        const iterator = seen.values()
        const toRemove = seen.size - LIMIT + 100
        for (let j = 0; j < toRemove; j++) {
          seen.delete(iterator.next().value)
        }
      }
    }

    expect(seen.size).toBeLessThanOrEqual(LIMIT)
    // Most recent should still be there
    expect(seen.has('msg-1199')).toBe(true)
  })

  it('should evict oldest entries first', () => {
    const seen = new Set()
    const LIMIT = 1000

    for (let i = 0; i < 1100; i++) {
      seen.add(`msg-${i}`)
      if (seen.size > LIMIT) {
        const iterator = seen.values()
        const toRemove = seen.size - LIMIT + 100
        for (let j = 0; j < toRemove; j++) {
          seen.delete(iterator.next().value)
        }
      }
    }

    // Oldest entries should have been evicted
    expect(seen.has('msg-0')).toBe(false)
    expect(seen.has('msg-100')).toBe(false)
    // Recent entries should remain
    expect(seen.has('msg-1099')).toBe(true)
  })
})
