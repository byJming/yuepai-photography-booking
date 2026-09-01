import { describe, expect, it } from 'vitest'

import { moveItem } from './collections'

describe('moveItem', () => {
  it('moves an item without mutating the source array', () => {
    const source = ['a', 'b', 'c']

    const result = moveItem(source, 2, 0)

    expect(result).toEqual(['c', 'a', 'b'])
    expect(source).toEqual(['a', 'b', 'c'])
  })

  it('returns a copy when the target is outside the list', () => {
    const source = ['a', 'b']

    const result = moveItem(source, 0, 3)

    expect(result).toEqual(source)
    expect(result).not.toBe(source)
  })
})
