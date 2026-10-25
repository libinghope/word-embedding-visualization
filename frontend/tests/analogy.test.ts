import { describe, expect, it } from 'vitest'
import { parseExpression } from '../src/lib/analogy'
describe('expression parser', () => {
  it('preserves raw terms, casing, duplicates, and signs', () => {
    expect(parseExpression(' king - man + woman ')).toEqual({ positive: ['king', 'woman'], negative: ['man'] })
    expect(parseExpression('New_York + king + king - king')).toEqual({ positive: ['New_York', 'king', 'king'], negative: ['king'] })
  })
  it.each(['', 'king +', 'king / man', 'king - +', 'king man', Array(11).fill('king').join(' + ')])('rejects malformed expression %s', value => {
    expect(() => parseExpression(value)).toThrow()
  })
})
