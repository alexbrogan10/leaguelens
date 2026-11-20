import { describe, expect, it } from 'vitest'
import { luckLabel, pct, record, signed } from '../format'

describe('format', () => {
  it('formats records with optional ties', () => {
    expect(record(7, 3, 0)).toBe('7-3')
    expect(record(7, 2, 1)).toBe('7-2-1')
  })
  it('signs numbers', () => {
    expect(signed(1.25)).toBe('+1.3')
    expect(signed(-0.5)).toBe('-0.5')
    expect(signed(0)).toBe('0.0')
  })
  it('formats percentages and luck', () => {
    expect(pct(0.625)).toBe('63%')
    expect(luckLabel(2)).toBe('Very lucky')
    expect(luckLabel(-0.7)).toBe('Unlucky')
    expect(luckLabel(0.1)).toBe('Neutral')
  })
})
